"""Paired three-policy comparison, public classification and decision audit."""
import argparse
from collections import Counter,defaultdict
import csv
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys

import numpy as np
os.environ.setdefault('MPLCONFIGDIR','/tmp/halliday-group-plots')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'vendor/macpoker-src'))
from analysis.halliday_report import BLUNDERS
from bot.groups import posterior,confidence
from harness.eval import score_set

NAMES=('Main','Call calibration','Groups + calibration','Groups + main')
RETURN_KEYS=('main','calibration','groups_calibration','groups_main',
             'calibration_group_gain','main_group_gain','calibration_base_gain','interaction')
STEM='opponent-groups-20261004'


def csv_file(path,rows):
    if not rows:return
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v) if isinstance(v,(dict,list,tuple)) else v for k,v in r.items()})


def paired_tables(report):
    groups=defaultdict(dict)
    for g in report['games']:
        key=g['cand_idx'],g['game']
        assert key not in groups[g['table']]
        groups[g['table']][key]=g
        assert sum(g['chips'])==0 and all(v=='OK' for v in g['verdicts']) and not any(g['errors'])
    tables=[]
    for t,group in sorted(groups.items()):
        n=len(report['tables'][t])+1
        assert 4<=n<=6
        assert set(group)=={(c,g) for c in range(4) for g in range(n)}
        chips=[sum(group[c,g]['chips'][0] for g in range(n)) for c in range(4)]
        scores=[score_set([group[c,g] for g in range(n)],100,2,40000) for c in range(4)]
        values=chips+[chips[2]-chips[1],chips[3]-chips[0],chips[2]-chips[3],
                      (chips[2]-chips[1])-(chips[3]-chips[0])]
        row=dict(table=t,games=n,**dict(zip(RETURN_KEYS,values)))
        for c,name in enumerate(RETURN_KEYS[:4]):
            row['points_'+name]=scores[c]['round_pts']
            row['won_'+name]=int(scores[c]['won_round'])
        tables.append(row)
    return tables


def paired_interval(tables,replicates=5000):
    counts=np.array([t['games'] for t in tables],dtype=float)
    totals=np.array([[t[k] for k in RETURN_KEYS]
                     for t in tables],dtype=float)
    point=totals.sum(0)/counts.sum()/2
    if len(tables)<2:return dict(point=point.tolist(),low=[None]*len(RETURN_KEYS),high=[None]*len(RETURN_KEYS))
    rng=np.random.default_rng(73793);draws=[]
    for first in range(0,replicates,100):
        index=rng.integers(len(tables),size=(min(100,replicates-first),len(tables)))
        draws.append(totals[index].sum(1)/counts[index].sum(1)[:,None]/2)
    low,high=np.quantile(np.concatenate(draws),[.025,.975],axis=0)
    return dict(point=point.tolist(),low=low.tolist(),high=high.tolist())


def placement_interval(tables,replicates=5000):
    points=np.array([[t['points_'+k] for k in RETURN_KEYS[:4]] for t in tables])
    wins=np.array([[t['won_'+k] for k in RETURN_KEYS[:4]] for t in tables])
    deltas=points[:,[2,3,2]]-points[:,[1,0,3]]
    rng=np.random.default_rng(38376);draws=[]
    for first in range(0,replicates,100):
        index=rng.integers(len(tables),size=(min(100,replicates-first),len(tables)))
        draws.append(deltas[index].mean(1))
    lo,hi=np.quantile(np.concatenate(draws),[.025,.975],axis=0)
    return dict(points=points.mean(0).tolist(),wins=wins.mean(0).tolist(),
                delta=deltas.mean(0).tolist(),low=lo.tolist(),high=hi.tolist())


def prefix_evaluation(run,output,fit):
    with np.load(run/'group-prefixes.npz',allow_pickle=False) as z:
        meta=json.loads(str(z['metadata']));rows=z['rows'];counts=z['counts']
    records=[]
    labels={b['bot']:b for b in fit['opponents']}
    for i,row in enumerate(rows):
        match,b,hand,seats,split,age,_=row
        label=labels[meta['bots'][int(b)]]
        if age!=0 or split not in (1,2) or not 4<=seats<=6 or not label['reliable_label']:continue
        probs=posterior(counts[i],fit['validation_groups'],fit['config']['temperature'],seats)
        top=int(np.argmax(probs));weight=confidence(probs,fit['validation_groups'],hand,fit['config']['threshold'])
        records.append(dict(match=meta['matches'][int(match)]['id'],bot=meta['bots'][int(b)],hands=int(hand),
            split='validation' if split==1 else 'test',expected_group=label['group'],predicted_group=top,
            probability=max(probs),counter_weight=weight,correct=top==label['group'],counts=counts[i].tolist()))
    csv_file(output/(STEM+'-classification.csv'),records)
    return records


