"""Reproduce a frozen opponent-model refresh with four parallel CUDA devices."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STEPS = ('baseline', 'prepare', 'train', 'compare', 'refit', 'refresh', 'build', 'select')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--start-at', choices=STEPS, default='baseline')
    parser.add_argument('--epochs', type=int, default=100)
    args = parser.parse_args()
    run = args.directory
    prefix = [sys.executable, '-B']
    commands = {
        'baseline': ['-m', 'opponent_model', '--data-dir', str(run/'source'), '--save-cache', str(run/'context-features.npz'),
                     '--output', str(run/'baseline-estimates.json'), '--devices', 'cuda:0', 'cuda:1', 'cuda:2', 'cuda:3',
                     '--bootstrap', '1000', '--permutations', '4999', '--batch-size', '128', '--memory-limit-mib', '768'],
        'prepare': ['-m', 'opponent_model.behavior', 'prepare', '--directory', str(run)],
        'train': ['-m', 'opponent_model.behavior', 'train', '--directory', str(run), '--epochs', str(args.epochs)],
        'compare': ['-m', 'opponent_model.behavior', 'compare', '--directory', str(run)],
        'refit': ['-m', 'opponent_model.behavior', 'refit', '--directory', str(run), '--devices', '0'],
        'refresh': ['-m', 'opponent_model.refresh', '--directory', str(run), '--devices', '0,1,2,3'],
        'select': ['analysis/latest_segments.py', '--directory', str(run)],
    }
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    for step in STEPS[STEPS.index(args.start_at):]:
        if step == 'build':
            mode = json.loads((run/'behavior-comparison.json').read_text())['selected']
            command = ['sparring/competitors/build.py', str(run/'opponent-estimates.json'), '--policy', str(run/f'policy-refit-{mode}.npz')]
        else:
            command = commands[step]
        print(f'{step}: {" ".join(prefix+command)}', flush=True)
        with (run/f'{step}.log').open('w') as log:
            subprocess.run(prefix+command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        print(f'{step}: complete', flush=True)


if __name__ == '__main__':
    main()
