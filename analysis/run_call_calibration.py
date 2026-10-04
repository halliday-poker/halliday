"""Refit current opponents and compare call corrections on paired duplicate deals."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.freeze_snapshot import baseline, freeze


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def environment():
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    # Some managed worktrees have mapped ownership. Scope trust to this tree.
    count = int(env.get('GIT_CONFIG_COUNT', '0'))
    env.update(GIT_CONFIG_COUNT=str(count + 1))
    env[f'GIT_CONFIG_KEY_{count}'] = 'safe.directory'
    env[f'GIT_CONFIG_VALUE_{count}'] = str(ROOT)
    return env


def command(run, name, args):
    started = time.monotonic()
    print(name + ': started', flush=True)
    with (run / (name + '.log')).open('w') as out:
        result = subprocess.run([sys.executable, '-B', '-u', *map(str, args)], cwd=ROOT,
                                env=environment(), stdout=out, stderr=subprocess.STDOUT)
    dump(run / (name + '-execution.json'), dict(exit_code=result.returncode,
        wall_seconds=time.monotonic() - started, command=[sys.executable, '-B', '-u', *map(str, args)]))
    if result.returncode:
        raise RuntimeError(f'{name} failed ({result.returncode}); see {run / (name + ".log")}')
    print(name + ': complete', flush=True)
    return (run / (name + '.log')).read_text()


def fit(run, source):
    if any((run/'simulate-traces').glob('*.json.gz')):
        raise ValueError('Simulation traces already exist; refitting requires a fresh study and catalogue')
    frozen = ROOT / 'analysis/results/refresh'
    if not (frozen / 'snapshot-manifest.json').exists():
        freeze(source, frozen, recover_state=True)
    target = run / 'fit'
    for name, args in [
        ('prepare', ['-m', 'opponent_model.runtime_patterns', 'prepare', '--source-directory', frozen, '--directory', target]),
        ('train', ['-m', 'opponent_model.within_game', 'train', '--directory', target, '--devices', '0,1,2,3', '--epochs', '100']),
        ('select', ['-m', 'opponent_model.runtime_patterns', 'select', '--directory', target]),
        ('refit', ['-m', 'opponent_model.runtime_patterns', 'refit', '--directory', target]),
        ('build', ['sparring/competitors/build.py', target/'runtime-fit.json', '--runtime-patterns',
                   '--destination', 'sparring/competitors/from_data_patterns'])]:
        command(run, name, args)


def freeze_variants(run, ref):
    if (run/'baseline-manifest.json').exists():
        raise ValueError('Variants already frozen; reuse them or choose a fresh study')
    os.environ.update({k: v for k, v in environment().items() if k.startswith('GIT_CONFIG_')})
    commit = subprocess.check_output(['git', 'rev-parse', ref], cwd=ROOT, env=environment(), text=True).strip()
    path = ROOT/f'snapshots/main_{commit[:7]}_call_study'
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary)/'main'
        record = baseline(ref, source)
        shutil.copyfile(ROOT/'bot/engine.py', source/'engine.py')
        if path.exists():
            for name in record['files']:
                assert (path/name).read_bytes() == (source/name).read_bytes(), name
        else:
            shutil.copytree(source, path)
    record['baseline'] = str(path.relative_to(ROOT))
    record['runtime_files'] = {name: sha256((path/name).read_bytes()).hexdigest() for name in record['files']}
    record['scope'] = 'Exact main strategy/parameters with the same optional GPU batching hook as the candidate.'
    dump(run/'baseline-manifest.json', record)
    dump(run/'fit/baseline-manifest.json', record)
    variants = [record['baseline']]
    for name, extra in [('core', ''), ('river', '\n# Predeclared pilot: four percentage points more river call margin.\n'
                        'DEFAULT_PARAMS = MappingProxyType(dict(DEFAULT_PARAMS, range_call_margin_river=0.06))\n')]:
        target = ROOT/('snapshots/call_calibration_' + name)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)/'candidate'
            shutil.copytree(ROOT/'bot', source, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            # The committed bot contains the selected pilot override. Strip
            # only our generated suffix to reconstruct both original variants.
            params = (source/'params.py').read_text().split('\n# Predeclared pilot:')[0]
            (source/'params.py').write_text(params + extra)
            if target.exists():
                for file in source.rglob('*'):
                    if file.is_file():
                        assert (target/file.relative_to(source)).read_bytes() == file.read_bytes(), file.name
            else:
                shutil.copytree(source, target)
        variants.append(str(target.relative_to(ROOT)))
    dump(run/'study-plan.json', dict(baseline=record['main_commit'], variants=variants,
        pilot_games_per_variant=500, final_games_per_variant=10000,
        pilot_seed='call-calibration-pilot-20261004', final_seed='call-calibration-confirm-20261004',
        selection='Choose river only if its paired pilot chip mean exceeds core; otherwise core. Final seed is held out.',
        interpretation='Learned newest-upload replicas; table-cluster paired intervals; timed sampling is hardware-dependent.',
        pool='sparring/competitors/from_data_patterns/latest-pool.txt'))


def evaluate(run, name, variants, games, seed, device, workers=12, traces=False):
    args = ['harness/eval.py', 'run', *variants, '--no-league', '--no-extend', '--games', str(games),
        '--deals', '100', '--sizes', '4,5,5,6', '--seed', seed, '--pool',
        'sparring/competitors/from_data_patterns/latest-pool.txt', '--device', device,
        '--workers', str(workers), '--gpu-devices', '0,1,2,3', '--gpu-workers', str(workers)]
    if traces: args += ['--trace-dir', str(run/(name+'-traces')), '--resume']
    output = command(run, name, args)
    match = re.search(r'Results: (.+?), appended', output)
    if not match: raise ValueError('Missing harness output path')
    shutil.copyfile(ROOT/match[1], run/(name+'.json'))
    report = json.loads((run/(name+'.json')).read_text())
    assert len(report['games']) == games*len(variants)
    assert all(all(v == 'OK' for v in g['verdicts']) and not any(g['errors']) for g in report['games'])
    return report


def choose_backend(run):
    timing = {};mean_game_seconds = {};projected = {}
    for device in ('cpu', 'cuda'):
        timing[device] = json.loads((run/('benchmark-'+device+'-execution.json')).read_text())['wall_seconds']
        games = json.loads((run/('benchmark-'+device+'.json')).read_text())['games']
        work = sum(g['wall_s'] for g in games)/12
        mean_game_seconds[device] = sum(g['wall_s'] for g in games)/len(games)
        projected[device] = max(0, timing[device]-work) + work*20000/len(games)
    result = dict(timing=timing, mean_game_seconds=mean_game_seconds,
        projected_20000_game_seconds=projected, device=min(projected, key=projected.get), workers=12,
        selection='Amortize measured per-game worker time over 20,000 executions, retaining observed startup/tail overhead. Projection is approximate.')
    dump(run/'backend-selection.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, choices=['fit', 'freeze', 'verify', 'tests', 'benchmark', 'pilot', 'simulate', 'cpu-check', 'audit', 'report'])
    parser.add_argument('--directory', type=Path, default=Path('analysis/results/call-calibration-20261004-r2'))
    parser.add_argument('--source', type=Path, default=Path('analysis/results/input-snapshot'))
    parser.add_argument('--baseline-ref', default='6cfdf0f44b332933d88d440791e7151028061849')
    args = parser.parse_args();run = args.directory.resolve();run.mkdir(parents=True, exist_ok=True)
    if args.stage == 'fit': fit(run, args.source)
    elif args.stage == 'freeze': freeze_variants(run, args.baseline_ref)
    elif args.stage == 'verify': command(run, 'verify', ['analysis/verify_runtime_patterns.py', '--directory', run/'fit'])
    elif args.stage == 'tests': command(run, 'tests', ['-m', 'unittest', 'discover', '-s', 'tests'])
    else:
        plan = json.loads((run/'study-plan.json').read_text())
        if args.stage == 'benchmark':
            for device in ('cpu', 'cuda'):
                evaluate(run, 'benchmark-'+device, plan['variants'][:1], 120,
                         'call-calibration-backend-20261004', device)
            choose_backend(run)
        elif args.stage == 'pilot':
            backend = json.loads((run/'backend-selection.json').read_text())
            evaluate(run, 'pilot', plan['variants'], 500, plan['pilot_seed'], backend['device'])
        elif args.stage == 'simulate':
            pilot = json.loads((run/'pilot.json').read_text())
            scores = {str(i): sum(g['chips'][0] for g in pilot['games'] if g['cand_idx'] == i) for i in range(3)}
            chosen = 2 if scores['2'] > scores['1'] else 1
            backend = choose_backend(run)
            selection = dict(pilot_chips=scores, chosen_index=chosen, selected=plan['variants'][chosen],
                rule=plan['selection'], final_seed=plan['final_seed'])
            if (run/'candidate-selection.json').exists():
                assert json.loads((run/'candidate-selection.json').read_text()) == selection
            dump(run/'candidate-selection.json', selection)
            for path in (ROOT/selection['selected']).glob('*.py'):
                shutil.copyfile(path, ROOT/'bot'/path.name)
            if chosen == 2:
                command(run, 'selected-tests', ['-m', 'unittest', 'discover', '-s', 'tests'])
            evaluate(run, 'simulate', [plan['variants'][0], plan['variants'][chosen]], 10000,
                     plan['final_seed'], backend['device'], traces=True)
        elif args.stage == 'cpu-check':
            evaluate(run, 'cpu-check', ['bot'], 120, 'call-calibration-cpu-check-20261004', 'cpu')
        elif args.stage == 'audit':
            report = json.loads((run/'simulate.json').read_text())
            if report['compute']['device'] == 'cuda' and not (run/'cpu-check.json').exists():
                evaluate(run, 'cpu-check', ['bot'], 120, 'call-calibration-cpu-check-20261004', 'cpu')
            dump(run/'simulation-plan.json', dict(games=len(report['games']), games_per_variant=10000))
            command(run, 'audit', ['analysis/audit_pattern_simulation.py', '--directory', run,
                '--trace-subdir', 'simulate-traces', '--devices', '0,1,2,3', '--workers', '12'])
        elif args.stage == 'report':
            command(run, 'report', ['analysis/report_call_calibration.py', '--directory', run])


if __name__ == '__main__': main()
