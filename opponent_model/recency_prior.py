"""Opportunity-specific priors with tenfold decay per older upload version."""
import numpy as np

from .data import COL
from .fit import BotModel,PARAMETERS

TARGETS={'vpip':200,'pfr':200,'threebet':100,'limp':200,'aggression':100,
         'cbet':50,'bluff':100,'stickiness':100,'size':50,'adaptive':200}
DECAY=.1
HALF_LIFE_HOURS=6.


def opportunities(rows):
    c=lambda name:rows[:,COL[name]]
    pre=c('street')==0;known=np.isfinite(c('pct'));raised=c('action')==3
    free=pre&known&(c('pre_raises')==0)
    post=(~pre)&np.isfinite(c('strength'))&~c('facing').astype(bool)&c('can_raise').astype(bool)
    stick=(~pre)&np.isfinite(c('strength'))&c('facing').astype(bool)&c('can_raise').astype(bool)&~raised
    return dict(vpip=free&c('facing').astype(bool),pfr=free&c('can_raise').astype(bool),
        limp=free&c('can_raise').astype(bool),threebet=pre&known&(c('pre_raises')==1)&c('can_raise').astype(bool),
        aggression=post,cbet=post&c('cbet').astype(bool),bluff=post,stickiness=stick,
        size=post&raised&~c('cbet').astype(bool),adaptive=post|stick)


def age_rows(rows,matches,uploads):
    cuts=sorted(set(uploads))
    times=np.asarray([matches[int(m)].get('played_at') or np.nan for m in rows[:,COL['match']]])
    age=len(cuts)-np.searchsorted(cuts,times,side='right')
    age[~np.isfinite(times)]=-1
    return age


def version_time_gaps(rows,matches,uploads):
    cuts=sorted(set(uploads))
    times=[matches[int(m)].get('played_at') for m in rows[:,COL['match']]]
    earliest=min(t for t in times if t is not None)
    return {age:max(0,(cuts[-1]-(cuts[-age-1] if age<len(cuts) else earliest))/3600)
            for age in range(1,len(cuts)+1)}


def prior_weights(rows,ages,gap_hours=None):
    """Newest observations all retain weight one; older ones fill sparse contexts."""
    masks=opportunities(rows);weights={};evidence={}
    for parameter in PARAMETERS:
        support=masks[parameter];count=int((support&(ages==0)).sum());remaining=max(0,TARGETS[parameter]-count)
        w=(ages==0).astype(float);versions=[]
        for age in sorted(set(ages[ages>0])):
            if remaining<=0:break
            local=ages==age;opportunities_count=int((local&support).sum())
            if not opportunities_count:continue
            gap=(gap_hours or {}).get(int(age),0)
            age_discount=DECAY**int(age);time_discount=2**(-gap/HALF_LIFE_HOURS)
            scale=min(age_discount*time_discount,remaining/opportunities_count)
            w[local]=scale;effective=scale*opportunities_count;remaining-=effective
            versions.append(dict(age=int(age),gap_hours=gap,age_discount=age_discount,time_discount=time_discount,
                                 raw_opportunities=opportunities_count,weight=scale,effective_opportunities=effective))
        weights[parameter]=w
        effective=count+sum(v['effective_opportunities'] for v in versions)
        evidence[parameter]=dict(latest_opportunities=count,target_opportunities=TARGETS[parameter],
            older_versions=versions,effective_opportunities=effective,
            status='latest_sufficient' if count>=TARGETS[parameter] else
                   'older_prior_used' if effective>=TARGETS[parameter]-1e-8 else 'still_sparse',
            warning='Opportunity targets are precision heuristics, not guarantees of accurate recovery.')
    # A shared action head gets the largest relevant prior weight for a row;
    # scaffold parameters retain separate likelihood weights below.
    joint=(ages==0).astype(float)
    for parameter,w in weights.items():joint=np.maximum(joint,w*masks[parameter])
    return weights,joint,evidence


def scaffold_fit(rows,hands,ages,compute,gap_hours=None):
    weights,_,evidence=prior_weights(rows,ages,gap_hours)
    model=BotModel(rows,hands,compute)
    match_ids=rows[:,COL['match']].astype(int)
    match_ages={m:int(ages[np.flatnonzero(match_ids==m)[0]]) for m in model.matches}
    rng=np.random.default_rng(38251)
    # Resample whole matches within each version, preserving newest support.
    bootstrap=np.ones((301,len(model.matches)))
    bootstrap[1:]=0
    for age in sorted(set(match_ages.values())):
        index=np.asarray([j for j,m in enumerate(model.matches) if match_ages[m]==age])
        sampled=rng.integers(len(index),size=(300,len(index)))
        for draw,values in enumerate(sampled,1):bootstrap[draw,index]=np.bincount(values,minlength=len(index))
    draws=[]
    for parameter in PARAMETERS:
        per_match=np.asarray([weights[parameter][np.flatnonzero(match_ids==m)[0]] for m in model.matches])
        values,_=model.fit_weights(compute.array(bootstrap*per_match[None,:]))
        draws.append(values[:,PARAMETERS.index(parameter)].cpu().numpy())
    values=np.column_stack(draws)
    values[:,1]=np.minimum(values[:,1],values[:,0]);values[:,2]=np.minimum(values[:,2],values[:,1])
    estimates={p:dict(estimate=float(values[0,j]),confidence_interval=np.quantile(values[1:,j],[.025,.975]).tolist(),
                     prior=evidence[p]) for j,p in enumerate(PARAMETERS)}
    style={p:(int(values[0,j]) if p=='adaptive' else float(values[0,j])) for j,p in enumerate(PARAMETERS)}
    return dict(surrogate_style=style,parameters=estimates,prior=evidence,
        interval_scope='Whole-match bootstrap stratified by version, conditional on tenfold age decay and fixed support targets; joint preflop bounds enforced.')
