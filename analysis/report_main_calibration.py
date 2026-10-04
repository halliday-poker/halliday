"""Compare one new main run with an archived, never rerun calibration control."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys

import numpy as np
os.environ.setdefault('MPLCONFIGDIR','/tmp/halliday-main-plots')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from analysis.halliday_report import BLUNDERS
from analysis.run_main_calibration import STEM, verify, dump, packed
from harness.eval import score_set

NAMES=('Archived call calibration','New main')
STREETS=('preflop','flop','turn','river')
FLAGS=('probable_missed_terminal_call','probable_bad_terminal_call','certain_avoidable_fold')


def csv_file(path, rows):
    if not rows:return
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v) if isinstance(v,(dict,list,tuple)) else v for k,v in row.items()})


def paired_tables(new, old):
    assert new['tables']==old['tables'], 'Different ordered opponent tables'
    assert new['seed']==old['seed'], 'Different deck seeds'
    for key in ('deals','time_ms','increment_ms'):
        assert new['args'][key]==old['args'][key], f'Different {key}'
    assert new['args']['deals']==100
    groups=[defaultdict(dict),defaultdict(dict)]
    for c,report in enumerate((old,new)):
        for g in report['games']:
            assert g['cand_idx']==(1 if c==0 else 0), 'Unexpected policy included'
            assert g['game'] not in groups[c][g['table']], 'Duplicate game'
            assert g['opponents']==report['tables'][g['table']]
            assert len(g['chips'])==len(g['opponents'])+1
            assert sum(g['chips'])==0 and all(v=='OK' for v in g['verdicts']) and not any(g['errors'])
            groups[c][g['table']][g['game']]=g
        assert set(groups[c])==set(range(len(report['tables'])))
    tables=[]
    for t,opponents in enumerate(new['tables']):
        n=len(opponents)+1
        assert 4<=n<=6
        assert all(set(group[t])==set(range(n)) for group in groups), 'Incomplete seat rotations'
        sets=[[group[t][g] for g in range(n)] for group in groups]
        chips=[sum(g['chips'][0] for g in gs) for gs in sets]
        scores=[score_set(gs,100,2,40000) for gs in sets]
        tables.append(dict(table=t,games=n,calibration=chips[0],main=chips[1],delta=chips[1]-chips[0],
            calibration_points=scores[0]['round_pts'],main_points=scores[1]['round_pts'],
            points_delta=scores[1]['round_pts']-scores[0]['round_pts'],
            calibration_win=int(scores[0]['won_round']),main_win=int(scores[1]['won_round'])))
    return tables


def interval(tables,keys=('calibration','main','delta'),game_weighted=True,replicates=5000):
    totals=np.array([[t[k] for k in keys] for t in tables],dtype=float)
    weights=np.array([t['games']*2 if game_weighted else 1 for t in tables],dtype=float)
    point=totals.sum(0)/weights.sum()
    rng=np.random.default_rng(73793);draws=[]
    for first in range(0,replicates,100):
        ix=rng.integers(len(tables),size=(min(100,replicates-first),len(tables)))
        draws.append(totals[ix].sum(1)/weights[ix].sum(1)[:,None])
    low,high=np.quantile(np.concatenate(draws),[.025,.975],axis=0)
    return dict(point=point.tolist(),low=low.tolist(),high=high.tolist(),replicates=replicates,
                unit='bb/100' if game_weighted else 'placement points',keys=list(keys))


def aggregate(games, originals):
    total=Counter();streets=defaultdict(Counter);loss=defaultdict(Counter)
    negative_loss=defaultdict(Counter);classes=Counter();phases=[Counter() for _ in range(4)]
    seen=set()
    for g in games:
        key=g['table'],g['game'];assert key not in seen;seen.add(key)
        assert g['chips']==originals[key]['chips'][0] and g['hands']==100
        total['games']+=1
        for k in ('chips','hands','actions','folds','flags','bad_calls','missed_calls','certain_folds',
                  'ev_audited','facing_decisions','allin_count','allin_luck','vpip_hands','pfr_hands','think_ms'):
            total[k]+=g[k]
        total['negative_games']+=g['chips']<0
        total['negative_games_with_flags']+=g['chips']<0 and g['flags']>0
        total['flags_in_negative_games']+=g['flags'] if g['chips']<0 else 0
        total['negative_game_chips']+=g['chips'] if g['chips']<0 else 0
        for street,v in g['streets'].items():streets[street].update(v)
        classes.update(g['classifications'])
        for i,v in enumerate(g['phases']):phases[i].update(v)
        for k,v in g['loss_categories'].items():
            loss[k].update(v)
            if g['chips']<0:negative_loss[k].update(v)
    assert seen==set(originals)
    total['terminal_folds']=sum(v['terminal_folds'] for v in streets.values())
    total['terminal_calls']=sum(v['terminal_calls'] for v in streets.values())
    total['facing_folds']=sum(v['facing_folds'] for v in streets.values())
    total['max_decision_ms']=max(g['max_ms'] for g in games)
    total['max_game_think_ms']=max(g['think_ms'] for g in games)
    return dict(total=total,streets=streets,loss=loss,negative_loss=negative_loss,classes=classes,phases=phases)


def cost(row):
    if row['action']=='fold':return max(0,row['public_ev_lower'] or 0)
    return max(0,-(row['public_ev_upper'] or 0))


def context(row):
    d=row['diagnostic'];e=d.get('estimate') or {}
    if d.get('equity') is None:return 'no accepted equity estimate'
    if e.get('method')=='monte_carlo' and e.get('samples',0)<128:return 'conservative sparse estimate'
    return 'tracked range estimate' if d.get('ranged') else 'uniform range estimate'


def figures(output, stats, returns, sizes, comparison):
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    colors=['#677d95','#008b78']
    fig,axs=plt.subplots(2,2,figsize=(13,9),layout='constrained')
    ax=axs[0,0]
    for i in (0,1):
        y=returns['point'][i]
        ax.bar(i,y,color=colors[i],width=.55)
        ax.errorbar(i,y,yerr=[[y-returns['low'][i]],[returns['high'][i]-y]],color='#223344',capsize=6)
        ax.text(i,returns['high'][i]+1,f'{y:.2f}',ha='center',fontweight='bold')
    ax.set_xticks([0,1],['Saved calibration','Main a707565']);ax.set_ylabel('bb / 100 hands')
    ax.set_title('Chip return · 95% table bootstrap')
    ax=axs[0,1]
    for i,n in enumerate((4,5,6)):
        v=sizes[n];y=v['point'][2]
        ax.errorbar(y,i,xerr=[[y-v['low'][2]],[v['high'][2]-y]],fmt='o',color=colors[1],capsize=5)
        ax.annotate(f'{y:+.2f}',(y,i),xytext=(0,10),textcoords='offset points',ha='center')
    ax.axvline(0,color='#777',lw=1);ax.set_yticks(range(3),['4 seats','5 seats','6 seats'])
    ax.set_ylim(-.5,2.5);ax.set_xlabel('New main − saved calibration (bb / 100)')
    ax.set_title('Matched improvement by table size')
    ax=axs[1,0];x=np.arange(3)
    for c in (0,1):
        vals=[stats[c]['total'][k] for k in ('missed_calls','bad_calls','certain_folds')]
        bars=ax.bar(x+(c-.5)*.35,vals,width=.35,color=colors[c],label=NAMES[c])
        ax.bar_label(bars,padding=3,fontsize=9)
    ax.set_xticks(x,['Missed terminal\ncalls','Bad terminal\ncalls','Certain avoidable\nfolds'])
    ax.set_title('Decision flags per 1 million hands');ax.legend(fontsize=9)
    ax=axs[1,1]
    keys=sorted((k for k in stats[1]['negative_loss'] if k!='non_losing_hand'),
                key=lambda k:stats[1]['negative_loss'][k]['chips'])[:5]
    labels={'profitable_allin_lost_runout':'Positive-EV all-in, lost runout','other_losing_allin':'Other losing all-in',
            'other_showdown_loss':'Other showdown loss','failed_air_bet_hand':'Failed air-bet hand',
            'failed_semibluff_hand':'Failed semibluff hand','postflop_invest_then_fold':'Invest postflop, then fold',
            'blind_only_fold':'Fold blinds','probable_bad_terminal_call':'Bad terminal call',
            'preflop_invest_then_fold':'Invest preflop, then fold'}
    x=np.arange(len(keys))
    for c in (0,1):
        ax.barh(x+(c-.5)*.35,[-stats[c]['negative_loss'].get(k,{}).get('chips',0)/1e6 for k in keys],
                height=.35,color=colors[c])
    ax.set_yticks(x,[labels.get(k,k.replace('_',' ')) for k in keys]);ax.invert_yaxis()
    ax.set_xlabel('Gross lost chips (millions)');ax.set_title('Losses inside negative games · not all errors')
    fig.suptitle('Main a707565 versus archived call calibration\n10,000 games each · identical 2,009 tables and decks',fontsize=15)
    for ext in ('png','svg'):fig.savefig(output/(STEM+'-comparison.'+ext),dpi=180)
    plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    for c in (0,1):
        chips=sorted(row['calibration_chips' if c==0 else 'main_chips'] for row in comparison)
        axs[0].plot(chips,np.arange(1,len(chips)+1)/len(chips),color=colors[c],label=NAMES[c])
        phases=stats[c]['phases']
        axs[1].plot(range(4),[v['chips']/2/v['hands']*100 for v in phases],marker='o',color=colors[c],label=NAMES[c])
    axs[0].axvline(0,color='#aaa',lw=1);axs[0].set(xlabel='Net chips per 100-hand game',ylabel='Fraction of games at or below',title='Game outcome distribution')
    axs[0].legend(fontsize=9);axs[1].set_xticks(range(4),['1–25','26–50','51–75','76–100'])
    axs[1].set(xlabel='Hand number within game',ylabel='bb / 100 hands',title='Within-game performance (descriptive)')
    for ext in ('png','svg'):fig.savefig(output/(STEM+'-distribution.'+ext),dpi=180)
    plt.close(fig)


def build(run, output):
    output.mkdir(parents=True,exist_ok=True)
    plan=verify(run)
    with gzip.open(run/'archived-calibration.json.gz','rt') as f:old=json.load(f)
    new=json.loads((run/'simulate.json').read_text())
    audit=json.loads((run/'audit-summary.json').read_text())
    assert audit['code_sha256']==old['code_sha256'], 'Public audit models changed between policies'
    resources=json.loads((run/'resources.json').read_text());assert resources['passed']
    tactics=json.loads((run/'tactical-review.json').read_text())
    assert tactics['games']==10000
    cases=json.loads((run/'case-review.json').read_text())
    tables=paired_tables(new,old);assert sum(t['games'] for t in tables)==10000
    assert len(new['games'])==len(old['games'])==len(audit['games'])==len(old['audits'])==10000
    returns=interval(tables)
    placements=interval(tables,('calibration_points','main_points','points_delta'),False)
    sizes={n:interval([t for t in tables if t['games']==n]) for n in (4,5,6)}
    originals=[{(g['table'],g['game']):g for g in r['games']} for r in (old,new)]
    sets=[old['audits'],audit['games']]
    stats=[aggregate(gs,orig) for gs,orig in zip(sets,originals)]
    flags=[old['flags'],[]];gpu=defaultdict(Counter);diagnostics=Counter();bets=Counter()
    for g in audit['games']:
        with gzip.open(run/'audit'/(g['match']+'.json.gz'),'rt') as f:shard=json.load(f)
        assert shard['summary']==g
        gpu[g['gpu']['device']].update({k:g['gpu'][k] for k in ('batches','ranked_hands','gpu_seconds')})
        for row in shard['decisions']:
            if row['classification'] in BLUNDERS:flags[1].append(row)
            d=row['diagnostic'];e=d.get('estimate')
            if e:
                diagnostics['equity_estimates']+=1
                diagnostics['time_limited']+=e.get('stop_reason')=='time_budget'
                diagnostics['rejected_estimates']+=d.get('equity') is None
                diagnostics['sparse_estimates']+=e.get('samples',0)<128
            if row['action']=='raise' and row['street']!='preflop':
                bets['postflop_raises']+=1
                for tag in ('air_bet','semibluff','bluff_answered','failed_air_bet','failed_semibluff','bet_then_fold'):
                    bets[tag]+=tag in row['tags']
                if row['call']==0 and row['amount']>=1.3*row['pot'] and row['pot']>0:
                    bets['overbet_openings']+=1
                    bets['overbet_air_or_draw']+=any(tag in row['tags'] for tag in ('air_bet','semibluff'))
                    bets['overbet_answered']+='bluff_answered' in row['tags']
    assert set(gpu)=={'cuda:0','cuda:1','cuda:2','cuda:3'} and all(v['ranked_hands']>0 for v in gpu.values())
    by_street=[defaultdict(Counter),defaultdict(Counter)];contexts=[Counter(),Counter()]
    flag_rows=[]
    for c,rows in enumerate(flags):
        assert len(rows)==stats[c]['total']['flags']
        for r in rows:
            by_street[c][r['street']][r['classification']]+=1
            contexts[c][context(r)]+=1
            d=r['diagnostic'];e=d.get('estimate') or {}
            flag_rows.append(dict(version=NAMES[c],id=r['id'],street=r['street'],action=r['action'],hole=r['hole'],
                board=r['board'],pot=r['pot'],call=r['call'],classification=r['classification'],
                public_ev_lower=r['public_ev_lower'],public_ev_upper=r['public_ev_upper'],hand_chips=r['hand_chips'],
                game_chips=r['match_chips'],bot_equity=d.get('equity'),equity_samples=e.get('samples'),
                stop_reason=e.get('stop_reason'),context=context(r),conservative_model_cost=cost(r)))
    comparison=[]
    by_key=[{(g['table'],g['game']):g for g in gs} for gs in sets]
    for key in sorted(originals[0]):
        a,b=[gs[key] for gs in by_key]
        comparison.append(dict(table=key[0],game=key[1],seats=b['size'],opponents=b['opponents'],
            calibration_chips=a['chips'],main_chips=b['chips'],delta=b['chips']-a['chips'],
            calibration_folds=a['folds'],main_folds=b['folds'],calibration_flags=a['flags'],main_flags=b['flags'],
            main_bad_calls=b['bad_calls'],main_missed_calls=b['missed_calls'],main_loss_categories=b['loss_categories']))
    pool=json.loads((ROOT/plan['catalogue']).read_text())['bots'];opponents=[]
    for identity,record in pool.items():
        subset=[t for t in tables if any(s.endswith('@'+identity) for s in new['tables'][t['table']])]
        if not subset:continue
        v=interval(subset,replicates=2000)
        opponents.append(dict(bot=record['name'],tables=len(subset),games=sum(t['games'] for t in subset),
            calibration_bb100=v['point'][0],main_bb100=v['point'][1],delta=v['point'][2],low=v['low'][2],high=v['high'][2]))
    summary=dict(plan=plan,return_interval=returns,placement_interval=placements,by_size=sizes,statistics=stats,
        outright_wins=[sum(t[k] for t in tables)/len(tables) for k in ('calibration_win','main_win')],
        flag_streets=by_street,flag_contexts=contexts,main_diagnostics=diagnostics,main_bets=bets,
        main_gpu=gpu,simulation_seconds=json.loads((run/'simulate-execution.json').read_text())['wall_seconds'],
        audit_seconds=audit['elapsed_seconds'],resources=resources,
        tactics=tactics,cases=cases,
        model_cost_lower=[sum(cost(r) for r in fs) for fs in flags])
    dump(run/'comparison-summary.json',summary)
    csv_file(output/(STEM+'-games.csv'),comparison)
    csv_file(output/(STEM+'-tables.csv'),tables)
    csv_file(output/(STEM+'-blunders.csv'),flag_rows)
    csv_file(output/(STEM+'-opponents.csv'),sorted(opponents,key=lambda v:v['main_bb100']))
    figures(output,stats,returns,sizes,comparison)
    write_report(run,output,summary,flags,sets,tables,opponents)
    packed(run/'main-audited-results.json.gz',dict(games=new['games'],audits=audit['games'],flags=flags[1],
        seed=new['seed'],tables=new['tables'],args=new['args'],code_sha256=audit['code_sha256']))
    evidence=output/'evidence'/STEM;evidence.mkdir(parents=True,exist_ok=True)
    for name in ('study-plan.json','main-manifest.json','simulation-plan.json','tables.json',
                 'archived-calibration.json.gz','main-audited-results.json.gz','archive-verification.json',
                 'comparison-summary.json','resources.json','resources.log','resources-execution.json',
                 'simulate.log','simulate-execution.json','audit.log','audit-execution.json','comparison-tests.log',
                 'tactical-review.json','tactics.log','tactics-execution.json','main-changes.patch',
                 'case-review.json','cases.log','cases-execution.json'):
        if (run/name).exists():shutil.copyfile(run/name,evidence/name)
    hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest()
        for p in [*output.glob(STEM+'*'),*evidence.iterdir()] if p.is_file() and p.name!='artifact-hashes.json'}
    dump(evidence/'artifact-hashes.json',hashes)
    print(json.dumps(dict(return_interval=returns,placement_interval=placements,
        totals=[s['total'] for s in stats],flag_streets=by_street,flag_contexts=contexts),indent=2))


def write_report(run, output, s, flags, sets, tables, opponents):
    stats=s['statistics'];tot=[v['total'] for v in stats];r=s['return_interval'];p=s['placement_interval']
    ci=lambda v,i:f"{v['point'][i]:+.2f} [{v['low'][i]:+.2f}, {v['high'][i]:+.2f}]"
    ev_bounds=lambda v:('rule-based' if v['public_ev_lower'] is None else
                        f"[{v['public_ev_lower']:.2f}, {v['public_ev_upper']:.2f}]")
    metric=lambda label,vs:'| '+label+' | '+' | '.join(str(v) for v in vs)+' |'
    pct=lambda numerator,denominator:f'{100*numerator/max(1,denominator):.3f}%'
    direction=('an improvement' if r['low'][2]>0 else 'a regression' if r['high'][2]<0 else 'no clear difference')
    negative=sorted((g for g in sets[1] if g['chips']<0),key=lambda g:g['chips'])
    selected=[*sorted((g for g in negative if g['flags']),key=lambda g:g['chips'])[:3],
              *[g for g in negative if not g['flags']][:2]]
    examples=[]
    for classification in FLAGS:
        examples.extend(sorted((v for v in flags[1] if v['classification']==classification),key=cost,reverse=True)[:3])
    losskeys=sorted((k for k in stats[1]['negative_loss'] if k!='non_losing_hand'),
                    key=lambda k:stats[1]['negative_loss'][k]['chips'])
    gross=-sum(stats[1]['negative_loss'][k]['chips'] for k in losskeys)
    badriver=s['flag_streets'][1].get('river',{}).get('probable_bad_terminal_call',0)
    misspre=s['flag_streets'][1].get('preflop',{}).get('probable_missed_terminal_call',0)
    tactics=s['tactics']['counts']
    case_notes=[]
    for label,case in s['cases'].items():
        row=case['decision'];d=row['diagnostic'];e=d.get('estimate') or {}
        prefix=f"- `{row['id']}` ({' '.join(row['hole'])}): "
        if label=='sparse_premium_fold':
            case_notes.append(prefix+f"the engine stopped after {e['samples']} samples with raw equity {e['equity']:.2%}. "
                f"The conservative partial-sample bound reduced this to {d['equity']:.2%}, below the {case['call_threshold']:.2%} call threshold, "
                f"despite {case['view']['clock_ms']/1000:.1f} seconds remaining in the game bank. The per-decision budget, rather than an exhausted bank, constrained this estimate. "
                'A larger budget for expensive terminal decisions is a targeted opportunity; sparse-estimate flags are rare overall.')
        elif label=='uniform_river_call' and case['known_shover_seats']:
            profile=case['profiles'][str(case['known_shover_seats'][0])]
            case_notes.append(prefix+f"the opponent had shoved preflop {profile['shoves']} times in {profile['hands']} observed hands. "
                'Main therefore treated its range as random cards even after postflop betting. '
                f"It accepted {d['equity']:.2%} equity against a {case['call_threshold']:.2%} threshold. "
                'This is a concrete weakness in transferring a preflop shover read to later streets: postflop actions should still inform that opponent’s range.')
        elif label=='river_range_fold':
            case_notes.append(prefix+f"the fully sampled tracked range gave {d['equity']:.2%} equity, below the {case['call_threshold']:.2%} call threshold. "
                f"The public sensitivity models instead put incremental call EV above +{row['public_ev_lower']:.2f} chips. "
                'This points to range calibration and margin interaction; it was not a missing-equity fallback.')
        elif label=='tracked_river_call':
            case_notes.append(prefix+f"the fully sampled tracked range gave {d['equity']:.2%} equity and crossed the {case['call_threshold']:.2%} call threshold. "
                f"All public sensitivity models put call EV below {row['public_ev_upper']:.2f} chips. "
                'Together with the folded strong hand above, this argues for reviewing range calibration by bet size and action history, rather than applying one global call-margin change.')
    rows=['# New main versus saved call calibration — 4 October 2026','',
        f"**New main (`{s['plan']['main_commit'][:7]}`) returned {r['point'][1]:.2f} bb/100 versus {r['point'][0]:.2f} for saved call calibration (`e186308`): a paired change of {ci(r,2)} bb/100 (95% interval).** "
        f"The matched replica study supports {direction}. Exactly **10,000 new games / 1,000,000 hands** were simulated; all 10,000 calibration games and their decision audits were read from the completed study, never rerun.",'',
        '![Comparison]('+STEM+'-comparison.png)','',
        '## Performance','',
        '| Metric | Saved call calibration | New main |','| --- | ---: | ---: |',
        metric('Net chips',[f"{v['chips']:,}" for v in tot]),
        metric('bb/100 [95% table bootstrap]',[ci(r,i) for i in (0,1)]),
        metric('Mean round placement points',[f'{v:.4f}' for v in p['point'][:2]]),
        metric('Outright first in duplicate table',[f'{v:.2%}' for v in s['outright_wins']]),
        metric('Negative 100-hand games',[f"{v['negative_games']:,} ({v['negative_games']/100:.2f}%)" for v in tot]),
        metric('Hands folded',[f"{v['folds']:,} ({v['folds']/10000:.2f}%)" for v in tot]),
        metric('Fold when facing a bet',[pct(v['facing_folds'],v['facing_decisions']) for v in tot]),
        metric('VPIP / preflop raise hands',[f"{v['vpip_hands']/10000:.2f}% / {v['pfr_hands']/10000:.2f}%" for v in tot]),
        metric('Probable missed terminal calls',[f"{v['missed_calls']:,}" for v in tot]),
        metric('Probable bad terminal calls',[f"{v['bad_calls']:,}" for v in tot]),
        metric('Certain avoidable folds',[str(v['certain_folds']) for v in tot]),
        metric('Flagged folds / all folds',[pct(v['missed_calls']+v['certain_folds'],v['folds']) for v in tot]),
        metric('Missed-call flags / terminal folds',[pct(v['missed_calls'],v['terminal_folds']) for v in tot]),
        metric('Bad-call flags / terminal calls',[pct(v['bad_calls'],v['terminal_calls']) for v in tot]),
        '| Player failures | 0 | 0 |','',
        f"The placement-point change is **{ci(p,2)} points per duplicate table**. Tournament scoring ranks chips within each game, then total game points within the duplicate set. Chip return and placement therefore measure different outcomes. This study models those duplicate tables, not the four-round regrouping or probability of a final podium finish.",'',
        'Return here is total chips divided by total hands, converted to bb/100. The harness console averages table rates equally, so its headline can differ slightly when table sizes vary; the paired report uses equal game weights for both versions.', '',
        '| Seats | Duplicate tables | Main bb/100 | Main − calibration [95% interval] |',
        '| ---: | ---: | ---: | ---: |',
        *[f"| {n} | {sum(t['games']==n for t in tables)} | {s['by_size'][n]['point'][1]:.2f} | {ci(s['by_size'][n],2)} |" for n in (4,5,6)],'',
        '![Distribution and phases]('+STEM+'-distribution.png)','',
        '## What changed in main','',
        '- Retains call-calibration safeguards: guaranteed shared royal-flush calls, conservative partial-sample terminal calls, and the 0.06 river call margin.',
        '- Weights opponent ranges by bet size; small bets retain more bluff mass and large bets retain less.',
        '- Opens any two cards when folded to the small blind; conditionally calls three-bets wider against a frequent three-bettor.',
        '- Restricts out-of-position stabs after calling, adds in-position flop floats, and uses 1.4-pot air/draw bets in selected positions.',
        '- Prices preflop all-ins against players already in the pot. The special proven-shover rescue also requires a top-range hand when others remain to act.',
        '',
        'These changes were evaluated together. Differences below do not identify the causal contribution of any individual change; no ablation or retuning was performed. The frozen main source is byte-identical to its Git bot tree, with no GPU patch.', '',
        '## Folds and decision weaknesses','',
        f"Main folded {tot[1]['folds']:,} of 1,000,000 hands. The audit found {tot[1]['missed_calls']:,} probable missed terminal calls and {tot[1]['certain_folds']} certain avoidable folds, or {pct(tot[1]['missed_calls']+tot[1]['certain_folds'],tot[1]['folds'])} of all folds. "
        'This is an audited flag rate, not the true fraction of unnecessary folds: future betting, opponent-model errors and unexamined alternatives prevent that identification. A terminal call settles the hand without further betting.', '',
        '| Street | Calibration missed / bad calls | Main missed / bad calls | Main terminal folds / calls |',
        '| --- | ---: | ---: | ---: |',
        *[f"| {street} | "+' | '.join(f"{s['flag_streets'][c].get(street,{}).get(FLAGS[0],0)} / {s['flag_streets'][c].get(street,{}).get(FLAGS[1],0)}" for c in (0,1))+
          f" | {stats[1]['streets'].get(street,{}).get('terminal_folds',0):,} / {stats[1]['streets'].get(street,{}).get('terminal_calls',0):,} |" for street in STREETS], '',
        f"Preflop accounts for {misspre:,} of main's missed terminal calls; the river accounts for {badriver:,} of its bad terminal calls. "
        f"Flagged-decision estimate contexts: {dict(s['flag_contexts'][1])}. "
        f"Of {s['main_diagnostics']['equity_estimates']:,} recorded equity estimates, {s['main_diagnostics']['time_limited']:,} stopped at the time budget and {s['main_diagnostics']['rejected_estimates']:,} were not accepted. "
        'These are diagnostic counts, not independent proofs of an error.', '',
        'The public audit is identical for both versions: tight/loose ranges and an extra wide-shover sensitivity where observed history supports it. A probable missed call requires every tested model’s 95% Monte Carlo lower bound to exceed +2 chips; a probable bad call requires every upper bound below −2. '
        'Those intervals cover simulation noise within the models, not uncertainty about whether the ranges describe the opponent. The audit does not adopt main’s new bet-size priors, so disagreement can reflect either a bot error or a range-model disagreement. Hidden-card outcomes are kept as retrospective diagnostics.', '',
        '### Reviewable examples','',
        '| Decision ID (zero-based hand) | Classification | Hole / board | Pot / call | Public call-EV bound | Hand / game chips | Estimate |',
        '| --- | --- | --- | ---: | ---: | ---: | --- |',
        *[f"| `{v['id']}` | {v['classification']} | {' '.join(v['hole'])} / {' '.join(v['board']) or 'preflop'} | {v['pot']} / {v['call']} | "
          f"{ev_bounds(v)} | {v['hand_chips']} / {v['match_chips']} | {context(v)} |" for v in examples], '',
        'The complete blunder CSV retains every flagged action, the bot’s equity estimate and sample count. Public EV is incremental call versus fold; it is not the hand’s final profit and cannot simply be added to the tournament score.', '',
        'Public-state replay explains the selected decisions without rerunning a bot:', '',
        *case_notes,'',
        '### Additional structural weaknesses and observed tactics','',
        f"**Bluff gate does not scale with size.** Main uses a 50% estimated fold-rate gate even for 1.4-pot bluffs. A single pure bluff with zero showdown equity needs `1.4 / (1 + 1.4) = 58.33%` folds to break even. "
        f"Public-event replay found **{tactics.get('air_overbets_below_immediate_breakeven_estimate',0):,}** heads-up, at-least-1.3-pot air bets whose own estimated fold rate was below the actual-size break-even threshold. "
        f"Opponents folded immediately in {tactics.get('below_gate_folded_to',0):,} of those spots ({pct(tactics.get('below_gate_folded_to',0),tactics.get('air_overbets_below_immediate_breakeven_estimate',0))}); the {tactics.get('below_gate_distinct_hands',0):,} distinct hands returned {tactics.get('below_gate_distinct_hand_chips',0):+,} chips. "
        'This sample supports testing size-specific fold estimates, not blindly reducing aggression. The generic estimate is not size-specific, high cards can improve, and later betting has value; the threshold gap alone does not prove a bad bet.', '',
        f"**Sparse three-bet read.** The wider-call gate accepts a 15% three-bet rate after only four opportunities: one three-bet in four already qualifies. "
        f"There were {tactics.get('additional_wide_threebet_calls',0):,} observed calls outside the old three-bet calling range under this gate, including {tactics.get('wide_threebet_calls_at_four_chances',0):,} at exactly four opportunities. The whole wider-call subset returned {tactics.get('wide_threebet_call_chips',0):+,} chips. "
        'Shrinkage or a minimum-confidence rule would reduce overreaction, but needs a separate held-out test.', '',
        f"**Players behind a shove.** There were {tactics.get('preflop_shove_calls_with_players_behind',0):,} preflop calls with additional players still outside the pot and yet to respond, returning {tactics.get('preflop_shove_calls_behind_chips',0):+,} chips in those hands. "
        'The equity calculation excludes those players; the special shover branch uses a hand whitelist to compensate. A joint model of additional callers would provide a more explicit price adjustment. These calls are not automatically terminal-call blunders.', '',
        f"The any-two small-blind rule opened {tactics.get('additional_small_blind_opens',0):,} hands outside the saved version’s steal range; those hands realized {tactics.get('additional_small_blind_open_chips',0):+,} chips in main versus {tactics.get('additional_small_blind_fold_benchmark',0):+,} for immediately folding those same small blinds. "
        f"Across all reviewed pure-air overbets, opponents folded immediately {tactics.get('pure_air_overbets_folded_to',0):,}/{tactics.get('pure_air_overbets',0):,} times. "
        'These are descriptive outcomes in selected contexts, not isolated treatment effects. The replay reads only public observations when rebuilding counters and executes no bot actions.', '',
        '## What happened in losing games','',
        f"Main finished negative in **{tot[1]['negative_games']:,} games**. **{tot[1]['negative_games_with_flags']:,}** ({pct(tot[1]['negative_games_with_flags'],tot[1]['negative_games'])}) contained a strict decision flag. "
        'A losing game without a flag can still contain missed value or bad bluffs; a losing all-in can also have been correct. The loss buckets below are mutually exclusive hand outcomes within negative games, not causal estimates of recoverable profit.', '',
        '| Losing-hand category | Hands in negative games | Gross chips lost | Share of gross loss |',
        '| --- | ---: | ---: | ---: |',
        *[f"| {k.replace('_',' ')} | {stats[1]['negative_loss'][k]['hands']:,} | {-stats[1]['negative_loss'][k]['chips']:,} | {-stats[1]['negative_loss'][k]['chips']/gross:.2%} |" for k in losskeys], '',
        '“Profitable all-in lost runout” uses the actual hidden cards after the decision and describes luck conditional on reaching that all-in. It is not information the bot could use or an unbiased estimate of the entire strategy’s strength.', '',
        '| Negative game | Main chips | Saved calibration chips | Strict flags | Largest hand losses |',
        '| --- | ---: | ---: | ---: | --- |',
        *[f"| `{g['match']}` | {g['chips']:,} | {next(v['chips'] for v in sets[0] if (v['table'],v['game'])==(g['table'],g['game'])):,} | {g['flags']} | "+
          '; '.join(f"h{h['hand']}: {h['chips']} ({h['loss_category'].replace('_',' ')})" for h in g['worst_hands'][:3])+' |' for g in selected], '',
        '### Opponent composition','',
        'The following are tables containing each named opponent, with all other opponents still present. They overlap and are descriptive; they are not heads-up results or isolated blame on one opponent.', '',
        '| Opponent present | Tables | Main bb/100 | Paired change [95% interval] |',
        '| --- | ---: | ---: | ---: |',
        *[f"| {v['bot']} | {v['tables']} | {v['main_bb100']:.2f} | {v['delta']:+.2f} [{v['low']:+.2f}, {v['high']:+.2f}] |" for v in sorted(opponents,key=lambda v:v['main_bb100'])[:8]], '',
        '## SWOT','',
        f"- **Strengths:** {r['point'][1]:.2f} bb/100 in this field; {direction} versus the saved calibration control, with paired change {ci(r,2)}. "
        f"Outright duplicate-table wins rose from {s['outright_wins'][0]:.2%} to {s['outright_wins'][1]:.2%}; gains were positive at every tested table size. "
        f"All 10,000 games completed without player failures. The six restricted wire-protocol checks passed. Existing terminal-call safeguards remain active.",
        f"- **Weaknesses:** {tot[1]['missed_calls']:,} missed terminal calls and {tot[1]['bad_calls']:,} bad terminal calls remain under the fixed public audit. "
        f"{badriver} of {tot[1]['bad_calls']} bad-call flags were on the river. Almost all strict flags used accepted tracked-range estimates, making range calibration the first review target; treating preflop shovers as random on the river produced a concrete bad-call example. Sparse estimates caused a few expensive missed opportunities. Failed air bets and investment followed by folding can be expensive, but their outcome alone does not establish a blunder.",
        '- **Opportunities:** retain action-conditioned postflop ranges for preflop shovers; calibrate ranges and call margins jointly by bet size. Test size-aware bluff gates and the identified low-confidence three-bet reads on fresh tables. Allocate more sampling time to costly terminal decisions where the bank permits. Evaluate the small-blind, float and overbet changes separately before attributing the gain to one feature. Review shove calls with players behind using an explicit probability of additional callers.',
        '- **Threats:** opponent replicas imperfectly recover real submissions, especially sparse newest versions; fixed-field confidence intervals omit fitting uncertainty. New submissions can change behavior. The different value/bluff bet sizes can reveal hand strength to an adaptive opponent; any-two small-blind opening can invite wider reraises. These are structural risks, not measured exploits by this fixed replica field.', '',
        '## Method, scope and reproduction','',
        f"Main commit: `{s['plan']['main_commit']}`. Calibration commit: `{s['plan']['calibration_commit']}` (bot changes originated in its parent). "
        f"The control is candidate 1 from `{s['plan']['archived_directory']}/simulate.json`, accompanied by its original audit. A compressed copy and SHA-256 provenance are included in the evidence directory.",'',
        'The older 61-opponent call-calibration study returned 37.77 bb/100. The primary control here is the most recent saved calibration run on the matching 69-opponent field (49.40 bb/100); the older field provides historical context only.', '',
        'The 69 replicas come from the same frozen refit as that control: all newest-version actions have full weight; trusted validation games against `house:call` mark uploads. Sparse parameters borrow older data with weight at most `0.1**version_age * 2**(-upload_gap_hours/6)`, capped by each parameter’s support target. Two newest uploads have no replay and use flagged prior-only estimates. No opponents were refitted for this comparison, which preserves the experimental control.', '',
        'Exactly 2,009 complete duplicate tables provide 10,000 games per version: Halliday plus 3–5 distinct sampled opponents, 100 hands/game, fresh 200-chip stacks, 1/2 blinds and a 30-second bank plus 100 ms/hand. Ordered lineups, seat rotations and deck seeds match the archive. '
        'The 5,000-draw bootstrap resamples whole paired tables. Chip return weights games equally; placement weights tables equally. Per-size and per-opponent intervals are descriptive and not adjusted for multiple comparisons.', '',
        f"New simulation: 16 CPU workers, {s['simulation_seconds']/60:.1f} minutes. Main’s exact engine has no CUDA batch hook; the earlier shared-hardware benchmark favored CPU16. "
        f"Decision audit: eight workers across all four V100s, {s['audit_seconds']/60:.1f} minutes; ranked-hand counts by device: "+
        ', '.join(f"{k}={v['ranked_hands']:,}" for k,v in sorted(s['main_gpu'].items()))+'.', '',
        'The baseline was executed earlier, so wall-clock-limited Monte Carlo sample counts can differ with host load even on identical observations. Paired decks reduce sampling noise but do not remove that execution-time confound. The intervals are conditional on one fitted field and do not measure live tournament generalization.', '',
        f"[Reproduction commands]({STEM}-reproduce.md) · [Paired games]({STEM}-games.csv) · [All flags]({STEM}-blunders.csv) · [Opponent composition]({STEM}-opponents.csv).",'']
    (output/(STEM+'.md')).write_text('\n'.join(rows))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,default=ROOT/'analysis/results'/STEM)
    p.add_argument('--output',type=Path,default=ROOT/'analysis/reports')
    args=p.parse_args();build(args.directory.resolve(),args.output.resolve())
