"""Evaluate frozen main once, reusing the completed call-calibration control."""
import argparse
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.run_opponent_groups import command, dump, environment, git_snapshot
from analysis.audit_pattern_simulation import fingerprint
from analysis.halliday_report import BLUNDERS

STEM = 'main-calibration-20261004'
MAIN = 'a707565'
CATALOGUE = ROOT/'sparring/competitors/from_data_groups/bots.json'
EVIDENCE = ROOT/'analysis/reports/evidence'/STEM


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def packed(path, value):
    path.write_bytes(gzip.compress(json.dumps(value, separators=(',', ':'),
        allow_nan=False).encode(), mtime=0))


def verify_archive(run, archive, simulation):
    from harness.eval import bot_hash
    expected={s:bot_hash(s) for t in simulation['tables'] for s in t}
    for t,opponents in enumerate(simulation['tables']):
        with gzip.open(archive/'simulate-traces'/f't{t:06d}-g0-c1.json.gz','rt') as f:
            identity=json.load(f)['identity']
        assert identity['seed']==simulation['seed'] and identity['deals']==100
        assert identity['time_ms']==30000 and identity['increment_ms']==100
        assert identity['opponents']==opponents
        assert identity['harness_sha256']==digest(ROOT/'harness/eval.py')
        assert all(identity['source_hashes'][s]==expected[s] for s in opponents)
        assert identity['source_hashes'][identity['candidate']]==bot_hash(identity['candidate'])
    dump(run/'archive-verification.json',dict(tables_checked=len(simulation['tables']),
        opponents=len(expected),passed=True,
        scope='First rotation from every archived table: seed, rules, ordered opponent specs, harness and all candidate/opponent source hashes match.'))


def prepare(run, archive, ref):
    """Freeze exact Git sources and extract (never execute) the old control."""
    if (run/'study-plan.json').exists():
        return verify(run)
    os.environ.update({k:v for k,v in environment().items() if k.startswith('GIT_CONFIG_')})
    commit = subprocess.check_output(['git','rev-parse',ref], cwd=ROOT, text=True).strip()
    snapshot = ROOT/f'snapshots/main_{commit[:7]}_calibration_study'
    main = git_snapshot(commit, snapshot, gpu_hook=False)
    simulation = json.loads((archive/'simulate.json').read_text())
    audits = json.loads((archive/'audit-summary.json').read_text())
    old_plan = json.loads((archive/'study-plan.json').read_text())
    assert fingerprint(CATALOGUE) == audits['code_sha256'], 'Keep the archived public audit model unchanged'
    games = sorted((g for g in simulation['games'] if g['cand_idx']==1), key=lambda g:(g['table'],g['game']))
    summaries = [g for g in audits['games'] if g['match'].endswith('-c1')]
    assert len(games)==len(summaries)==10000
    assert sum(len(t)+1 for t in simulation['tables'])==10000
    assert all(3<=len(t)<=5 for t in simulation['tables'])
    verify_archive(run,archive,simulation)
    flags=[]
    for g in summaries:
        with gzip.open(archive/'audit'/(g['match']+'.json.gz'),'rt') as f:
            shard=json.load(f)
        assert shard['summary']==g
        flags.extend(r for r in shard['decisions'] if r['classification'] in BLUNDERS)
    packed(run/'archived-calibration.json.gz',dict(games=games,audits=summaries,flags=flags,
        code_sha256=audits['code_sha256'],seed=simulation['seed'],tables=simulation['tables'],
        args=simulation['args'],commit=old_plan['calibration_commit']))
    dump(run/'tables.json',simulation['tables'])
    dump(run/'main-manifest.json',main)
    source = {str(p.relative_to(ROOT)):digest(p) for p in (
        archive/'simulate.json',archive/'audit-summary.json',archive/'study-plan.json')}
    dependencies = dict(audits['code_sha256'])
    for p in [ROOT/'harness/eval.py',ROOT/'sparring/param.py',
              *ROOT.glob('sparring/competitors/*.py'),*ROOT.glob('vendor/macpoker-src/macpoker/*.py'),
              *(ROOT/old_plan['variants'][1]).glob('*.py'),
              *CATALOGUE.parent.glob('*.npz'),CATALOGUE.parent/'profiles.json',
              CATALOGUE.parent/'latest-pool.txt', *snapshot.glob('*.py')]:
        if p.exists():dependencies[str(p.relative_to(ROOT))]=digest(p)
    dump(run/'study-plan.json',dict(main_commit=commit,main_snapshot=str(snapshot.relative_to(ROOT)),
        calibration_commit=old_plan['calibration_commit'],archived_candidate_index=1,
        archived_directory=str(archive.relative_to(ROOT)),archived_sha256=source,
        control_pack_sha256=digest(run/'archived-calibration.json.gz'),
        tables_sha256=digest(run/'tables.json'),dependencies=dependencies,
        seed=simulation['seed'],games=10000,duplicate_tables=len(simulation['tables']),
        rules=old_plan['rules'],pool=old_plan['pool'],catalogue=str(CATALOGUE.relative_to(ROOT)),
        compute=dict(device='cpu',workers=16,audit_devices=[0,1,2,3],audit_workers=8),
        baseline_policy='Read the archived calibration results. Never simulate the control again.',
        backend_reason='Prior matched backend benchmark favored CPU16 on shared V100s; exact main has no batched CUDA hook. Audit uses all four V100s.',
        opponent_policy='Reuse the same 69 newest-version replicas and discounted sparse priors as the archived control; do not refit for this paired comparison.'))
    dump(run/'simulation-plan.json',dict(games=10000,variants=1,deals=100))
    return verify(run)


