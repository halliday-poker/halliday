"""CUDA fits of all ten scaffold settings by game window and pooled phase."""
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import json
from pathlib import Path
import time

import numpy as np
import torch

from .compute import Compute
from .data import COL
from .fit import BotModel, PARAMETERS
from .within_game import read


def hand_counts(hands, key_column=0):
    return {int(m): [len(group), int(group[:, 4].sum()), int(group[:, 5].sum())]
            for m in np.unique(hands[:, key_column]) for group in [hands[hands[:, key_column] == m]]}


def fit_windows(directory, devices):
    began = time.monotonic(); torch.set_num_threads(1)
    meta, data = read(directory)
    bots = np.unique(data['bot']).tolist()
    computes = [Compute(f'cuda:{d}', batch_size=128, memory_limit_mib=768, seed=72861) for d in devices]

    def shard(worker):
        compute = computes[worker]; torch.cuda.set_device(compute.device)
        output = {}; windows = []
        for b in bots[worker::len(computes)]:
            name = meta['bots'][b]
            rows = data['rows'][data['bot'] == b].astype(np.float64)
            hands = data['hands'][data['hands'][:, 2] == b]
            matches = sorted(map(int, np.unique(hands[:, 0])))
            # Complete games allow the same bootstrap draw to represent the
            # same match in every phase; no independent-window pseudoreplication.
            counts = hand_counts(hands)
            complete = [m for m in matches if counts[m][0] == 100]
            phases, draws = [], []
            for phase in range(5):
                selected_rows = rows[np.isin(rows[:, COL['match']], complete)
                                     & (rows[:, COL['hand']]//20 == phase)]
                selected_hands = hands[np.isin(hands[:, 0], complete) & (hands[:, 1]//20 == phase)]
                if not len(selected_hands):
                    continue
                model = BotModel(selected_rows, hand_counts(selected_hands), compute)
                compute.generator.manual_seed(72861+b)
                estimate = model.estimate(list(range(len(model.matches))), bootstrap=300)
                compute.generator.manual_seed(72861+b)
                weights = compute.bootstrap_weights(list(range(len(model.matches))), len(model.matches), 300)
                values, _ = model.fit_weights(weights)
                draws.append(values.cpu().numpy())
                phases.append(dict(phase=phase, hand_from=phase*20, hand_through=phase*20+19,
                    matches=len(model.matches), hands=len(selected_hands), chips=float(selected_hands[:, 3].sum()),
                    fold_rate=float(selected_hands[:, 6].mean()), vpip=float(selected_hands[:, 4].mean()),
                    pfr=float(selected_hands[:, 5].mean()), mean_card_percentile=float(np.nanmean(selected_rows[selected_rows[:, COL['street']] == 0, COL['pct']])),
                    **estimate))
            change = {}
            if len(draws) == 5:
                delta = draws[-1]-draws[0]
                for j, parameter in enumerate(PARAMETERS):
                    change[parameter] = dict(estimate=float(delta[0, j]),
                        paired_match_bootstrap_interval=np.quantile(delta[1:, j], [.025, .975]).tolist(),
                        warning='Descriptive interval conditional on grid and surrogate; not a regular parameter-change significance test.')
            # Fit at most 16 games as separate windows at once. Other games
            # collapse into one sufficient-statistics group to bound GPU memory.
            for start in range(0, len(matches), 16):
                current = matches[start:start+16]
                keys = [(m, w) for m in current for w in range(10)
                        if ((hands[:, 0] == m) & (hands[:, 1]//10 == w)).any()]
                mapping = {key: i+1 for i, key in enumerate(keys)}
                units = np.asarray([mapping.get((int(m), int(h)//10), 0)
                                    for m, h in rows[:, [COL['match'], COL['hand']]]])
                hand_units = np.asarray([mapping.get((int(m), int(h)//10), 0) for m, h in hands[:, :2]])
                grouped_rows = rows.copy(); grouped_rows[:, COL['match']] = units
                grouped_hands = hands.copy(); grouped_hands[:, 0] = hand_units
                local_counts = hand_counts(grouped_hands)
                model = BotModel(grouped_rows, local_counts, compute)
                indices = {unit: i for i, unit in enumerate(model.matches)}
                weights = np.zeros((len(keys), len(indices)))
                raw_weights = np.zeros_like(weights)
                for i, (m, window) in enumerate(keys):
                    outside = [unit for unit in model.matches if unit == 0 or keys[unit-1][0] != m]
                    prior_hands = sum(local_counts[unit][0] for unit in outside)
                    if prior_hands:
                        weights[i, [indices[unit] for unit in outside]] = 20/prior_hands
                    weights[i, indices[i+1]] = 1
                    raw_weights[i, indices[i+1]] = 1
                values, _ = model.fit_weights(compute.array(weights))
                raw, _ = model.fit_weights(compute.array(raw_weights))
                values, raw = values.cpu().numpy(), raw.cpu().numpy()
                for i, (m, window) in enumerate(keys):
                    h = hands[(hands[:, 0] == m) & (hands[:, 1]//10 == window)]
                    entry = dict(bot=name, match=meta['matches'][m]['id'], epoch=meta['profiles'][name]['epoch'],
                                 hand_from=10*window, hand_through=10*window+9, hands=len(h),
                                 chips=int(h[:, 3].sum()), vpip_rate=float(h[:, 4].mean()),
                                 pfr_rate=float(h[:, 5].mean()), fold_rate=float(h[:, 6].mean()),
                                 prior_hands=20 if counts[m][0] < len(hands) else 0)
                    local = indices[i+1]
                    for j, parameter in enumerate(PARAMETERS):
                        block = model.blocks[model.block_for(parameter, int(values[i, -1]))]
                        count = float(block.counts[local])
                        if parameter == 'cbet':
                            count = float((block.totals[local]*block.features[:, 2]).sum())
                        elif parameter == 'adaptive':
                            count = float(model.blocks['post0'].counts[local] + model.blocks['stick0'].counts[local])
                        entry[parameter] = float(values[i, j])
                        entry[parameter+'_opportunities'] = int(count)
                        entry[parameter+'_raw'] = float(raw[i, j]) if count >= 10 else None
                    windows.append(entry)
            output[name] = dict(epoch=meta['profiles'][name]['epoch'], segment=meta['profiles'][name]['segment'],
                matches=len(matches), complete_matches=len(complete), hands=len(hands), phases=phases,
                late_minus_early=change, selected_match_ids=[meta['matches'][m]['id'] for m in matches])
            print(json.dumps(dict(event='window-fit', bot=name, matches=len(matches), device=str(compute.device))), flush=True)
        return output, windows

    with ThreadPoolExecutor(max_workers=len(computes)) as executor:
        shards = list(executor.map(shard, range(len(computes))))
    result = dict(bots={k: v for out, _ in shards for k, v in out.items()},
                  devices=[c.metadata() for c in computes], seconds=time.monotonic()-began,
                  input_actions_sha256=meta['input_audit']['actions_sha256'],
                  notes=['Scaffold settings are inverse-fit surrogate summaries, not recovered source constants.',
                         'Individual ten-hand windows are sparse; shrunk values can be prior-dominated. Raw values need ten local opportunities.',
                         'The 20-hand pooled phases resample complete matches jointly. Current-game data is excluded from each per-window prior.',
                         'No test information from these descriptive fits is used to train or select predictive models.'])
    (directory/'dynamics-windows.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    windows = sorted((row for _, rows in shards for row in rows), key=lambda r: (r['bot'], r['match'], r['hand_from']))
    with gzip.open(directory/'dynamics-game-windows.csv.gz', 'wt', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(windows[0])); writer.writeheader(); writer.writerows(windows)
    print(json.dumps(dict(window_rows=len(windows), bots=len(result['bots']), seconds=result['seconds'])), flush=True)
