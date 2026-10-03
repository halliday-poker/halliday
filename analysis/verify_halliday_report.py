"""Check report accounting, input immutability, and public-information isolation."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from queue import Queue
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import halliday_performance as performance
from analysis.halliday_report import BLUNDERS, DIR


def fingerprint(path):
    digest = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify(directory, device):
    def read(name):
        return json.loads((directory/name).read_text())
    extraction, audit = read('extraction.json'), read('reconstruction-audit.json')
    rows, hands, matches = read('classified-actions.json'), read('classified-hands.json'), read('match-reviews.json')
    summary, gpu = read('summary.json'), read('gpu-work.json')
    assert fingerprint(Path(extraction['source'])) == extraction['sha256'], 'source changed'
    assert fingerprint(directory/'matches-snapshot.json') == extraction['matches_sha256']
    assert fingerprint(directory/'state-snapshot.json') == extraction['state_sha256']
    assert not audit['errors'] and all(m['matches'] and m['contiguous'] for m in audit['matches'])
    assert len(rows) == audit['actions'] == len({r['id'] for r in rows})
    assert len(hands) == audit['hands'] == len({(h['match'],h['hand']) for h in hands})
    assert len(matches) == extraction['target_matches'] == len(audit['matches'])
    assert Counter(r['action'] for r in rows) == audit['action_counts']
    by_match, hand_map = defaultdict(list), {(h['match'],h['hand']):h for h in hands}
    for hand in hands:
        by_match[hand['match']].append(hand)
    for match in matches:
        group = by_match[match['match']]
        assert sum(h['chips'] for h in group) == match['chips']
        assert sum(v['chips'] for v in match['loss_categories'].values()) == match['chips']
        assert sum(v['hands'] for v in match['loss_categories'].values()) == match['hands']
    for row in rows:
        log = hand_map[(row['match'],row['hand'])]['log']
        assert row['history'] == log[:row['action_index']-1], 'future action leaked into history'
        if row['classification'] == 'probable_bad_terminal_call':
            assert row['action']=='call' and row['terminal_call'] and row['public_ev_upper'] < -2
        if row['classification'] == 'probable_missed_terminal_call':
            assert row['action']=='fold' and row['terminal_call'] and row['public_ev_lower'] > 2
    bad_calls = [r for r in rows if r['classification']=='probable_bad_terminal_call']
    assert len(bad_calls) == len({(r['match'],r['hand']) for r in bad_calls}), 'call savings double counted'
    ladder_ids = {m['match'] for m in matches if m['kind']=='ladder'}
    assert summary['chips'] == sum(h['chips'] for h in hands if h['match'] in ladder_ids)
    assert summary['negative_match_net'] == sum(v['chips'] for v in summary['losses_in_negative_matches'].values())
    assert sum(summary['classifications'].values()) == summary['actions']
    assert summary['folds'] == sum(r['action']=='fold' for r in rows if r['match'] in ladder_ids)
    assert all(x['ranked_hands']>0 for x in gpu)

    # Cover each street, terminal/nonterminal decisions, multiway pots and the
    # historical shover exception. Regenerate both sensitivity models after
    # removing every non-public field, using only an explicit allowlist.
    groups = {}
    for row in rows:
        if row['public']:
            key = (row['street'],row['terminal_call'],len(row['opponents'])>1,bool(row['known_shovers']))
            groups.setdefault(key, row)
    queue = Queue()
    queue.put(device)
    performance.worker_init(queue)
    assert not performance._INIT_ERROR, performance._INIT_ERROR
    allowed = {'id','hole','board','opponents','history','known_shovers','n','live','seat','terminal_call'}
    checked = []
    try:
        for row in groups.values():
            public_only = {key:row[key] for key in allowed}
            for model in ('tight','loose'):
                full = performance.public_ranks(row, model)
                redacted = performance.public_ranks(public_only, model)
                np.testing.assert_array_equal(full,redacted)
                estimate = performance.payoff_summary(full,row)
                for key in ('equity','call_ev','ev_se'):
                    assert estimate[key] == row['public'][model][key], 'scored estimate differs from rerun'
            checked.append(row['id'])
    finally:
        performance._GPU.close()

    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_halliday_performance.py')
    with (directory/'tests.log').open('w') as stream:
        result = unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    assert result.wasSuccessful(), 'audit tests failed; see tests.log'
    files = ['analysis/halliday_performance.py','analysis/halliday_report.py',
             'analysis/render_halliday_report.py','analysis/verify_halliday_report.py',
             'bot/ranges.py','bot/engine.py','bot/params.py','harness/gpu_rank.cu',
             'tests/test_halliday_performance.py']
    verified = dict(source_sha256=extraction['sha256'],actions=len(rows),hands=len(hands),matches=len(matches),
                    input_unchanged=True,accounting_reconciled=True,public_contexts_rechecked=checked,
                    audit_tests_passed=result.testsRun,devices=sorted({x['device'] for x in gpu}),
                    code_sha256={name:fingerprint(ROOT/name) for name in files})
    verified['description'] = (
        f"{result.testsRun} audit tests passed. All {len(rows):,} action IDs and {len(hands):,} hand IDs are unique, "
        f"all {len(matches)} match totals and exclusive loss buckets reconcile, and prior histories contain no future actions. "
        f"Both public-range models were reproduced exactly in {len(checked)} representative contexts after removing every field "
        "outside the explicit public-information allowlist. The source SHA-256 was unchanged after computation. "
        "Source-code fingerprints, tested context IDs and test output are retained alongside this report."
    )
    (directory/'verification.json').write_text(json.dumps(verified,indent=2))
    print(json.dumps(verified,indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,default=DIR)
    parser.add_argument('--gpu-device',type=int,default=0)
    args=parser.parse_args()
    verify(args.directory,args.gpu_device)