def verify(run):
    plan=json.loads((run/'study-plan.json').read_text())
    for relative,expected in plan['dependencies'].items():
        assert digest(ROOT/relative)==expected, f'Frozen dependency changed: {relative}'
    assert digest(run/'tables.json')==plan['tables_sha256']
    assert digest(run/'archived-calibration.json.gz')==plan['control_pack_sha256']
    return plan


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',required=True,choices=('prepare','restore','verify','resources','simulate','audit','tactics','cases','report'))
    p.add_argument('--directory',type=Path,default=ROOT/'analysis/results'/STEM)
    p.add_argument('--archive',type=Path,default=ROOT/'analysis/results/opponent-groups-20261004')
    p.add_argument('--main-ref',default=MAIN)
    args=p.parse_args();run=args.directory.resolve();run.mkdir(parents=True,exist_ok=True)
    if args.stage=='restore':
        for name in ('study-plan.json','main-manifest.json','simulation-plan.json','tables.json','archived-calibration.json.gz'):
            if (run/name).exists():
                assert (run/name).read_bytes()==(EVIDENCE/name).read_bytes(),f'Refusing to overwrite {name}'
            else:shutil.copyfile(EVIDENCE/name,run/name)
        verify(run);return
    if args.stage=='prepare':prepare(run,args.archive.resolve(),args.main_ref);return
    plan=verify(run)
    if args.stage=='verify':return
    if args.stage=='resources':
        command(run,'resources',['harness/resource_check.py',plan['main_snapshot'],'--repeats','2','--output',run/'resources.json'])
    elif args.stage=='simulate':
        if (run/'simulate.json').exists():
            result=json.loads((run/'simulate.json').read_text())
            assert len(result['games'])==10000 and result['args']['bots']==[plan['main_snapshot']]
            print('Completed main result exists; preserving it.');return
        log=command(run,'simulate',['harness/eval.py','run',plan['main_snapshot'],'--no-league','--no-extend',
            '--deals','100','--time-ms','30000','--increment-ms','100','--seed',plan['seed'],
            '--tables-json',run/'tables.json','--pool',plan['pool'],'--device','cpu','--workers','16',
            '--trace-dir',run/'traces','--resume','--label',STEM])
        matches=re.findall(r'Results: ([^,\n]+)',log)
        assert len(matches)==1
        shutil.copyfile(ROOT/matches[0],run/'simulate.json')
        result=json.loads((run/'simulate.json').read_text())
        assert len(result['games'])==10000 and result['tables']==json.loads((run/'tables.json').read_text())
        assert {g['cand_idx'] for g in result['games']}=={0}
    elif args.stage=='audit':
        command(run,'audit',['analysis/audit_pattern_simulation.py','--directory',run,
            '--trace-subdir','traces','--catalogue',plan['catalogue'],'--devices','0,1,2,3','--workers','8'])
    elif args.stage=='tactics':
        command(run,'tactics',['analysis/review_main_tactics.py','--directory',run])
    elif args.stage=='cases':
        command(run,'cases',['analysis/review_main_tactics.py','--directory',run,'--cases'])
    elif args.stage=='report':
        command(run,'report',['analysis/report_main_calibration.py','--directory',run])


if __name__=='__main__':main()
