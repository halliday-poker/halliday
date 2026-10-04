"""Newest-interval, whole-match tests of progress and public-history effects.

Run prepare, windows, train, then analysis/report_within_game.py. These models
are diagnostics; they do not replace the simulator's selected static policy.
"""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
import json
import multiprocessing as mp
from pathlib import Path
import time

import numpy as np
import torch
from torch import nn

from .behavior import Network, metrics
from .data import COL
from sparring.competitors.build import latest_profiles

MODES = ('static', 'progress', 'history', 'combined')
from sparring.competitors.patterns import HISTORY, PROGRESS, PublicHistory, progress_features

SEED = 202610041


def read(directory):
    with np.load(directory/'dynamics-data.npz', allow_pickle=False) as archive:
        meta = json.loads(str(archive['metadata']))
        data = {k: archive[k].copy() for k in archive.files if k != 'metadata'}
    data.setdefault('primary',np.ones(len(data['y']), dtype=bool))
    data.setdefault('sample_weight',np.ones(len(data['y']),dtype=np.float32))
    return meta, data


def prepare(directory, include_validation=False):
    report = json.loads((directory/'opponent-estimates.json').read_text())
    if report['segmentation_policy']['mode'] != 'upload':
        raise ValueError('This newest-submission study requires the trusted upload interval mapping')
    profiles = latest_profiles(report)
    with np.load(directory/'behavior-data.npz', allow_pickle=False) as archive:
        meta = json.loads(str(archive['metadata']))
        original = {k: archive[k].copy() for k in archive.files if k != 'metadata'}
    match_index = {m['id']: i for i, m in enumerate(meta['matches'])}
    mask = np.zeros(len(original['y']), dtype=bool)
    excluded = {}
    for b, bot in enumerate(meta['bots']):
        profile = profiles[bot]
        if profile.get('exclusion_reason'):
            excluded[bot] = profile['exclusion_reason']; continue
        if bot.startswith('house:') or profile['validation_only']:
            excluded[bot] = 'House or validation-only identity'; continue
        if not profile['known_play_times'] and not profile.get('prior_only'):
            excluded[bot] = 'No trusted play time; newest submission cannot be assigned'; continue
        ids = [match_index[mid] for mid in profile['match_ids']
               if (include_validation or meta['matches'][match_index[mid]]['kind'] == 'ladder')
               and meta['matches'][match_index[mid]].get('played_at') is not None]
        mask |= (original['bot'] == b) & np.isin(original['match'], ids)
    keys = ('rows', 'x', 'legal', 'y', 'size_y', 'size_targets', 'bot', 'match', 'split', 'baseline', 'baseline_size')
    data = {key: original[key][mask] for key in keys}
    desired = {(int(m), int(h), int(b)) for m, h, b in
               zip(data['match'], data['rows'][:, COL['hand']], data['bot'])}
    eligible = {(m, b) for m, _, b in desired}
    names_to_index = {name: i for i, name in enumerate(meta['bots'])}
    match_set = {m for m, _, _ in desired}
    contexts, hand_rows, histories = {}, [], {}
    current, events = None, []

    def consume(key, group):
        mid, hand = key
        m = match_index[mid]
        if m not in match_set:
            return
        names = meta['matches'][m]['names']
        history = histories.setdefault(mid, PublicHistory(names))
        if history.hands != hand or group[-1].get('event') != 'hand_end':
            raise ValueError(f'{key}: incomplete or unordered hand')
        for name in names:
            index = names_to_index[name]
            if (m, index) in eligible:
                contexts[m, hand, index] = history.before(name)
        end = group[-1]
        deltas = dict(zip(end['deltas_bot_names'], end['deltas_by_bot']))
        measured = history.finish([e for e in group if 'action' in e], deltas)
        for name in names:
            b = names_to_index[name]
            if (m, b) in eligible:
                hand_rows.append([m, hand, b, *measured[name]])

    digest = sha256()
    with (directory/'source/actions.jsonl').open('rb') as stream:
        for raw in stream:
            digest.update(raw)
            event = json.loads(raw)
            key = event['match'], event['hand']
            if current is not None and key != current:
                consume(current, events); events = []
            current = key; events.append(event)
    if current is not None:
        consume(current, events)
    assert digest.hexdigest() == meta['input_audit']['actions_sha256']
    assert desired <= set(contexts), 'Every action must have a preceding public history'
    data['history'] = np.asarray([contexts[int(m), int(h), int(b)] for m, h, b in
        zip(data['match'], data['rows'][:, COL['hand']], data['bot'])])
    data['progress'] = progress_features(data['rows'][:, COL['hand']])
    data['hands'] = np.asarray(hand_rows, dtype=np.float64)
    meta.update(excluded=excluded, profiles=profiles, history_features=HISTORY, progress_features=PROGRESS,
                hand_columns=['match', 'hand', 'bot', 'chips', 'vpip', 'pfr', 'fold'],
                selection='Each identity in its newest trusted observed upload interval. Other seats may use the versions actually encountered.',
                history_scope='Only public actions and settled results from strictly earlier hands; no opponent cards or current-hand result.')
    np.savez_compressed(directory/'dynamics-data.npz', metadata=np.asarray(json.dumps(meta)), **data)
    plan = dict(input_actions_sha256=digest.hexdigest(), actions=len(data['y']),
                hands=len(hand_rows), matches=len(np.unique(data['match'])),
                bots=len(np.unique(data['bot'])), excluded=excluded, modes=MODES,
                split_policy=meta['split_policy'], seed=SEED, epochs=100,
                selection='Choose model and stopping by validation action NLL + 0.2 sizing-bin NLL; no test selection.',
                windows='10-hand per-game descriptions; 20-hand pooled phases with whole-match bootstrap.',
                shrinkage='Per-game/window fit adds a same-game-excluded pooled prior equal to 20 hands; insufficient local support remains flagged.',
                inference='Three prespecified model comparisons use adjusted bootstrap intervals; per-bot paired sign-permutation tests use BH FDR. Associations are not causal or recovered source parameters.')
    (directory/'dynamics-plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    print(json.dumps({k: plan[k] for k in ('actions', 'hands', 'matches', 'bots', 'excluded')}, indent=2))


def design(data, mode):
    progress = data['progress'] if mode in ('progress', 'combined') else np.zeros_like(data['progress'])
    history = data['history'] if mode in ('history', 'combined') else np.zeros_like(data['history'])
    return np.concatenate([data['x'], progress, history], axis=1)


def train_one(job):
    directory, mode, device, epochs = job
    directory = Path(directory); began = time.monotonic()
    torch.set_num_threads(1); torch.manual_seed(SEED); torch.cuda.set_device(device)
    total = torch.cuda.get_device_properties(device).total_memory
    from .compute import memory_limit_mib
    torch.cuda.set_per_process_memory_fraction(memory_limit_mib()*2**20/total, device)
    meta, data = read(directory)
    gpu = torch.device(f'cuda:{device}')
    tensors = {key: torch.as_tensor(data[key], device=gpu) for key in ('y', 'size_y', 'bot', 'legal')}
    tensors['x'] = torch.as_tensor(design(data, mode), device=gpu)
    tensors['epoch'] = torch.zeros(len(data['y']), device=gpu, dtype=torch.long)
    network = Network(tensors['x'].shape[1], len(meta['bots']), 1).to(gpu)
    optimizer = torch.optim.AdamW(network.parameters(), lr=.003, weight_decay=.005)
    training_weight=data.get('training_weight',data['sample_weight'])
    tensors['weight']=torch.as_tensor(training_weight,device=gpu)
    training = torch.as_tensor(np.flatnonzero((data['split'] == 0)&(training_weight>0)), device=gpu)
    validation_mask=(data['split']==1)&data['primary']
    validation = torch.as_tensor(np.flatnonzero(validation_mask), device=gpu)

    def predict(indices, replacement=None):
        network.eval(); probabilities, sizes = [], []
        with torch.no_grad():
            for idx in indices.split(8192):
                x = tensors['x'][idx].clone()
                if replacement:
                    for column, value in replacement.items():
                        x[:, column] = value
                a, s = network(x, tensors['bot'][idx], tensors['epoch'][idx], tensors['legal'][idx])
                probabilities.append(a.softmax(1).cpu().numpy()); sizes.append(s.softmax(1).cpu().numpy())
        return np.concatenate(probabilities), np.concatenate(sizes)

    best, weights, curve = float('inf'), None, []
    for epoch in range(1, epochs+1):
        network.train()
        order = training[torch.randperm(len(training), device=gpu)]
        for idx in order.split(8192):
            a, s = network(tensors['x'][idx], tensors['bot'][idx], tensors['epoch'][idx], tensors['legal'][idx])
            w=tensors['weight'][idx]
            loss = (nn.functional.cross_entropy(a, tensors['y'][idx],reduction='none')*w).sum()/w.sum()
            raises = tensors['y'][idx] == 3
            if raises.any():
                loss += .2*(nn.functional.cross_entropy(s[raises], tensors['size_y'][idx][raises],reduction='none')*w[raises]).sum()/w[raises].sum()
            optimizer.zero_grad(set_to_none=True); loss.backward(); optimizer.step()
        p, sizes = predict(validation)
        y = data['y'][validation_mask]; sy = data['size_y'][validation_mask]
        nll = float(-np.log(p[np.arange(len(y)), y].clip(1e-9)).mean())
        snll = float(-np.log(sizes[np.flatnonzero(y == 3), sy[y == 3]].clip(1e-9)).mean())
        score = nll+.2*snll
        curve.append(dict(epoch=epoch, nll=nll, size_nll=snll, objective=score))
        if score < best:
            best, best_epoch = score, epoch
            weights = {k: v.detach().cpu().clone() for k, v in network.state_dict().items()}
        if epoch == 1 or epoch % 10 == 0:
            print(json.dumps(dict(mode=mode, device=device, epoch=epoch, objective=score)), flush=True)
    network.load_state_dict(weights)
    probability, sizing_prob = predict(torch.arange(len(data['y']), device=gpu))
    sizing = (sizing_prob*data['size_targets']).sum(1)
    result = dict(mode=mode, device=str(gpu), epoch=best_epoch, validation_objective=best, curve=curve,
                  validation=metrics(data, probability, sizing, data['split'] == 1),
                  test=metrics(data, probability, sizing, data['split'] == 2),
                  seconds=time.monotonic()-began, peak_allocated_bytes=torch.cuda.max_memory_allocated(gpu),
                  seed=SEED, features=tensors['x'].shape[1], input_actions_sha256=meta['input_audit']['actions_sha256'])
    np.savez_compressed(directory/f'dynamics-predictions-{mode}.npz', probability=probability, sizing=sizing)
    np.savez_compressed(directory/f'dynamics-policy-{mode}.npz', **{k: v.numpy() for k, v in weights.items()})
    # Standardized progress association: same held-out contexts, histories and
    # legal actions; only hand progress changes. This is not a causal effect.
    if mode in ('progress', 'combined'):
        test = torch.as_tensor(np.flatnonzero(data['split'] == 2), device=gpu)
        standardized = {}
        for hand in (9, 49, 89):
            replacement = {data['x'].shape[1]+i: float(value) for i, value in enumerate(progress_features([hand])[0])}
            standardized[f'hand_{hand}'] = predict(test, replacement)[0]
        np.savez_compressed(directory/f'dynamics-standardized-{mode}.npz', **standardized)
    (directory/f'dynamics-{mode}.json').write_text(json.dumps(result, indent=2)+'\n')
    return {k: result[k] for k in ('mode', 'device', 'epoch', 'seconds', 'peak_allocated_bytes')}


def explain(directory, device=0):
    """Conditional permutation diagnostics, selected using validation only."""
    torch.set_num_threads(1); torch.cuda.set_device(device)
    meta, data = read(directory)
    scores = {mode: json.loads((directory/f'dynamics-{mode}.json').read_text())['validation_objective'] for mode in MODES}
    mode = min(scores, key=scores.get)
    test = np.flatnonzero(data['split'] == 2)
    x = design(data, mode)[test]; bots = data['bot'][test]; legal = data['legal'][test]
    network = Network(x.shape[1], len(meta['bots']), 1).to(f'cuda:{device}')
    with np.load(directory/f'dynamics-policy-{mode}.npz', allow_pickle=False) as weights:
        network.load_state_dict({k: torch.as_tensor(weights[k], device=f'cuda:{device}') for k in weights.files})
    network.eval()

    def predict(matrix):
        output, sizing = [], []
        with torch.no_grad():
            for start in range(0, len(matrix), 8192):
                end = start+8192
                a, s = network(torch.as_tensor(matrix[start:end], device=f'cuda:{device}'),
                    torch.as_tensor(bots[start:end], device=f'cuda:{device}'),
                    torch.zeros(len(matrix[start:end]), dtype=torch.long, device=f'cuda:{device}'),
                    torch.as_tensor(legal[start:end], device=f'cuda:{device}'))
                output.append(a.softmax(1).cpu().numpy())
                sizing.append((s.softmax(1).cpu().numpy()*data['size_targets'][test[start:end]]).sum(1))
        return np.concatenate(output), np.concatenate(sizing)

    truth = data['y'][test]
    reference_p, reference_size = predict(x)
    reference = -np.log(reference_p[np.arange(len(test)), truth].clip(1e-9))
    reference_error = reference_size-data['rows'][test, COL['amount']]
    with np.load(directory/f'dynamics-predictions-{mode}.npz', allow_pickle=False) as saved:
        expected = -np.log(saved['probability'][test, truth].clip(1e-9))
        np.testing.assert_allclose(reference_size, saved['sizing'][test], atol=1e-4)
    np.testing.assert_allclose(reference, expected, atol=2e-5)
    base = data['x'].shape[1]
    start = base+len(PROGRESS)
    groups = {}
    if mode in ('progress', 'combined'):
        groups['hand_progress'] = list(range(base, start))
    if mode in ('history', 'combined'):
        groups.update(public_score=list(range(start, start+3)),
                      recent_results=list(range(start+3, start+6)),
                      observed_frequencies=list(range(start+6, start+12)))
    differences, size_differences = {}, {}
    for number, (group, columns) in enumerate(groups.items()):
        totals = np.zeros(len(test)); size_totals = np.zeros(len(test)); rng = np.random.default_rng(SEED+number)
        strata = defaultdict(list)
        for i, (b, h, street) in enumerate(zip(bots, data['rows'][test, COL['hand']], data['rows'][test, COL['street']])):
            strata[int(b), int(street), -1 if group == 'hand_progress' else int(h)//20].append(i)
        for repeat in range(5):
            permuted = x.copy()
            for indices in strata.values():
                indices = np.asarray(indices)
                permuted[np.ix_(indices, columns)] = x[np.ix_(rng.permutation(indices), columns)]
            p, sizing = predict(permuted)
            totals += -np.log(p[np.arange(len(test)), truth].clip(1e-9))-reference
            size_totals += (sizing-data['rows'][test, COL['amount']])**2-reference_error**2
        differences[group] = totals/5
        size_differences[group] = size_totals/5
    np.savez_compressed(directory/'dynamics-permutation.npz', **differences)
    np.savez_compressed(directory/'dynamics-permutation-sizing.npz', **size_differences)
    result = dict(model=mode, repeats=5, device=f'cuda:{device}',
        scope='Shuffle each feature group jointly within bot, street and 20-hand phase (progress uses bot/street only). Other recorded context stays fixed. Correlated predictors and implausible combinations limit causal interpretation.',
        mean_nll_increase={key: float(value.mean()) for key, value in differences.items()},
        mean_raise_mse_increase={key: float(value[truth == 3].mean()) for key, value in size_differences.items()})
    (directory/'dynamics-explanation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', choices=['prepare', 'windows', 'train', 'explain'])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--devices', default='0,1,2,3')
    parser.add_argument('--epochs', type=int, default=100)
    args = parser.parse_args(); devices = [int(d) for d in args.devices.split(',')]
    if args.step == 'prepare':
        prepare(args.directory)
    elif args.step == 'windows':
        from .within_game_windows import fit_windows
        fit_windows(args.directory, devices)
    elif args.step == 'explain':
        explain(args.directory, devices[0])
    else:
        if len(devices) != 4 or len(set(devices)) != 4:
            parser.error('Four distinct GPUs are required for simultaneous ablations')
        with ProcessPoolExecutor(max_workers=4, mp_context=mp.get_context('spawn')) as pool:
            jobs = [(str(args.directory), mode, device, args.epochs) for mode, device in zip(MODES, devices)]
            for result in pool.map(train_one, jobs):
                print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
