"""Reproduce the opponent-group experiment with a frozen input and main baseline."""
import argparse
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import runpy
from pprint import pformat
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.freeze_snapshot import baseline, freeze


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def environment():
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    count = int(env.get('GIT_CONFIG_COUNT', '0'))
    env.update(GIT_CONFIG_COUNT=str(count + 1))
    env[f'GIT_CONFIG_KEY_{count}'] = 'safe.directory'
    env[f'GIT_CONFIG_VALUE_{count}'] = str(ROOT)
    env.setdefault('OPPONENT_CUDA_MEMORY_MIB', '512')
    return env


def command(run, name, args):
    started = time.monotonic()
    print(name + ': started', flush=True)
    argv = [sys.executable, '-B', '-u', *map(str, args)]
    with (run/(name + '.log')).open('w') as out:
        result = subprocess.run(argv, cwd=ROOT, env=environment(), stdout=out, stderr=subprocess.STDOUT)
    dump(run/(name + '-execution.json'), dict(exit_code=result.returncode,
         wall_seconds=time.monotonic()-started, command=argv))
    if result.returncode:
        raise RuntimeError(f'{name} failed; see {run/(name + ".log")}')
    print(name + ': complete', flush=True)
    return (run/(name+'.log')).read_text()


def install_snapshot(source,destination):
    if destination.exists():
        expected={p.name:p.read_bytes() for p in source.glob('*.py')}
        actual={p.name:p.read_bytes() for p in destination.glob('*.py')}
        if expected!=actual:
            raise ValueError(f'{destination}: existing frozen source differs; use an isolated checkout and fresh study name')
    else:
        shutil.copytree(source,destination)


def git_snapshot(ref,destination,gpu_hook=False):
    with tempfile.TemporaryDirectory() as temporary:
        source=Path(temporary)/'source'
        record=baseline(ref,source)
        if gpu_hook:shutil.copyfile(ROOT/'bot/engine.py',source/'engine.py')
        install_snapshot(source,destination)
        record['files']={k:v for k,v in record['files'].items() if '__pycache__' not in Path(k).parts and not k.endswith('.pyc')}
        record['runtime_files']={k:sha256((source/k).read_bytes()).hexdigest() for k in record['files']}
    record['baseline']=str(destination.relative_to(ROOT))
    return record


