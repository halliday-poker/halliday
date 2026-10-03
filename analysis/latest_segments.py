"""Record the exact newest observed intervals used by an analysis rerun."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from opponent_model.data import load_cache
from opponent_model.behavior import metrics, MODES
from sparring.competitors.build import latest_profiles
from sparring.competitors.catalog import spec


def select(directory, profiles_path):
    report = json.loads((directory/'opponent-estimates.json').read_text())
    manifest = json.loads(profiles_path.read_text())
    profiles = manifest['profiles']
    assert profiles == latest_profiles(report), 'Generated profiles are not the latest report intervals'
    assert manifest['report_sha256'] == sha256((directory/'opponent-estimates.json').read_bytes()).hexdigest()
    data = load_cache(directory/'context-features.npz')
    assert manifest['input_audit']['actions_sha256'] == data.audit['actions_sha256']
    metadata = {m['id']: m for m in data.matches}
    observed = {m['id'] for i, m in enumerate(data.matches) if any(i in hands for hands in data.hands.values())}
    events = json.loads((directory/'behavior-input.json').read_text())['upload_events']
    included, excluded, selected = [], {}, {}
    for name, profile in profiles.items():
        ids = [mid for mid in profile['match_ids'] if mid in observed and metadata[mid]['kind'] == 'ladder']
        latest_upload = max((e['at'] for e in events.get(name, []) if e['passed'] and e['trusted_time']), default=None)
        selected[name] = dict(segment=profile['segment'], epoch=profile['epoch'],
            matches=len(ids), match_ids=ids, from_utc=profile['observed_from_utc'],
            through_utc=profile['observed_through_utc'], boundary_from=profile['boundary_from'],
            known_play_times=profile['known_play_times'], latest_successful_upload=latest_upload,
            newer_upload_without_observed_ladder_data=bool(latest_upload and latest_upload > profile['observed_through']),
            policy_status=profile['behavior']['status'])
        if name == 'Halliday':
            excluded[name] = 'Replaced by the exact current-main baseline'
        elif name.startswith('house:'):
            excluded[name] = 'House validation bot, not an external team'
        elif not ids:
            excluded[name] = 'No observed ladder matches in the selected interval'
        elif not profile['known_play_times']:
            excluded[name] = 'No trusted play timestamp; latest submission cannot be assigned reliably'
        else:
            included.append(name)
    hero = selected['Halliday']['match_ids']
    if not hero or not selected['Halliday']['known_play_times']:
        raise ValueError('No reliably dated latest Halliday interval')
    strict = [mid for mid in hero if all(mid in selected.get(name, {}).get('match_ids', []) for name in metadata[mid]['names'])]
    prefix = profiles_path.parent.resolve().relative_to(ROOT).as_posix()
    catalog = prefix+'/'+manifest['catalog']
    pool = [f'{spec(catalog, profiles[name]["id"])} 1' for name in included]
    pool_text = '# Latest trusted observed ladder interval per external identity.\n'+'\n'.join(pool)+'\n'
    (directory/'latest-field-pool.txt').write_text(pool_text)
    (profiles_path.parent/'latest-pool.txt').write_text(pool_text)
    for filename, ids in [('latest-halliday-matches.json', hero), ('strict-latest-halliday-matches.json', strict)]:
        (directory/filename).write_text(json.dumps(sorted(ids), indent=2)+'\n')
    matched = [[spec(catalog, profiles[name]['id']) for name in metadata[mid]['names'] if name != 'Halliday']
               for mid in sorted(strict)]
    (directory/'latest-matched-tables.json').write_text(json.dumps(matched, indent=2)+'\n')
    result = dict(input_actions_sha256=data.audit['actions_sha256'], profiles_sha256=sha256(profiles_path.read_bytes()).hexdigest(),
        selection='Newest observed interval per display identity; never pooled historical replicas.',
        included_opponents=included, excluded=excluded, profiles=selected,
        latest_halliday_matches=len(hero), all_seats_latest_matches=len(strict),
        training_scope='Shared behavior model learns from historical intervals with separate epoch features. Only newest intervals are instantiated in this field.',
        caveat='A successful validation identifies an upload, not a proven deployment. Unobserved uploads and identity renames cannot be recreated from actions alone.')
    (directory/'latest-selection.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def predictive(directory, selection):
    with np.load(directory/'behavior-data.npz', allow_pickle=False) as archive:
        meta = json.loads(str(archive['metadata']))
        data = {key: archive[key].copy() for key in archive.files if key != 'metadata'}
    data['primary'] = np.asarray([m['kind'] == 'ladder' for m in meta['matches']])[data['match']]
    latest = np.zeros(len(data['y']), dtype=bool)
    match_indices = {m['id']: i for i, m in enumerate(meta['matches'])}
    eligible = set(selection['included_opponents']) | {'Halliday'}
    for index, bot in enumerate(meta['bots']):
        if bot not in eligible:
            continue
        indices = [match_indices[mid] for mid in selection['profiles'][bot]['match_ids']]
        latest |= (data['bot'] == index) & np.isin(data['match'], indices)
    mask = latest & (data['split'] == 2)
    if not mask.any():
        raise ValueError('No held-out newest-interval observations')
    scores = {'original_scaffold': metrics(data, data['baseline'], data['baseline_size'], mask)}
    for mode in MODES:
        with np.load(directory/f'predictions-{mode}.npz', allow_pickle=False) as pred:
            scores[mode] = metrics(data, pred['probability'], pred['sizing'], mask)
    paired = []
    rng = np.random.default_rng(92061004)
    for reference in ('original_scaffold', 'none', 'placebo'):
        left, right = scores[reference]['by_match'], scores['upload']['by_match']
        common = sorted(set(left) & set(right))
        differences = np.asarray([left[mid]['nll'] - right[mid]['nll'] for mid in common])
        boot = differences[rng.integers(len(common), size=(5000, len(common)))].mean(1)
        paired.append(dict(reference=reference, candidate='upload', matches=len(common),
                           mean_match_nll_gain=float(differences.mean()),
                           ci95=np.quantile(boot, [.025, .975]).tolist(),
                           three_comparison_adjusted_ci=np.quantile(boot, [.025/3, 1-.025/3]).tolist()))
    result = dict(scope='Held-out actions in the newest trusted ladder intervals of Halliday and included external identities; whole-match split unchanged. Other seats need not be in their newest interval for this conditional action-prediction test.',
                  actions=int(mask.sum()), matches=int(len(np.unique(data['match'][mask]))),
                  selection='Model choice remains validation-only; these test metrics are descriptive and are not used to switch models.',
                  paired_comparisons=paired, models=scores)
    (directory/'latest-predictive-comparison.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--profiles', type=Path, default=ROOT/'sparring/competitors/from_data/profiles.json')
    args = parser.parse_args()
    selection = select(args.directory, args.profiles)
    scores = predictive(args.directory, selection)
    print(json.dumps(dict(opponents=len(selection['included_opponents']), latest_halliday_matches=selection['latest_halliday_matches'],
                         all_seats_latest_matches=selection['all_seats_latest_matches'], heldout_latest_actions=scores['actions']), indent=2))
