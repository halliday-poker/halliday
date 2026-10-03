"""Evaluate exact current main against only the recorded newest opponent field."""
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
from harness.eval import bot_hash
from analysis.summarize_benchmarks import summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--tables', type=int, default=400)
    parser.add_argument('--events', type=int, default=10)
    parser.add_argument('--workers', type=int, default=16)
    parser.add_argument('--seed', default='latest-main-r2-20261004')
    args = parser.parse_args()
    run = args.directory
    baseline = json.loads((run/'baseline-manifest.json').read_text())
    selection = json.loads((run/'latest-selection.json').read_text())
    for relative, digest in baseline['files'].items():
        assert sha256((ROOT/baseline['baseline']/relative).read_bytes()).hexdigest() == digest
    pool = run/'latest-field-pool.txt'
    plan = dict(baseline=baseline, bot_hash=bot_hash(baseline['baseline']), tables=args.tables, events=args.events,
                seed=args.seed, hands_per_game=100, table_sizes=[4, 5, 5, 6],
                opponent_identities=selection['included_opponents'], pool_sha256=sha256(pool.read_bytes()).hexdigest(),
                purpose='Describe exact main against the refreshed newest observed field; no candidate tuning or promotion.',
                compute='Auto selects CUDA only for compatible bot engines; unmodified current main may require CPU simulation. Model fitting and replay audit use four V100s.')
    (run/'benchmark-plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    prefix = [sys.executable, '-B', '-u']
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    compute = ['--device', 'auto', '--workers', str(args.workers), '--gpu-workers', str(args.workers), '--gpu-devices', '0,1,2,3']
    commands = {
        'field': ['harness/eval.py', 'run', baseline['baseline'], '--pool', str(pool), '--no-league', '--no-extend',
                  '--tables', str(args.tables), '--deals', '100', '--seed', args.seed,
                  '--label', 'Exact origin/main versus newest observed ladder intervals'] + compute,
        'tournament': ['harness/tournament.py', baseline['baseline'], '--pool', str(pool), '--repeats', str(args.events),
                       '--rounds', '4', '--deals', '100', '--seed', args.seed+'-tournament', '--output', str(run/'tournament.json')] + compute,
        'verify-tournament': ['analysis/verify_tournament.py', str(run/'tournament.json'), '--output', str(run/'tournament-verification.json')],
    }
    for step, command in commands.items():
        print(f'{step}: {" ".join(prefix+command)}', flush=True)
        with (run/f'{step}.log').open('w') as log:
            subprocess.run(prefix+command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        if step == 'field':
            output = re.search(r'Results: (.+?), appended', (run/'field.log').read_text())
            if not output:
                raise ValueError('Harness did not record an output artifact')
            summary = summarize([ROOT/output.group(1)], plan['purpose'])
            summary['baseline_commit'] = baseline['main_commit']
            (run/'field-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
        print(f'{step}: complete', flush=True)


if __name__ == '__main__':
    main()