def summarize(run,output):
    output.mkdir(parents=True,exist_ok=True)
    simulation=json.loads((run/'simulate.json').read_text())
    audits=json.loads((run/'audit-summary.json').read_text())
    plan=json.loads((run/'study-plan.json').read_text())
    fit=json.loads((run/'groups-fit.json').read_text())
    runtime=json.loads((run/'fit/runtime-fit.json').read_text())
    selected=json.loads((run/'candidate-selection.json').read_text())
    backend=json.loads((run/'backend-selection.json').read_text())
    snapshot=json.loads((run/'input/snapshot-manifest.json').read_text())
    coverage=json.loads((run/'fit/runtime-verification.json').read_text())
    resources=json.loads((run/'selected-resources.json').read_text())
    assert resources['passed']
    tables=paired_tables(simulation)
    assert len(simulation['games'])==len(audits['games'])==40000
    assert sum(t['games'] for t in tables)==10000
    interval=paired_interval(tables)
    placements=placement_interval(tables)
    summaries=[Counter() for _ in NAMES];streets=[defaultdict(Counter) for _ in NAMES]
    classified=[Counter() for _ in NAMES];game_rows=[];flags=[];seen=set();gpu=defaultdict(Counter)
    original={(g['cand_idx'],g['table'],g['game']):g for g in simulation['games']}
    loss=[defaultdict(Counter) for _ in NAMES];negative_loss=[defaultdict(Counter) for _ in NAMES]
    flag_streets=[defaultdict(Counter) for _ in NAMES]
    group_phases={c:defaultdict(Counter) for c in (2,3)}
    group_use={c:Counter() for c in (2,3)};first_group_hands={c:[] for c in (2,3)}
    for number,g in enumerate(audits['games'],1):
        c=int(g['match'].rsplit('-c',1)[1]);key=c,g['table'],g['game']
        assert key not in seen;seen.add(key)
        assert g['chips']==original[key]['chips'][0] and g['hands']==100
        s=summaries[c];s['games']+=1
        for k in ('chips','hands','actions','folds','bad_calls','missed_calls','certain_folds','allin_luck','ev_audited'):
            s[k]+=g[k]
        s['negative_games']+=g['chips']<0
        s['negative_games_with_flags']+=g['chips']<0 and g['flags']>0
        classified[c].update(g['classifications'])
        for street,v in g['streets'].items():streets[c][street].update(v)
        for category,v in g['loss_categories'].items():loss[c][category].update(v)
        if g['chips']<0:
            for category,v in g['loss_categories'].items():negative_loss[c][category].update(v)
        gpu[g['gpu']['device']].update({k:g['gpu'][k] for k in ('batches','ranked_hands','gpu_seconds')})
        game_rows.append(dict(variant=NAMES[c],match=g['match'],table=g['table'],game=g['game'],chips=g['chips'],
                              opponents=g['opponents'],folds=g['folds'],bad_calls=g['bad_calls'],missed_calls=g['missed_calls'],
                              allin_luck=g['allin_luck'],loss_categories=g['loss_categories']))
        with gzip.open(run/'audit'/(g['match']+'.json.gz'),'rt') as f:shard=json.load(f)
        assert shard['summary']==g
        per_hand={};first={}
        for row in shard['decisions']:
            d=row['diagnostic']
            if row['classification'] in BLUNDERS:
                flag_streets[c][row['street']].update([row['classification']])
                flags.append(dict(variant=NAMES[c],id=row['id'],street=row['street'],action=row['action'],
                    hole=row['hole'],board=row['board'],pot=row['pot'],call=row['call'],
                    classification=row['classification'],public_ev_lower=row['public_ev_lower'],public_ev_upper=row['public_ev_upper'],
                    hand_chips=row['hand_chips'],game_chips=row['match_chips'],groups=d.get('groups')))
            if c in (2,3):
                assert d.get('groups_available') is True,'Grouping disabled by malformed runtime events'
                group_use[c]['decisions']+=1
                for player,reading in d['groups'].items():
                    per_hand[row['hand'],player]=reading
                    if reading['weight']>0:
                        first.setdefault(player,row['hand'])
                        group_use[c][reading['group']]+=1
        if c in (2,3):
            first_group_hands[c].extend(first.values())
            for (h,p),reading in per_hand.items():
                phase=h//10*10
                group_phases[c][phase]['observations']+=1
                group_phases[c][phase]['classified']+=reading['weight']>0
                group_phases[c][phase]['weight_sum']+=reading['weight']
                group_phases[c][phase]['drift_detected']+=reading['drift']>0
        if number%5000==0:print(f'{number}/40000 audited games summarized',flush=True)
    assert seen==set(original)
    assert set(gpu)=={'cuda:0','cuda:1','cuda:2','cuda:3'}
    assert all(v['ranked_hands']>0 for v in gpu.values())
    assert all(s['games']==10000 and s['hands']==1000000 for s in summaries)
    assert all(group_use[c]['decisions']>0 and first_group_hands[c] for c in (2,3))
    csv_file(output/(STEM+'-games.csv'),game_rows);csv_file(output/(STEM+'-blunders.csv'),flags)
    csv_file(output/(STEM+'-tables.csv'),tables)
    csv_file(output/(STEM+'-opponents.csv'),fit['opponents'])
    parameters=[]
    for name,b in runtime['bots'].items():
        for parameter,v in b['estimate']['parameters'].items():
            parameters.append(dict(bot=name,parameter=parameter,estimate=v['estimate'],variance=v['bootstrap_variance'],
                low=v['confidence_interval'][0],high=v['confidence_interval'][1],
                newest_support=v['prior']['latest_opportunities'],effective_support=v['prior']['effective_opportunities'],
                status=v['prior']['status'],older_versions=v['prior']['older_versions']))
    csv_file(output/(STEM+'-parameters.csv'),parameters)
    prefix_evaluation(run,output,fit)
    summary=dict(interval=interval,return_keys=RETURN_KEYS,placements=placements,summaries=summaries,streets=streets,
        classifications=classified,loss_categories=loss,negative_game_loss_categories=negative_loss,flag_streets=flag_streets,
        group_phases=group_phases,group_use=group_use,first_group_hands={c:Counter(v) for c,v in first_group_hands.items()},
        duplicate_tables=len(tables),compute=simulation['compute'],audit_gpu=gpu,audit_code_sha256=audits['code_sha256'])
    plot(output,interval,fit,summaries,group_phases)
    ci=lambda i:f"{interval['point'][i]:+.2f} [{interval['low'][i]:+.2f}, {interval['high'][i]:+.2f}]"
    metric=lambda key:' | '.join(f"{s[key]:,}" for s in summaries)
    prior_only=[n for n,v in runtime['selection']['bots'].items() if v.get('prior_only') and n!='Halliday']
    sparse=sum(p['status']=='still_sparse' for p in parameters)
    rows=['# Opponent groups — 4 October 2026','',
        f"The held-out study ran **10,000 games per version**, or **4,000,000 hands**, against {len(fit['opponents'])} refreshed opponent replicas. "
        f"Adding grouping to call calibration changed chip return by **{ci(4)} bb/100**; adding grouping to main changed it by **{ci(5)} bb/100**.",'',
        ('The primary interval supports an improvement over call calibration in this replica field.' if interval['low'][4]>0 else
         'The primary interval supports a regression versus call calibration in this replica field.' if interval['high'][4]<0 else
         'The primary interval does not establish an improvement over call calibration in this replica field.'),'',
        '| Metric | Main | Call calibration | Groups + calibration | Groups + main |','| --- | ---: | ---: | ---: | ---: |',
        '| Net chips | '+metric('chips')+' |',
        '| bb/100 [95% paired-table bootstrap interval] | '+' | '.join(ci(i) for i in range(4))+' |',
        '| Mean duplicate-table placement points | '+' | '.join(f'{x:.3f}' for x in placements['points'])+' |',
        '| Outright first in duplicate table | '+' | '.join(f'{100*x:.2f}%' for x in placements['wins'])+' |',
        '| Folds per hand | '+' | '.join(f"{100*s['folds']/s['hands']:.2f}%" for s in summaries)+' |',
        '| Negative games | '+metric('negative_games')+' |',
        '| Probable missed terminal calls | '+metric('missed_calls')+' |',
        '| Probable bad terminal calls | '+metric('bad_calls')+' |',
        '| Provably avoidable folds | '+metric('certain_folds')+' |',
        '| Player failures | 0 | 0 | 0 | 0 |','',
        f"Identical opponent tables, seat rotations and decks were used for all four policies. Bootstrap resampling keeps each of the {len(tables):,} complete duplicate tables together. "
        'Chip return weights games equally; placement points weight complete duplicate tables equally. Grouping versus calibration was the original primary comparison. '
        'The user requested grouping on main after the three-policy run started; that variant uses the same frozen settings and final seed without further tuning. '
        'The additional comparisons are descriptive, with individual 95% intervals rather than a familywise claim. Timed sampling can differ between runs and hardware. These are replica simulations, not live tournament results.','',
        f"With grouping on both bases, the calibration-based bot differs from the main-based bot by **{ci(6)} bb/100**. "
        f"The difference between the two grouping improvements is **{ci(7)} bb/100**.",'',
        '| Placement-point change [95% paired-table interval] | Change |','| --- | ---: |',
        *[f"| {label} | {placements['delta'][i]:+.3f} [{placements['low'][i]:+.3f}, {placements['high'][i]:+.3f}] |"
          for i,label in enumerate(('Grouping added to calibration','Grouping added to main','Calibration base versus main base, both grouped'))],'',
        'The previous call-calibration study reported main at 36.0671 and calibration at 37.76845 bb/100, a paired change of +1.70135 '
        '[+0.77688, +2.67168]. That study used 61 opponents; this refit uses 69. Raw returns across the two studies are not controlled comparisons. '
        '[Previous committed report](https://github.com/halliday-poker/halliday2/blob/e186308ade4a05778d68a82b9fd636adb46e999b/analysis/reports/call-calibration-20261004.md).','',
        f'![Performance, classification and counter diagnostics]({STEM}-comparison.png)','',
        '## Strategy','',
        'The calibration-based variant retains the terminal-call corrections and 0.06 river margin from call calibration. '
        'The main-based variant disables both terminal-call corrections and restores main\'s 0.02 tracked-range river margin. '
        'Its group river-margin targets shift by the same -0.04, preserving identical counter adjustments relative to each base. '
        'A compact beta-binomial classifier observes completed public hands, uses table-size-specific distributions, '
        'and assigns probabilities to behavioral groups. Group variance and sparse-fit uncertainty reduce the strength of the counter. '
        'Unknown opponents retain the baseline strategy. No opponent names, external model files, network calls or GPU are used by the submitted bot.','',
        '| Group | Reliable training identities | Main counter |','| --- | ---: | --- |',
        *[f"| {g['name']} | {len(g['members'])} | Bluff frequency target {g['counter']['bluff_frequency']:.2f}; "
          f"tracked bluff floor {g['counter']['range_bluff_floor']:.2f}; river call margin {g['counter']['range_call_margin_river']:.3f}; "
          f"late bet size {g['counter']['late_pot_fraction']:.2f} pot. |" for g in fit['groups']],'',
        'Every target is blended with baseline settings according to classification confidence. '
        'Aggression alone is not treated as proof of bluffing. Showdown features use only legally revealed cards. '
        'A fitted adaptive trait and supported changes in conditional frequencies permit small private sizing variation, '
        'with the same distribution for value bets and bluffs. Random variation never changes call/fold thresholds or the decision to value-bet a strong hand.','',
        f"The separate 600-game-per-variant pilot chose `{selected['selected']}` by the predeclared total-chip rule. "
        f"Pilot totals: {selected['pilot_chips']}. Range-only adaptation was an ablation, not a replacement for the requested group counters. "
        'The final seed was held out from this selection. The main-based grouping variant uses that same selected strength; it was not retuned.','',
        '## Early identification','',
        'Groups and likelihoods were fitted on training games; group count, temperature and threshold were selected using validation prefixes at hands 5, 10 and 20. '
        'The table below measures agreement with training-derived behavioral labels on held-out newest-version games at four-to-six-seat tables. '
        'Labels are not recovered source-code identities. Development examined archive diagnostics; this is not an untouched external validation set. '
        'Runtime priors were then refitted using all available newest observations.','',
        '| Hands observed | Held-out opponent games | Start blending | Agreement among classified |','| --- | ---: | ---: | ---: |',
        *[f"| {e['hands']} | {e['prefixes']} | {100*e['coverage']:.1f}% | {100*e['accuracy']:.1f}% |" for e in fit['evaluation'] if e['split']=='test' and e['hands'] in (5,10,20,50,100)],'',
        'Small early samples and ambiguous styles remain unclassified. Identification is per game: the tournament starts a fresh process for each game, so memory cannot carry across a whole round. '
        'The runtime trace audit confirms the classifier remained active throughout every candidate decision.','',
        '## Refitted field and uncertainty','',
        f"The frozen input contains {snapshot['rows']:,} records, {snapshot['matches_with_actions']:,} replays and {snapshot['metadata_matches']:,} metadata matches; "
        f"{len(snapshot['metadata_without_actions'])} metadata matches lack a replay. All {coverage['coverage']['actions']:,} newest-version action rows were retained, including upload validation games. "
        'Every trusted validation against house:call starts a new version regardless of verdict.','',
        'Older observations contribute only to sparse contexts, at maximum weight '
        '`0.1 ** version_age * 2 ** (-upload_gap_hours / 6)`, capped at each parameter\'s support target. '
        f"{sparse}/{len(parameters)} parameter estimates remain below target. Parameter uncertainty uses 300 whole-match bootstrap draws stratified by version; "
        'the files retain covariance and between-game variation as well as point estimates. These quantify uncertainty within the replica model, not all possible changes in a new submission.','',
        f"Newest submissions without replays: {', '.join(prior_only)}. Those opponents use discounted historical priors and remain explicitly uncertain. "
        'The classifier models the broader archive and conditions on table size; restricting training to four-to-six seats would omit most identities.','',
        '## Weaknesses and decision review','',
        *[f"**{NAMES[c]}:** {summaries[c]['missed_calls']:,} probable missed terminal calls, {summaries[c]['bad_calls']:,} probable bad terminal calls; "
          f"{summaries[c]['negative_games_with_flags']:,} of {summaries[c]['negative_games']:,} negative games contain a flagged action."
          for c in (2,3)],'',
        'A losing game is not itself proof of a blunder. Every simulated hand was reconstructed to verify legality, payouts and zero-sum chips.','',
        'Terminal call/fold flags require agreement across tight/loose public-range models and applicable shover sensitivity, after a Monte Carlo margin and a 2-chip threshold. '
        'These are model-based review candidates, not known optimal-action labels; there is no correction for multiple decision-level tests. Changed policies encounter different later decisions.','',
        '| Variant | Street | Missed terminal calls | Bad terminal calls |','| --- | --- | ---: | ---: |',
        *[f"| {NAMES[c]} | {street} | {flag_streets[c][street]['probable_missed_terminal_call']:,} | {flag_streets[c][street]['probable_bad_terminal_call']:,} |"
          for c in (2,3) for street in ('preflop','flop','turn','river')],'',
        'The following ledger includes only games ending with negative chips. Categories classify losing hands; the final row retains profitable hands in those games. '
        'A category\'s chips are realized results, not an estimate of how many chips a strategy change would recover. Failed bluffs and lost all-ins can be correct decisions.','',
        '| Hand category in negative games | Groups + calibration: hands / chips | Groups + main: hands / chips |',
        '| --- | ---: | ---: |',
        *[f"| {category.replace('_',' ')} | "+' | '.join(f"{negative_loss[c][category]['hands']:,} / {negative_loss[c][category]['chips']:+,}" for c in (2,3))+' |'
          for category in sorted(set(negative_loss[2])|set(negative_loss[3]),key=lambda k:(k=='non_losing_hand',negative_loss[2][k]['chips']))],'',
        '## SWOT','',
        '- **Strengths:** compact public-event inference, uncertainty-weighted counters, retained call fixes, and measured resource compliance.',
        '- **Weaknesses:** broad groups hide variation within a style; early classification covers only part of the field. Bluff and adaptation estimates remain indirect.',
        '- **Opportunities:** collect more recent games at tournament table sizes, review high-cost call/fold cases, and test finer groups only when early identification supports them.',
        '- **Threats:** new uploads, strategic deception, sparse priors, and replica mismatch can invalidate the learned group signatures. No four-round regrouping or podium probability is simulated.','',
        '## Compute and reproduction','',
        f"Main `{plan['main_commit']}`; call calibration `{plan['calibration_commit']}`. The selected backend used {backend['workers']} {backend['device']} workers after matched throughput benchmarks. "
        'All four V100s performed fitting and the separate decision audit. GPU batching was checked against main\'s CPU math on 48 fixed-sample cases.','',
        f"The selected bot passed restricted subprocess games with one CPU, a 512 MiB address-space limit, read-only filesystems and a private network namespace. "
        f"Maximum measured RSS was {max(g['resources']['RESOURCE_USAGE']['max_rss_kib'] for g in resources['games'])/1024:.1f} MiB. "
        'Tests, smoke results, source hashes, model manifests and device work counters accompany the report.','',
        f"Input SHA-256: `{runtime['source_sha256']}`.",'',
        f'[Reproduction commands]({STEM}-reproduce.md) · [Paired tables]({STEM}-tables.csv) · [Game reviews]({STEM}-games.csv) · '
        f'[Blunder cases]({STEM}-blunders.csv) · [Classification checks]({STEM}-classification.csv) · [Parameters]({STEM}-parameters.csv)','']
    (output/(STEM+'.md')).write_text('\n'.join(rows))
    evidence=output/'evidence'/STEM;evidence.mkdir(parents=True,exist_ok=True)
    for name in ('study-plan.json','baseline-manifest.json','calibration-manifest.json','variants-manifest.json','candidate-selection.json',
                 'backend-selection.json','groups-fit.json','group-integration-verification.json','selected-resources.json','main-groups-resources.json',
                 'study-extension.json','simulate-execution.json','audit-execution.json','selected-tests-execution.json','selected-tests.log',
                 'four-tests-execution.json','four-tests.log','smoke.log'):
        shutil.copyfile(run/name,evidence/name)
    for name in ('runtime-fit.json','runtime-verification.json','prior-verification.json','snapshot-manifest.json','upload-selection.json'):
        shutil.copyfile(run/'fit'/name,evidence/name)
    (evidence/'comparison-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    paths=list(output.glob(STEM+'*'))+list(evidence.iterdir())
    hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file() and p.name!='artifact-hashes.json'}
    (evidence/'artifact-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
    print(json.dumps(dict(interval=interval,summaries=summaries),indent=2))


def plot(output,interval,fit,summaries,phases):
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(14,10),layout='constrained');colors=['#87969d','#386e91','#248574','#ad6c37']
    ax=axes[0,0];means=np.array(interval['point'][:4]);x=np.arange(4)
    ax.bar(x,means,color=colors)
    ax.errorbar(x,means,yerr=[means-np.array(interval['low'][:4]),np.array(interval['high'][:4])-means],fmt='none',color='black',capsize=4)
    ax.set(xticks=x,xticklabels=[n.replace(' + ',' +\n') for n in NAMES],ylabel='bb / 100 hands',title='A. Return with table-bootstrap 95% intervals')
    ax=axes[0,1];checks=[e for e in fit['evaluation'] if e['split']=='test']
    ax.plot([e['hands'] for e in checks],[100*e['coverage'] for e in checks],'-o',label='Coverage')
    ax.plot([e['hands'] for e in checks],[100*e['accuracy'] for e in checks],'-o',label='Agreement when classified')
    ax.set(xlabel='Completed hands',ylabel='Percent',ylim=(0,105),title='B. Held-out early group identification');ax.legend()
    ax=axes[1,0];x=np.arange(2)
    for c in range(4):ax.bar(x+(c-1.5)*.20,[summaries[c]['missed_calls'],summaries[c]['bad_calls']],.20,label=NAMES[c],color=colors[c])
    ax.set(xticks=x,xticklabels=['Missed terminal calls','Bad terminal calls'],ylabel='Model-supported flags',title='C. Call and fold review');ax.legend()
    ax=axes[1,1]
    for c in (2,3):
        keys=sorted(phases[c]);p=phases[c]
        ax.plot([k+5 for k in keys],[100*p[k]['classified']/p[k]['observations'] for k in keys],'-o',color=colors[c],label=NAMES[c]+': classified')
        ax.plot([k+5 for k in keys],[100*p[k]['weight_sum']/p[k]['observations'] for k in keys],'--',color=colors[c],label=NAMES[c]+': mean weight')
    ax.set(xlabel='Hand phase midpoint',ylabel='Percent',ylim=(0,105),title='D. Online classification during simulation');ax.legend()
    fig.suptitle('Opponent groups · 10,000 matched games per version · refreshed newest-upload replicas',fontsize=14)
    fig.savefig(output/(STEM+'-comparison.png'),dpi=170);fig.savefig(output/(STEM+'-comparison.svg'));plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,default=Path('analysis/results/opponent-groups-20261004'))
    p.add_argument('--output',type=Path,default=Path('analysis/reports'))
    args=p.parse_args();summarize(args.directory.resolve(),args.output.resolve())
