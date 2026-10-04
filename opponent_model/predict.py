"""Exact marginal action probabilities of the original ParamBot scaffold."""
import numpy as np
from sparring.competitors.policy import COL,legal_actions


def param_probabilities(rows, style, contamination=.05):
    c=lambda name:rows[:,COL[name]]
    p={key:np.full(len(rows),value,dtype=float) for key,value in style.items()}
    if style['adaptive']:
        p['stickiness']=np.clip(p['stickiness']+.15*c('agg_high'),0,1)
        p['bluff']=p['bluff']-.05*c('agg_high')
        p['bluff']=np.where(c('fold_high'),p['bluff']+.15,np.where(c('fold_low'),p['bluff']*.3,p['bluff']))
        p['bluff']=np.clip(p['bluff'],0,1)
        p['cbet']=np.clip(p['cbet']+.15*c('fold_high'),0,1)
    pre=c('street')==0;facing=c('facing')>0;can=c('can_raise')>0
    pct=c('pct');nraise=c('pre_raises')
    opened=pct<p['vpip']
    raises=np.where(nraise==0,opened*(pct<p['pfr'])*(1-p['limp']),
                    np.where(nraise==1,pct<p['threebet'],pct<p['threebet']*.35)).astype(float)
    calls=np.where(nraise==0,opened,np.where(nraise==1,
                    (pct<p['vpip']*(.3+.5*p['stickiness']))&(c('call')<=.3*c('stack')),
                    pct<p['threebet']*(.6+p['stickiness'])))
    st=np.nan_to_num(c('strength'));draw=c('draw')
    value=st>=.8-.3*p['aggression'];continuation=c('cbet')*p['cbet']
    semi=draw*p['aggression']*.6
    free_raise=np.where(value,1,continuation+(1-continuation)*(semi+(1-semi)*p['bluff']*.5))
    value_raise=(st>=.92-.12*p['aggression'])*(.4+.6*p['aggression'])
    facing_raise=value_raise+(1-value_raise)*(c('street')!=3)*p['bluff']*.15
    raises=np.where(pre,raises,np.where(facing,facing_raise,free_raise))
    odds=c('call')/np.maximum(1,c('pot')+c('call'))
    post_call=st+.1*draw*(c('street')!=3)>=odds+.2-.3*p['stickiness']
    calls=np.where(pre,calls,post_call)
    prob=np.zeros((len(rows),4))
    prob[:,3]=raises*can
    prob[:,0]=facing*(1-raises)*(1-calls)
    prob[:,2]=facing*((1-raises)*calls+raises*(~can))
    prob[:,1]=(~facing)*(1-prob[:,3])
    allowed=legal_actions(rows)
    prob=(1-contamination)*prob+contamination*allowed/allowed.sum(1,keepdims=True)
    return prob/prob.sum(1,keepdims=True)


def param_size(rows,style):
    c=lambda name:rows[:,COL[name]]
    pre=c('street')==0
    aggression=np.full(len(rows),style['aggression'])
    cbet=np.clip(style['cbet']+.15*style['adaptive']*c('fold_high'),0,1)*c('cbet')
    value=np.nan_to_num(c('strength'))>=.8-.3*aggression
    # Exact size is randomized and clipped; this is a deterministic conditional
    # central target for common-MAE comparison, not its likelihood.
    nominal=c('pot')*style['size']*np.where(value,1,1-.2*cbet)
    post=np.where(c('facing'),3*c('top'),nominal)
    before=np.where(c('pre_raises')==0,5+2*c('limpers'),
                    np.where(c('pre_raises')==1,3*c('top'),np.where(c('top')>60,c('maximum'),2.3*c('top'))))
    return np.clip(np.where(pre,before,post),c('minimum'),c('maximum'))
