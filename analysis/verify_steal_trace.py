"""Verify the added-open diagnostic and export compact evidence from its trace."""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness import eval as harness


def verify(source):
    raw = source.read_bytes()
    data = json.loads(raw)
    args = data['args']
    pool = harness.read_pool(ROOT/'sparring/competitors/from_data/pool.txt', [])
    tables = harness.draw_tables(pool, args['tables'], [4, 5, 5, 6], args['seed'])
    expected = {(t, r) for t, table in enumerate(tables) for r in range(len(table)+1)}
    actual = [(g['table'], g['game']) for g in data['games']]
    assert len(actual) == len(set(actual)) and set(actual) == expected
    counts = np.zeros((len(tables), 2))
    categories = defaultdict(lambda: dict(hands=0, margin=0))
    compute = defaultdict(lambda: dict(games=0, batches=0, ranked_hands=0))
    for game in data['games']:
        assert sum(game['chips']) == 0
        assert all(v == 'OK' for v in game['verdicts']) and not any(game['errors'])
        marks = game['marks']
        assert len({m['hand'] for m in marks}) == len(marks)
        for mark in marks:
            end = mark['events'][-1]
            assert end['type'] == 'hand_end' and end['hand'] == mark['hand']
            assert sum(end['deltas']) == 0
            assert end['deltas'][mark['seat']] == mark['chips']
            assert mark['invested'] in (0, 1)
            margin = mark['chips'] + mark['invested']
            assert margin == mark['margin_over_folding']
            flop = any(e['type'] == 'street' and e['street'] == 'flop' for e in mark['events'])
            category = ('postflop_win' if mark['chips'] > 0 else 'postflop_loss') if flop else (
                'won_preflop' if mark['chips'] > 0 else 'lost_preflop')
            assert category == mark['category'] and flop == mark['flop']
            categories[category]['hands'] += 1
            categories[category]['margin'] += margin
            counts[game['table']] += [1, margin]
        work = game['compute']
        totals = compute[work['device']]
        totals['games'] += 1
        for key in ('batches', 'ranked_hands'):
            totals[key] += work.get(key, 0)
    summary = data['summary']
    total = counts.sum(0)
    assert summary['games'] == len(actual) and summary['failures'] == 0
    assert total.tolist() == [summary['added_opens'], summary['margin_over_folding']]
    assert dict(categories) == summary['categories']
    if total[0]:
        assert summary['per_added_open'] == total[1] / total[0]
    rng = np.random.default_rng(6019)
    samples = counts[rng.integers(len(tables), size=(5000, len(tables)))].sum(1)
    samples = samples[samples[:, 0] > 0]
    if len(samples):
        interval = np.quantile(samples[:, 1] / samples[:, 0], [.025, .975])
        np.testing.assert_array_equal(interval, summary['table_bootstrap_ci95'])
    result = {key: value for key, value in data.items() if key != 'games'}
    result['compute_totals'] = dict(compute)
    result['verification'] = dict(complete_rotations=True, zero_sum=True,
        hand_end_deltas_match=True, unique_marked_hands=True, game_count=len(actual),
        bootstrap_reproduced=True, source=str(source), source_sha256=sha256(raw).hexdigest())
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path,
        default=Path('analysis/results/refresh-20261004/steals-action-trace.json'))
    parser.add_argument('--output', type=Path,
        default=Path('analysis/results/refresh-20261004/steals-action-summary.json'))
    args = parser.parse_args()
    result = verify(args.source)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result['verification'], indent=2))
