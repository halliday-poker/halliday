"""Compare exact main and the Halliday replica on strictly latest observed tables."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.summarize_benchmarks import summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=12)
    parser.add_argument('--seed', default='latest-main-r2-20261004-matched')
    args = parser.parse_args()
    run = args.directory
    baseline = json.loads((run/'baseline-manifest.json').read_text())
    profiles = json.loads((ROOT/'sparring/competitors/from_data/profiles.json').read_text())['profiles']
    replica = 'sparring/competitors/from_data/'+profiles['Halliday']['file']
    tables = run/'latest-matched-tables.json'
    plan = dict(seed=args.seed, baseline=baseline, replica=replica, tables_sha256=sha256(tables.read_bytes()).hexdigest(),
                purpose='Descriptive fidelity on newest-interval observed compositions, with fresh duplicate decks; not original-deck replay, held-out model validation or proof of a source version.')
    (run/'fidelity-plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    command = [sys.executable, '-B', '-u', 'harness/eval.py', 'run', baseline['baseline'], replica,
               '--tables-json', str(tables), '--pool', str(run/'latest-field-pool.txt'), '--no-league', '--no-extend',
               '--seed', args.seed, '--workers', str(args.workers), '--device', 'auto',
               '--gpu-devices', '0,1,2,3', '--gpu-workers', str(args.workers),
               '--label', 'Exact main and newest Halliday replica on all-seats-latest observed lineups']
    with (run/'fidelity.log').open('w') as log:
        subprocess.run(command, cwd=ROOT, env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1'),
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    match = re.search(r'Results: (.+?), appended', (run/'fidelity.log').read_text())
    if not match:
        raise ValueError('Missing harness result')
    source = ROOT/match.group(1)
    summary = summarize([source], plan['purpose'])
    games = json.loads(source.read_text())['games']
    for index, candidate in enumerate(summary['summary']):
        rows = [g for g in games if g['cand_idx'] == index]
        hands = len(rows) * 100
        candidate['behavior'] = dict(hands=hands,
            fold_rate=sum(sum(v.get('fold', 0) for v in g['behavior'][0]['actions'].values()) for g in rows)/hands,
            vpip=sum(g['behavior'][0]['vpip_hands'] for g in rows)/hands,
            pfr=sum(g['behavior'][0]['pfr_hands'] for g in rows)/hands)
    (run/'fidelity-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary['summary'], indent=2))


if __name__ == '__main__':
    main()
