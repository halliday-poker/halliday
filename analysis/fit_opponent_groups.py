"""Fit small public-behavior groups; evaluate identification on held-out games."""
import argparse
from bisect import bisect_right
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
from pprint import pformat
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'vendor/macpoker-src'))
from bot.group_observer import GroupObserver, FEATURES
from bot.groups import FEATURE_WEIGHTS, posterior, confidence
from bot.params import DEFAULT_PARAMS
from opponent_model.validation import match_split

# Fit one common set of counter adjustments on the calibrated reference. The
# main-based variant shifts the river target together with its base margin.
DEFAULT_PARAMS=dict(DEFAULT_PARAMS,range_call_margin_river=.06)

CHECKPOINTS=(5,10,15,20,30,50,75,100)


def dump(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def extract(run):
    fit=json.loads((run/'fit/runtime-fit.json').read_text())
    matches=json.loads((run/'input/source/matches.json').read_text())
    names=sorted(n for n in fit['bots'] if n!='Halliday')
    bots={n:i for i,n in enumerate(names)}
    by_id={m['id']:(i,m) for i,m in enumerate(matches)}
    splits=match_split(matches)
    cuts={name:sorted({m['at'] for m in matches if m.get('kind')=='validation'
          and len(m['names'])==2 and name in m['names'] and 'house:call' in m['names']
          and isinstance(m.get('at'),(int,float)) and m['at']>1e11}) for name in names}
    observers={}; output=[];counts=[];current=None;events=[]

    def consume(key,events):
        mid,hand=key; mi,meta=by_id[mid];time=meta.get('at')
        if not isinstance(time,(float,int)) or time<=1e11:return
        eligible=[n for n in meta['names'] if n in bots]
        if not eligible:return
        actions=[e for e in events if 'action' in e]
        shift=(actions[0]['seat']-meta['names'].index(actions[0]['bot']))%len(meta['names'])
        seated=[meta['names'][(s-shift)%len(meta['names'])] for s in range(len(meta['names']))]
        obs=observers.setdefault(mid,GroupObserver())
        obs.on_hand_start(dict(players=seated,stacks=[200]*len(seated),button=0))
        folded=set();board=[]
        for e in events:
            if e.get('event')=='board':
                board=list(e['board']);obs.on_street(dict(street=e['street'],board=board))
            elif 'action' in e:
                obs.on_action({k:e[k] for k in ('seat','street','action','amount')})
                if e['action']=='fold':folded.add(e['seat'])
        end=events[-1]
        assert end['event']=='hand_end'
        # Spectator rows contain ALL hole cards. Only un-folded players in an
        # actual showdown become public; never expose the others to the observer.
        revealed={str(s):end['holes'][n] for s,n in enumerate(seated)
                  if s not in folded and n in end.get('holes',{})} if len(seated)-len(folded)>1 else {}
        obs.on_hand_end(dict(revealed=revealed));obs.learn_pending()
        for name in eligible:
            assert obs.hands[name]==hand+1
            if hand+1 not in CHECKPOINTS and not (meta.get('kind')=='validation' and hand==1):continue
            age=len(cuts[name])-bisect_right(cuts[name],time)
            start=cuts[name][-age-1] if age<len(cuts[name]) else time
            gap=max(0,(cuts[name][-1]-start)/3_600_000)
            output.append((mi,bots[name],hand+1,len(seated),int(splits[mi]),age,gap))
            counts.append([list(pair) for pair in obs.counts[name]])

    digest=sha256()
    with (run/'input/source/actions.jsonl').open('rb') as stream:
        for raw in stream:
            digest.update(raw);event=json.loads(raw);key=event['match'],event['hand']
            if current is not None and key!=current:
                consume(current,events);events=[]
                if current[0]!=key[0]:observers.pop(current[0],None)
            current=key;events.append(event)
    if current:consume(current,events)
    assert digest.hexdigest()==fit['source_sha256']
    meta=dict(bots=names,matches=matches,features=FEATURES,checkpoints=CHECKPOINTS,
              fields=['match','bot','hands','seats','split','version_age','upload_gap_hours'],
              actions_sha256=digest.hexdigest(),observer_sha256=sha256((ROOT/'bot/group_observer.py').read_bytes()).hexdigest(),
              scope='Only public actions and legal showdown reveals; per-game resets and player-id seat mapping. No hidden holes or future events enter prefixes.')
    np.savez_compressed(run/'group-prefixes.npz',metadata=np.asarray(json.dumps(meta)),
                        rows=np.asarray(output,dtype=np.float64),counts=np.asarray(counts,dtype=np.float32))
    print(json.dumps(dict(prefixes=len(output),bots=len(names),sha256=digest.hexdigest())),flush=True)


def kmeans(x,k,seed=548):
    best=None
    for attempt in range(32):
        rng=np.random.default_rng(seed+attempt)
        centers=x[rng.choice(len(x),k,replace=False)].copy()
        for _ in range(80):
            distances=((x[:,None,:]-centers[None,:,:])**2).sum(2)
            labels=distances.argmin(1)
            newer=np.array([x[labels==j].mean(0) if (labels==j).any() else x[distances.min(1).argmax()] for j in range(k)])
            if np.allclose(newer,centers):break
            centers=newer
        cost=((x-centers[labels])**2).sum()
        if best is None or cost<best[0]:best=(cost,centers,labels)
    return best[1:]


def signatures(rows,counts,nbots,split=None,seat_range=None):
    final=rows[:,2]==100
    if seat_range is not None:final&=(rows[:,3]>=seat_range[0])&(rows[:,3]<=seat_range[1])
    if split is not None:final&=rows[:,4]==split
    totals=np.zeros((nbots,len(FEATURES),2));games=np.zeros(nbots)
    # Newest games always retain full weight; historical games fill only sparse
    # feature opportunities and are discounted by upload age and elapsed time.
    for b in range(nbots):
        idx=np.flatnonzero(final&(rows[:,1]==b))
        newest=idx[rows[idx,5]==0]
        totals[b]=counts[newest].sum(0)
        games[b]=len(newest)
        for age in sorted(set(rows[idx,5])-{0}):
            older=idx[rows[idx,5]==age]
            version_counts=counts[older].sum(0)
            target=np.array([200,200,100,200,100,100,100,50,30])
            remaining=np.maximum(0,target-totals[b,:,1])
            cap=.1**age*2**(-rows[older,6].max()/6)
            weight=np.minimum(cap,remaining/np.maximum(1,version_counts[:,1]))
            totals[b]+=version_counts*weight[:,None]
    return totals,games


def counter(mean,style):
    """Bounded target settings; prototype confidence controls their runtime use."""
    clamp=lambda v,lo,hi:min(hi,max(lo,float(v)))
    vpip,pfr,threebet,shove,fold,bet,raising,large,weak=mean
    bluff=style['bluff'];sticky=style['stickiness']
    prior=dict(range_prior_vpip=clamp(vpip,.08,.9),range_prior_pfr=clamp(pfr,.03,vpip),
               range_prior_threebet=clamp(threebet,.01,.4),
               range_bluff_floor=clamp(DEFAULT_PARAMS['range_bluff_floor']*(.6+2*bluff),.04,.45))
    target=dict(prior,bluff_frequency=clamp((fold-.25)/.4,.05,1),
        value_threshold=clamp(.68-.07*sticky-.04*bluff,.56,.69),
        raise_threshold=clamp(.89-.07*bluff,.8,.92),
        cbet_pot_fraction=clamp(.72+.48*(1-fold),.72,1.15),
        late_pot_fraction=clamp(.72+.48*(1-fold),.72,1.15))
    for street in ('flop','turn','river'):
        for prefix in ('','range_'):
            name=prefix+'call_margin_'+street
            target[name]=clamp(DEFAULT_PARAMS[name]+.035*(.25-bluff),.005,.12)
    return prior,target


def fit_groups(run):
    with np.load(run/'group-prefixes.npz',allow_pickle=False) as z:
        meta=json.loads(str(z['metadata']));rows=z['rows'];counts=z['counts']
    assert meta['observer_sha256']==sha256((ROOT/'bot/group_observer.py').read_bytes()).hexdigest()
    refit=json.loads((run/'fit/runtime-fit.json').read_text())
    names=meta['bots'];nbots=len(names)
    training,games=signatures(rows,counts,nbots,split=0)
    reliable=(games>=2)&(training[:,0,1]>=200)
    rates=(training[:,:,0]+1)/(training[:,:,1]+2)
    # Observability matters: unseen showdowns cannot reliably define an early group.
    spread=np.maximum(.08,rates[reliable].std(0))
    availability=np.minimum(1,training[:,:,1]/np.array([100,100,30,100,30,30,30,20,20]))
    weights=np.asarray(FEATURE_WEIGHTS)*availability[reliable].mean(0)
    transform=np.sqrt(weights)/spread
    x=rates*transform
    options=[];candidates={}
    validation=np.flatnonzero((rows[:,4]==1)&(rows[:,5]==0)&(rows[:,3]>=4)&(rows[:,3]<=6)
                             &np.isin(rows[:,2],[5,10,20])&reliable[rows[:,1].astype(int)])

    def prototypes(labels,k,statistics,split):
        stats_rates=(statistics[:,:,0]+1)/(statistics[:,:,1]+2)
        contexts={name:signatures(rows,counts,nbots,split=split,seat_range=seats)[0]
                  for name,seats in [('short',(2,3)),('tournament',(4,6)),('full',(7,9))]}
        groups=[]
        for j in range(k):
            members=np.flatnonzero((labels==j)&reliable)
            if not len(members):return None
            center=stats_rates[members].mean(0)
            variance=stats_rates[members].var(0)+np.mean(center*(1-center)/(statistics[members,:,1]+3),axis=0)
            concentration=np.clip(center*(1-center)/np.maximum(variance,.0005)-1,3,80)
            styles={p:float(np.mean([refit['bots'][names[b]]['style'][p] for b in members]))
                    for p in refit['bots'][names[members[0]]]['style']}
            uncertainty={p:float(np.var([refit['bots'][names[b]]['style'][p] for b in members])+
                np.mean([refit['bots'][names[b]]['estimate']['parameters'][p]['bootstrap_variance'] for b in members])) for p in styles}
            prior,target=counter(center,styles)
            # Uncertain recovered parameters imply a smaller exploit, even if
            # the observable behavioral group itself is identified confidently.
            reliability=1/(1+2*np.sqrt(uncertainty['bluff']+uncertainty['stickiness']))
            target={key:float(DEFAULT_PARAMS[key]+reliability*(value-DEFAULT_PARAMS[key])) for key,value in target.items()}
            prior={key:target[key] for key in prior}
            context_shapes={}
            for name,stat in contexts.items():
                local=stat[members]
                context_rates=(local[:,:,0]+20*center)/(local[:,:,1]+20)
                mean=context_rates.mean(0)
                variance=context_rates.var(0)+np.mean(center*(1-center)/(local[:,:,1]+20),axis=0)
                # Without context data, preserve the broad group uncertainty.
                variance=np.maximum(variance,center*(1-center)/(concentration+1))
                context_shapes[name]=dict(mean=mean.clip(.005,.995).tolist(),
                    concentration=np.clip(mean*(1-mean)/np.maximum(variance,.0005)-1,3,80).tolist())
            label=('active_pressure' if center[5]>.5 else 'sticky_passive' if center[4]<.35
                   else 'frequent_folders' if center[4]>.6 else 'wide_passive' if center[0]>.3 else 'selective_passive')
            groups.append(dict(name=f'{label}_{j+1}',prior=float((len(members)+1)/(reliable.sum()+k)),
                mean=center.clip(.005,.995).tolist(),concentration=concentration.tolist(),
                range_prior=prior,counter=target,adaptive=styles['adaptive'],
                contexts=context_shapes,members=[names[b] for b in members],style=styles,
                parameter_variance=uncertainty,counter_reliability=float(reliability)))
        return groups

    for k in (2,3,4,5,6,7):
        centers,local=kmeans(x[reliable],k)
        labels=((x[:,None,:]-centers[None,:,:])**2).sum(2).argmin(1)
        groups=prototypes(labels,k,training,0)
        if groups is None:continue
        for temperature in (.5,1.,1.5,2.):
            probs=np.asarray([posterior(counts[i],groups,temperature,rows[i,3]) for i in validation])
            truth=labels[rows[validation,1].astype(int)]
            predicted=probs.argmax(1);pmax=probs.max(1)
            for threshold in (.6,.7,.8):
                chosen=pmax>=threshold
                accuracy=float((predicted[chosen]==truth[chosen]).mean()) if chosen.any() else 0.
                coverage=float(chosen.mean())
                # Errors cost more than an abstention; fewer groups break ties.
                utility=float(np.mean(chosen*((predicted==truth)*1.0-(predicted!=truth)*3.0)))-.004*k
                entry=dict(groups=k,temperature=temperature,threshold=threshold,
                    validation_accuracy=accuracy,validation_coverage=coverage,utility=utility)
                options.append(entry);candidates[k]=groups,labels,centers
    selected=max(options,key=lambda e:e['utility'])
    groups,labels,centers=candidates[selected['groups']]
    config={k:selected[k] for k in ('temperature','threshold')}
    evaluations=[]
    for split in (1,2):
        for h in CHECKPOINTS:
            idx=np.flatnonzero((rows[:,4]==split)&(rows[:,5]==0)&(rows[:,2]==h)
                              &(rows[:,3]>=4)&(rows[:,3]<=6)&reliable[rows[:,1].astype(int)])
            probs=np.asarray([posterior(counts[i],groups,config['temperature'],rows[i,3]) for i in idx])
            truth=labels[rows[idx,1].astype(int)]
            pred=probs.argmax(1);pmax=probs.max(1)
            active=np.array([confidence(p,groups,h,config['threshold'])>0 for p in probs])
            evaluations.append(dict(split=['train','validation','test'][split],hands=h,prefixes=len(idx),
                classified=int(active.sum()),coverage=float(active.mean()),
                accuracy=float((pred[active]==truth[active]).mean()) if active.any() else None,
                all_accuracy=float((pred==truth).mean()),
                calibration=[dict(low=lo,high=lo+.1,count=int(((pmax>=lo)&(pmax<lo+.1)).sum()),
                    correct=int(((pmax>=lo)&(pmax<lo+.1)&(pred==truth)).sum())) for lo in (.5,.6,.7,.8,.9)]))
    # Preserve honest held-out diagnostics, then use all newest observations to
    # refine beta distributions for the fixed group definitions before simulation.
    all_stats,all_games=signatures(rows,counts,nbots)
    final=prototypes(labels,len(groups),all_stats,None)
    records=[]
    for b,name in enumerate(names):
        probs=posterior(all_stats[b].tolist(),final,config['temperature'])
        games_mask=(rows[:,1]==b)&(rows[:,2]==100)&(rows[:,5]==0)
        local=counts[games_mask]
        game_rates=np.divide(local[:,:,0],local[:,:,1],out=np.full_like(local[:,:,0],np.nan),where=local[:,:,1]>0)
        dispersion={feature:(float(np.var(game_rates[np.isfinite(game_rates[:,j]),j],ddof=1))
                    if np.isfinite(game_rates[:,j]).sum()>1 else None) for j,feature in enumerate(FEATURES)}
        records.append(dict(bot=name,group=int(labels[b]),training_games=int(games[b]),
            newest_games=int(all_games[b]),reliable_label=bool(reliable[b]),posterior=probs,
            newest_between_game_rate_variance=dispersion,
            parameter_variances={p:v['bootstrap_variance'] for p,v in refit['bots'][name]['estimate']['parameters'].items()}))
    report=dict(source_sha256=meta['actions_sha256'],selected=selected,selection_grid=options,
        validation_groups=groups,groups=final,opponents=records,evaluation=evaluations,
        features=FEATURES,feature_weights=FEATURE_WEIGHTS,config=config,
        scope='Group definitions and beta priors trained on training games; K/temperature/threshold selected on validation prefixes. Test uses only newest held-out games with >=200 training hands. Final priors refit on all newest data with discounted sparse historical support. Group labels are behavioral clusters, not recovered bot source or known true classes.')
    dump(run/'groups-fit.json',report)
    compact=[{k:v for k,v in group.items() if k not in ('members','style','parameter_variance','counter_reliability')} for group in final]
    text='"""Generated public-behavior priors; regenerate with analysis/fit_opponent_groups.py."""\n'
    text+=f'INPUT_SHA256 = {meta["actions_sha256"]!r}\nFEATURES = {FEATURES!r}\n'
    text+=f'CONFIG = {config!r}\nGROUPS = {pformat(compact,width=105,sort_dicts=False)}\n'
    (ROOT/'bot/group_priors.py').write_text(text)
    print(json.dumps(dict(selected=selected,test=[v for v in evaluations if v['split']=='test']),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,default=Path('analysis/results/opponent-groups-20261004'))
    p.add_argument('--step',choices=['extract','fit'],required=True)
    args=p.parse_args()
    (extract if args.step=='extract' else fit_groups)(args.directory.resolve())