def freeze_variants(run):
    if (run/'study-plan.json').exists():
        raise ValueError('Variants already frozen; reuse the recorded study or start another directory.')
    os.environ.update({k:v for k,v in environment().items() if k.startswith('GIT_CONFIG_')})
    main=json.loads((run/'baseline-manifest.json').read_text())
    ref=subprocess.check_output(['git','rev-parse','origin/feat/call-calibration'],cwd=ROOT,text=True).strip()
    calibration=ROOT/f'snapshots/call_calibration_{ref[:7]}_group_study'
    record=git_snapshot(ref,calibration)
    dump(run/'calibration-manifest.json',record)
    variants=[main['baseline'],record['baseline']]
    for suffix,override in [('full',{}),('half',{'group_strength':.5}),('ranges',{'group_counters':False,'group_mix':0.0})]:
        prefix='opponent_groups' if run.name=='opponent-groups-20261004' else run.name.replace('-','_')
        target=ROOT/f'snapshots/{prefix}_{suffix}'
        with tempfile.TemporaryDirectory() as temporary:
            source=Path(temporary)/'source'
            shutil.copytree(ROOT/'bot',source,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            text=(source/'params.py').read_text().split('\n# Main-based grouping:')[0].split('\n# Selected opponent-group pilot')[0]
            if override:text+='\n# Selected opponent-group pilot variant.\nDEFAULT_PARAMS = MappingProxyType(dict(DEFAULT_PARAMS, **'+repr(override)+'))\n'
            (source/'params.py').write_text(text)
            fit=json.loads((run/'groups-fit.json').read_text())
            priors=[{k:v for k,v in group.items() if k not in ('members','style','parameter_variance','counter_reliability')}
                    for group in fit['groups']]
            header=(source/'group_priors.py').read_text().split('GROUPS = ')[0]
            (source/'group_priors.py').write_text(header+'GROUPS = '+pformat(priors,width=105,sort_dicts=False)+'\n')
            install_snapshot(source,target)
        variants.append(str(target.relative_to(ROOT)))
    manifest={v:{str(p.relative_to(ROOT/v)):sha256(p.read_bytes()).hexdigest() for p in (ROOT/v).glob('*.py')} for v in variants}
    dump(run/'variants-manifest.json',manifest)
    dump(run/'study-plan.json',dict(main_commit=main['main_commit'],calibration_commit=ref,
        variants=variants,pilot_games_per_variant=600,final_games_per_variant=10000,
        pilot_seed='opponent-groups-pilot-20261004',final_seed='opponent-groups-confirm-20261004',
        selection='Choose full or half group strength by higher total paired pilot chips; full wins ties. Range-only is an ablation, not an eligible replacement for group counters.',
        primary_comparison='Grouping versus call calibration; main is the original control.',
        pool='sparring/competitors/from_data_groups/latest-pool.txt',
        rules=dict(deals=100,sizes=[4,5,5,6],stack=200,blinds=[1,2],bank_ms=30000,increment_ms=100)))


def extend_comparison(run):
    """Add main + grouping without rerunning or changing the original controls."""
    plan=json.loads((run/'study-plan.json').read_text())
    if not (run/'candidate-selection.json').exists():
        pilot=json.loads((run/'pilot.json').read_text())
        chips={str(c):sum(g['chips'][0] for g in pilot['games'] if g['cand_idx']==c) for c in range(5)}
        chosen=2 if chips['2']>=chips['3'] else 3
        dump(run/'candidate-selection.json',dict(chosen_index=chosen,selected=plan['variants'][chosen],
             pilot_chips=chips,rule=plan['selection']))
    selected=json.loads((run/'candidate-selection.json').read_text())['selected']
    destination=ROOT/(selected.rsplit('_',1)[0]+'_main')
    with tempfile.TemporaryDirectory() as temporary:
        source=Path(temporary)/'source'
        shutil.copytree(ROOT/selected,source,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        main=runpy.run_path(str(ROOT/plan['variants'][0]/'params.py'))['DEFAULT_PARAMS']
        calibrated=runpy.run_path(str(source/'params.py'))['DEFAULT_PARAMS']
        delta=main['range_call_margin_river']-calibrated['range_call_margin_river']
        with (source/'params.py').open('a') as f:
            f.write('\n# Main-based grouping: preserve main\'s call behavior.\n'
                    'DEFAULT_PARAMS = MappingProxyType(dict(DEFAULT_PARAMS, terminal_range_calls=False, '
                    'partial_terminal_equity=False, range_call_margin_river='+repr(main['range_call_margin_river'])+'))\n')
        data=runpy.run_path(str(source/'group_priors.py'))
        for group in data['GROUPS']:group['counter']['range_call_margin_river']+=delta
        header=(source/'group_priors.py').read_text().split('GROUPS = ')[0]
        (source/'group_priors.py').write_text(header+'GROUPS = '+pformat(data['GROUPS'],width=105,sort_dicts=False)+'\n')
        install_snapshot(source,destination)
    record=dict(variants=[*plan['variants'][:2],selected,str(destination.relative_to(ROOT))],
        games_per_variant=10000,total_games=40000,seed=plan['final_seed'],
        reason='User requested grouping on both main and call-calibration bases; same fitted groups, strength, counters and private sizing mixture.',
        selection='Use the already selected grouping strength on both bases; no tuning against final results.',
        main_group_changes=dict(terminal_range_calls=False,partial_terminal_equity=False,
                               range_call_margin_river=main['range_call_margin_river'],counter_river_offset=delta),
        comparisons=['groups+calibration minus calibration','groups+main minus main','groups+calibration minus groups+main'],
        files={p.name:sha256(p.read_bytes()).hexdigest() for p in destination.glob('*.py')})
    if (run/'study-extension.json').exists():assert json.loads((run/'study-extension.json').read_text())==record
    dump(run/'study-extension.json',record)
    return record


def evaluate(run,name,variants,games,seed,device,workers,traces=False):
    args=['harness/eval.py','run',*variants,'--no-league','--no-extend','--games',games,'--deals',100,
          '--sizes','4,5,5,6','--seed',seed,'--pool','sparring/competitors/from_data_groups/latest-pool.txt',
          '--device',device,'--workers',workers,'--gpu-devices','0,1,2,3','--gpu-workers',workers]
    if traces:args+=['--trace-dir',run/(name+'-traces'),'--resume']
    output=command(run,name,args)
    path=re.search(r'Results: (.+?), appended',output)
    if not path:raise ValueError('Missing harness result path')
    shutil.copyfile(ROOT/path[1],run/(name+'.json'))
    result=json.loads((run/(name+'.json')).read_text())
    assert len(result['games'])==games*len(variants)
    assert all(all(v=='OK' for v in g['verdicts']) and not any(g['errors']) and sum(g['chips'])==0 for g in result['games'])
    return result


def integration(run):
    extension=extend_comparison(run)
    evaluate(run,'integration-four',extension['variants'][2:],24,'opponent-groups-integration-20261004','cpu',8,traces=True)
    counts={str(c):dict(games=0,decisions=0,opponent_classifications=0,weighted_counter_reads=0) for c in (0,1)}
    for path in (run/'integration-four-traces').glob('*.json.gz'):
        with gzip.open(path,'rt') as f:trace=json.load(f)
        c=str(trace['result']['cand_idx']);s=counts[c];s['games']+=1
        for d in trace['decisions']:
            assert d.get('groups_available') is True
            s['decisions']+=1;s['opponent_classifications']+=len(d['groups'])
            s['weighted_counter_reads']+=sum(v['weight']>0 for v in d['groups'].values())
    assert all(s['games']==24 and s['weighted_counter_reads']>0 for s in counts.values())
    dump(run/'group-integration-verification.json',dict(passed=True,variants=extension['variants'][2:],counts=counts))


def benchmark(run,plan):
    measurements={}
    for label,device,workers in [('cpu','cpu',12),('cuda','cuda',8),('cpu-16','cpu',16),('cuda-12','cuda',12)]:
        if (run/('benchmark-'+label+'.json')).exists():
            result=json.loads((run/('benchmark-'+label+'.json')).read_text())
        else:
            result=evaluate(run,'benchmark-'+label,plan['variants'][:3],120,
                            'opponent-groups-backend-20261004',device,workers)
        elapsed=json.loads((run/('benchmark-'+label+'-execution.json')).read_text())['wall_seconds']
        work=sum(g['wall_s'] for g in result['games'])/workers
        projected=max(0,elapsed-work)+work*30000/len(result['games'])
        measurements[label]=dict(device=device,workers=workers,wall_seconds=elapsed,projected_seconds=projected,
            mean_game_seconds=sum(g['wall_s'] for g in result['games'])/len(result['games']))
    chosen=min(measurements,key=lambda k:measurements[k]['projected_seconds'])
    dump(run/'backend-selection.json',dict(device=measurements[chosen]['device'],workers=measurements[chosen]['workers'],measurements=measurements,
        scope='Amortize measured worker time and startup/tail over 30,000 executions; projection, not a measured full-study speedup. CPU checks 12/16 workers; CUDA checks two/three workers per GPU with roughly 1 GiB available per device.'))


def freeze_inputs(run, source, ref):
    frozen = run/'input'
    if not (frozen/'snapshot-manifest.json').exists():
        freeze(source, frozen, recover_state=True)
    if not (run/'baseline-manifest.json').exists():
        os.environ.update({k:v for k,v in environment().items() if k.startswith('GIT_CONFIG_')})
        commit = subprocess.check_output(['git','rev-parse',ref],cwd=ROOT,text=True).strip()
        destination = ROOT/f'snapshots/main_{commit[:7]}_opponent_groups'
        record = git_snapshot(commit,destination,gpu_hook=True)
        record['scope'] = 'Exact main strategy with the shared optional offline GPU batch hook.'
        dump(run/'baseline-manifest.json',record)
    return frozen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, choices=['freeze','refit','prepare','train','select','refit-models','build','verify',
        'groups','snapshots','tests','smoke','resources','benchmark','pilot','simulate','extend','integration','simulate-four','cpu-check','audit','report'])
    parser.add_argument('--directory',type=Path,default=Path('analysis/results/opponent-groups-20261004'))
    parser.add_argument('--source',type=Path,default=Path('analysis/results/input-snapshot'))
    parser.add_argument('--baseline-ref',default='6cfdf0f44b332933d88d440791e7151028061849')
    args=parser.parse_args(); run=args.directory.resolve(); run.mkdir(parents=True,exist_ok=True)
    frozen=freeze_inputs(run,args.source.resolve(),args.baseline_ref)
    if args.stage=='freeze': return
    target=run/'fit'; target.mkdir(exist_ok=True)
    shutil.copyfile(run/'baseline-manifest.json',target/'baseline-manifest.json')
    if args.stage=='groups':
        command(run,'groups-extract',['analysis/fit_opponent_groups.py','--directory',run,'--step','extract'])
        command(run,'groups-fit',['analysis/fit_opponent_groups.py','--directory',run,'--step','fit']);return
    if args.stage=='snapshots':freeze_variants(run);return
    if args.stage=='extend':extend_comparison(run);return
    if args.stage=='integration':integration(run);return
    if args.stage=='tests':command(run,'tests',['-m','unittest','discover','-s','tests']);return
    if args.stage=='smoke':command(run,'smoke',['harness/eval.py','smoke','bot']);return
    if args.stage=='resources':
        command(run,'resources',['harness/resource_check.py','bot','--repeats','2','--output',run/'resources.json']);return
    if args.stage in ('benchmark','pilot','simulate','simulate-four','cpu-check','audit','report'):
        plan=json.loads((run/'study-plan.json').read_text())
        if args.stage=='benchmark':benchmark(run,plan)
        elif args.stage=='pilot':
            backend=json.loads((run/'backend-selection.json').read_text())
            evaluate(run,'pilot',plan['variants'],600,plan['pilot_seed'],backend['device'],backend['workers'])
        elif args.stage=='simulate':
            pilot=json.loads((run/'pilot.json').read_text())
            chips={str(c):sum(g['chips'][0] for g in pilot['games'] if g['cand_idx']==c) for c in range(5)}
            chosen=2 if chips['2']>=chips['3'] else 3
            selection=dict(chosen_index=chosen,selected=plan['variants'][chosen],pilot_chips=chips,rule=plan['selection'])
            if (run/'candidate-selection.json').exists():assert json.loads((run/'candidate-selection.json').read_text())==selection
            dump(run/'candidate-selection.json',selection)
            for p in (ROOT/selection['selected']).glob('*.py'):shutil.copyfile(p,ROOT/'bot'/p.name)
            command(run,'selected-tests',['-m','unittest','discover','-s','tests'])
            command(run,'selected-resources',['harness/resource_check.py','bot','--repeats','2',
                                             '--output',run/'selected-resources.json'])
            backend=json.loads((run/'backend-selection.json').read_text())
            evaluate(run,'simulate',[*plan['variants'][:2],selection['selected']],10000,plan['final_seed'],
                     backend['device'],backend['workers'],traces=True)
        elif args.stage=='cpu-check':
            evaluate(run,'cpu-check',['bot'],120,'opponent-groups-cpu-check-20261004','cpu',12)
        elif args.stage=='simulate-four':
            extension=extend_comparison(run)
            for p in (ROOT/extension['variants'][3]).glob('*.py'):shutil.copyfile(p,ROOT/'bot'/p.name)
            command(run,'four-tests',['-m','unittest','discover','-s','tests'])
            if not (run/'selected-tests.log').exists():
                for suffix in ('.log','-execution.json'):
                    shutil.copyfile(run/('four-tests'+suffix),run/('selected-tests'+suffix))
            if not (run/'selected-resources.json').exists():
                command(run,'selected-resources',['harness/resource_check.py',extension['variants'][2],'--repeats','2',
                        '--output',run/'selected-resources.json'])
            command(run,'main-groups-resources',['harness/resource_check.py',extension['variants'][3],'--repeats','2',
                    '--output',run/'main-groups-resources.json'])
            backend=json.loads((run/'backend-selection.json').read_text())
            if (run/'simulate.json').exists() and len(json.loads((run/'simulate.json').read_text())['games'])==30000:
                for suffix in ('.json','.log','-execution.json'):
                    shutil.copyfile(run/('simulate'+suffix),run/('simulate-three'+suffix))
            # Candidate indexes 0..2 and trace identities are unchanged; resume
            # reuses the three existing runs and only computes candidate 3.
            evaluate(run,'simulate',extension['variants'],10000,extension['seed'],backend['device'],backend['workers'],traces=True)
        elif args.stage=='audit':
            result=json.loads((run/'simulate.json').read_text())
            if result['compute']['device']=='cuda' and not (run/'cpu-check.json').exists():
                evaluate(run,'cpu-check',['bot'],120,'opponent-groups-cpu-check-20261004','cpu',12)
            assert len(result['games'])==40000
            dump(run/'simulation-plan.json',dict(games=len(result['games']),games_per_variant=10000))
            command(run,'audit',['analysis/audit_pattern_simulation.py','--directory',run,'--trace-subdir','simulate-traces',
                                '--catalogue','sparring/competitors/from_data_groups/bots.json',
                                '--devices','0,1,2,3','--workers','8'])
        elif args.stage=='report':
            command(run,'report',['analysis/report_opponent_groups.py','--directory',run])
        return
    steps = [
        ('prepare',['-m','opponent_model.runtime_patterns','prepare','--source-directory',frozen,'--directory',target]),
        ('train',['-m','opponent_model.within_game','train','--directory',target,'--devices','0,1,2,3','--epochs','100']),
        ('select',['-m','opponent_model.runtime_patterns','select','--directory',target]),
        ('refit-models',['-m','opponent_model.runtime_patterns','refit','--directory',target]),
        ('build',['sparring/competitors/build.py',target/'runtime-fit.json','--runtime-patterns',
                  '--destination','sparring/competitors/from_data_groups']),
        ('verify',['analysis/verify_runtime_patterns.py','--directory',target])]
    for name,argv in steps:
        if args.stage=='refit' or name==args.stage:
            if name!='verify' and any((run/'simulate-traces').glob('*.json.gz')):
                raise ValueError('Refitting would invalidate stored simulations; use a fresh study and checkout.')
            command(run,name,argv)


if __name__=='__main__': main()
