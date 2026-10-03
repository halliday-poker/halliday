"""Independently reconcile cohorts, hand denominators and window exports."""
import argparse
import csv
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from opponent_model.data import COL, load_cache
from opponent_model.within_game import MODES, read
from sparring.competitors.catalog import PARAMETERS, validate_style


def verify(directory):
    meta, data = read(directory)
    cache = load_cache(directory/'context-features.npz')
    windows = json.loads((directory/'dynamics-windows.json').read_text())
    collected = {m['id']: m for m in json.loads((directory/'source/matches.json').read_text())}
    digest = sha256()
    with (directory/'source/actions.jsonl').open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    assert digest.hexdigest() == cache.audit['actions_sha256'] == windows['input_actions_sha256']
    lookup = {}; selected_pairs = set()
    for b in np.unique(data['bot']):
        b = int(b); name = meta['bots'][b]; selected = meta['profiles'][name]
        rows = data['rows'][data['bot'] == b]; hands = data['hands'][data['hands'][:, 2] == b]
        assert name not in meta['excluded']
        for m in np.unique(rows[:, COL['match']]).astype(int):
            match = meta['matches'][m]
            assert match['id'] in selected['match_ids'] and match['kind'] == 'ladder' and match['played_at'] is not None
            group = hands[hands[:, 0] == m]
            np.testing.assert_array_equal(np.sort(group[:, 1]), np.arange(100))
            assert [len(group), int(group[:, 4].sum()), int(group[:, 5].sum())] == cache.hands[name][m]
            raw = collected[match['id']]
            assert int(group[:, 3].sum()) == raw['chips'][raw['names'].index(name)]
            selected_pairs.add((name, match['id']))
            for window in range(10):
                local = group[group[:, 1]//10 == window]
                actions = rows[(rows[:, COL['match']] == m) & (rows[:, COL['hand']]//10 == window)]
                post = ((actions[:, COL['street']] != 0) & np.isfinite(actions[:, COL['strength']])
                        & actions[:, COL['can_raise']].astype(bool))
                # Both free postflop bets and facing-price call/fold decisions
                # distinguish the scaffold's adaptive mode.
                adaptive = post & ((actions[:, COL['facing']] == 0) | (actions[:, COL['action']] != 3))
                lookup[name, match['id'], window] = dict(hands=len(local), chips=int(local[:, 3].sum()),
                    vpip_rate=float(local[:, 4].mean()), pfr_rate=float(local[:, 5].mean()), fold_rate=float(local[:, 6].mean()),
                    adaptive_opportunities=int(adaptive.sum()))
    seen = set()
    with gzip.open(directory/'dynamics-game-windows.csv.gz', 'rt') as stream:
        for row in csv.DictReader(stream):
            key = row['bot'], row['match'], int(row['hand_from'])//10
            assert key not in seen; seen.add(key)
            for field, expected in lookup[key].items():
                assert abs(float(row[field])-expected) < 1e-10
            validate_style(row['bot'], {key: float(row[key]) for key in PARAMETERS})
            for parameter in PARAMETERS:
                if int(row[parameter+'_opportunities']) < 10:
                    assert row[parameter+'_raw'] == ''
            profile = meta['profiles'][row['bot']]
            assert int(row['epoch']) == profile['epoch']
    assert seen == set(lookup)
    for match in np.unique(data['match']):
        assert len(np.unique(data['split'][data['match'] == match])) == 1
    models = {mode: json.loads((directory/f'dynamics-{mode}.json').read_text()) for mode in MODES}
    assert {m['device'] for m in models.values()} == {'cuda:0', 'cuda:1', 'cuda:2', 'cuda:3'}
    assert all(0 < m['peak_allocated_bytes'] < 768*2**20 for m in models.values())
    assert len({m['features'] for m in models.values()}) == 1
    assert len({m['seed'] for m in models.values()}) == 1
    result = dict(source_sha256=digest.hexdigest(), input_unchanged=True, latest_interval_and_timestamp_checks=True,
        match_atomic_splits=True, action_rows=len(data['y']), hand_rows=len(data['hands']),
        bot_games=len(selected_pairs), window_rows=len(seen), hands_include_no_action_walks=True,
        public_chip_totals_reconcile=True, all_four_training_gpus_verified=True,
        peak_allocated_bytes={mode: m['peak_allocated_bytes'] for mode, m in models.items()},
        limitation='Source and accounting checks do not establish causal mechanisms or identify deployed source versions.')
    (directory/'dynamics-verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    verify(parser.parse_args().directory)
