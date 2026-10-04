"""Whole-match predictive comparisons and parallel CUDA replica training.

python -m opponent_model.behavior prepare --directory analysis/results/refresh-20261004
python -m opponent_model.behavior train --directory analysis/results/refresh-20261004
"""
from collections import Counter,defaultdict
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import json
import multiprocessing as mp
from pathlib import Path
import time

import numpy as np
import torch
from torch import nn

from .compute import Compute
from .data import COL,Dataset,load_cache
from .pipeline import analyze
from .predict import param_probabilities,param_size
from .validation import match_split,upload_events,epoch_map
from sparring.param import ARCHETYPES
from sparring.competitors.policy import features,legal_actions,size_labels,size_targets

MODES=('none','upload','placebo','change')


def prepare(directory,devices):
    data=load_cache(directory/'context-features.npz')
    if data.audit.get('legacy_context_missing'):
        raise ValueError('Reconstruct richer public contexts before training')
    bots=sorted(data.observations)
    split=match_split(data.matches)
    events,validation_audit=upload_events(data.matches,json.loads((directory/'validation-meta.json').read_text()))
    training_obs,training_hands,kept={},{},{}
    for bot in bots:
        rows=data.observations[bot]
        allowed={i for i,m in enumerate(data.matches) if m['kind']=='ladder' or bot=='house:call'}
        keep=np.isin(rows[:,COL['match']],list(allowed))
        kept[bot]=rows[keep]
        indices=rows[:,COL['match']].astype(int)
        selected={m:v for m,v in data.hands[bot].items() if m in allowed and split[m]==0}
        if selected:
            training_obs[bot]=rows[keep&(split[indices]==0)]
            training_hands[bot]=selected
    training=Dataset(data.matches,training_obs,training_hands,data.audit|{'partition':'training complete matches only'})
    compute=[Compute(f'cuda:{d}',batch_size=128,memory_limit_mib=768) for d in devices]
    baseline=analyze(training,compute,bootstrap=100,permutations=4999,
                     progress=lambda phase,bot:print(json.dumps(dict(phase=phase,bot=bot)),flush=True))
    (directory/'training-baseline.json').write_text(json.dumps(baseline,indent=2))
    all_rows,bot_index,base_pred,base_size=[],[],[],[]
    for index,bot in enumerate(bots):
        rows=kept[bot]
        all_rows.append(rows);bot_index.extend([index]*len(rows))
        segments=baseline['bots'].get(bot,{}).get('segments',[])
        p=np.zeros((len(rows),4));sizes=np.zeros(len(rows))
        if not segments:
            p=param_probabilities(rows,ARCHETYPES['tag']);sizes=param_size(rows,ARCHETYPES['tag'])
        else:
            times=np.asarray([data.matches[int(m)]['collected_at'] for m in rows[:,COL['match']]])
            for segment in segments:
                lo=segment['boundary_from'];hi=segment['boundary_to']
                mask=(times>=lo if lo is not None else np.ones(len(rows),bool))&(times<hi if hi is not None else np.ones(len(rows),bool))
                p[mask]=param_probabilities(rows[mask],segment['surrogate_style'])
                sizes[mask]=param_size(rows[mask],segment['surrogate_style'])
        base_pred.append(p);base_size.append(sizes)
    rows=np.concatenate(all_rows)
    match=rows[:,COL['match']].astype(np.int64)
    b=np.asarray(bot_index,dtype=np.int64)
    epochs,epoch_meta={},{}
    for mode in MODES:
        mapping,meta=epoch_map(data.matches,bots,mode,events=events,report=baseline)
        epochs[mode]=np.concatenate([mapping[bot][kept[bot][:,COL['match']].astype(int)] for bot in bots])
        epoch_meta[mode]=meta
    meta=dict(bots=bots,matches=data.matches,split_seed=20261004,split_policy='60/20/20 deterministic hash of whole match ID; all bots at a table share a split',
              validation_audit=validation_audit,upload_events=events,epochs=epoch_meta,input_audit=data.audit,
              warning='This evaluates interpolation to unseen matches, not prediction of an unseen future bot version. Team validation hands are excluded; house:call is retained.')
    arrays=dict(x=features(rows),rows=rows.astype(np.float32),legal=legal_actions(rows),y=rows[:,COL['action']].astype(np.int64),
                size_y=size_labels(rows),size_targets=size_targets(rows),bot=b,match=match,split=split[match],
                baseline=np.concatenate(base_pred).astype(np.float32),baseline_size=np.concatenate(base_size).astype(np.float32))
    arrays.update({f'epoch_{mode}':value for mode,value in epochs.items()})
    np.savez_compressed(directory/'behavior-data.npz',metadata=np.asarray(json.dumps(meta)),**arrays)
    (directory/'behavior-input.json').write_text(json.dumps(meta,indent=2))
    print(json.dumps(dict(event='prepared',actions=len(rows),features=arrays['x'].shape[1],partitions=dict(Counter(map(int,arrays['split']))),validation=validation_audit)),flush=True)


class Network(nn.Module):
    def __init__(self,features,bots,epochs):
        super().__init__()
        self.bot=nn.Embedding(bots,12)
        self.epoch=nn.Embedding(epochs,8)
        self.hidden=nn.Sequential(nn.Linear(features+20,64),nn.ReLU(),nn.Linear(64,64),nn.ReLU())
        self.action=nn.Linear(64,4);self.sizing=nn.Linear(64,10)
        self.bot_action=nn.Embedding(bots,4);self.epoch_action=nn.Embedding(epochs,4)
        self.bot_size=nn.Embedding(bots,10);self.epoch_size=nn.Embedding(epochs,10)
        for module in (self.bot,self.epoch,self.bot_action,self.epoch_action,self.bot_size,self.epoch_size):
            nn.init.zeros_(module.weight)

    def forward(self,x,bot,epoch,legal):
        h=self.hidden(torch.cat([x,self.bot(bot),self.epoch(epoch)],dim=1))
        action=self.action(h)+self.bot_action(bot)+self.epoch_action(epoch)
        size=self.sizing(h)+self.bot_size(bot)+self.epoch_size(epoch)
        return action.masked_fill(~legal,-1e9),size


def metrics(data,prob,sizing,mask):
    mask=mask&data['primary']
    indices=np.flatnonzero(mask);truth=data['y'][indices]
    p=prob[indices]
    nll=-np.log(np.maximum(p[np.arange(len(indices)),truth],1e-9))
    brier=(p*p).sum(1)-2*p[np.arange(len(indices)),truth]+1
    predicted_size=sizing[indices]
    size_error=np.abs(predicted_size-data['rows'][indices,COL['amount']])
    raises=truth==3
    groups={}
    for key,values in (('match',data['match'][indices]),('bot',data['bot'][indices])):
        groups[key]={}
        for value in np.unique(values):
            selected=values==value
            groups[key][str(value)]=dict(actions=int(selected.sum()),nll=float(nll[selected].mean()),
                                        brier=float(brier[selected].mean()),sizing_mae=float(size_error[selected&raises].mean()) if (selected&raises).any() else None)
    confidence=p.max(1);correct=p.argmax(1)==truth
    calibration=[];ece=0.0
    for lower in np.linspace(0,.9,10):
        select=(confidence>=lower)&((confidence<lower+.1) if lower<.9 else (confidence<=1))
        if select.any():
            calibration.append(dict(lower=float(lower),n=int(select.sum()),confidence=float(confidence[select].mean()),accuracy=float(correct[select].mean())))
            ece+=float(select.mean()*abs(confidence[select].mean()-correct[select].mean()))
    streets={}
    for street in range(4):
        select=data['rows'][indices,COL['street']]==street
        if select.any():
            streets[str(street)]=dict(n=int(select.sum()),nll=float(nll[select].mean()),
                                      observed=np.bincount(truth[select],minlength=4).tolist(),predicted=p[select].mean(0).tolist())
    return dict(actions=len(indices),nll=float(nll.mean()),brier=float(brier.mean()),accuracy=float(correct.mean()),
                sizing_mae=float(size_error[raises].mean()),ece=ece,calibration=calibration,streets=streets,by_match=groups['match'],by_bot=groups['bot'])


def train_one(job):
    directory,mode,device,epochs,refit=job
    directory=Path(directory);began=time.monotonic()
    torch.set_num_threads(1);torch.manual_seed(71601)
    torch.cuda.set_device(device)
    torch.cuda.set_per_process_memory_fraction(.09,device)
    with np.load(directory/'behavior-data.npz',allow_pickle=False) as source:
        meta=json.loads(str(source['metadata']))
        data={k:source[k].copy() for k in source.files if k!='metadata'}
    data['primary']=np.asarray([m['kind']=='ladder' for m in meta['matches']])[data['match']]
    gpu=torch.device(f'cuda:{device}')
    tensors={key:torch.as_tensor(data[key],device=gpu) for key in ('x','y','size_y','bot','legal')}
    tensors['epoch']=torch.as_tensor(data['epoch_'+mode],device=gpu)
    network=Network(data['x'].shape[1],len(meta['bots']),len(meta['epochs'][mode]['keys'])).to(gpu)
    optimizer=torch.optim.AdamW(network.parameters(),lr=.003,weight_decay=.005)
    train_indices=torch.as_tensor(np.flatnonzero(np.ones(len(data['y']),bool) if refit else data['split']==0),device=gpu)
    val_mask=(data['split']==1)&data['primary']
    validation=torch.as_tensor(np.flatnonzero(val_mask),device=gpu)
    best,best_epoch,weights=float('inf'),0,None
    curve=[]
    def predict(indices):
        actions,sizes=[],[]
        network.eval()
        with torch.no_grad():
            for chunk in indices.split(8192):
                a,s=network(tensors['x'][chunk],tensors['bot'][chunk],tensors['epoch'][chunk],tensors['legal'][chunk])
                actions.append(a.softmax(1).cpu().numpy());sizes.append(s.softmax(1).cpu().numpy())
        return np.concatenate(actions),np.concatenate(sizes)
    for epoch in range(1,epochs+1):
        network.train()
        order=train_indices[torch.randperm(len(train_indices),device=gpu)]
        for idx in order.split(8192):
            a,s=network(tensors['x'][idx],tensors['bot'][idx],tensors['epoch'][idx],tensors['legal'][idx])
            loss=nn.functional.cross_entropy(a,tensors['y'][idx])
            raises=tensors['y'][idx]==3
            if raises.any():
                loss=loss+.2*nn.functional.cross_entropy(s[raises],tensors['size_y'][idx][raises])
            # Sparse epochs retain small adjustments to the shared bot model.
            loss=loss+.002*(network.epoch.weight.square().mean()+network.epoch_action.weight.square().mean()+network.epoch_size.weight.square().mean())
            optimizer.zero_grad(set_to_none=True);loss.backward();optimizer.step()
        p,size=predict(validation)
        y=data['y'][val_mask];sy=data['size_y'][val_mask]
        nll=float(-np.log(p[np.arange(len(y)),y].clip(1e-9)).mean())
        snll=float(-np.log(size[np.arange(len(y))[y==3],sy[y==3]].clip(1e-9)).mean())
        score=nll+.2*snll
        curve.append(dict(epoch=epoch,validation_nll=nll,validation_size_nll=snll,objective=score))
        if score<best or refit:
            best,best_epoch,weights=score,epoch,{k:v.detach().cpu().clone() for k,v in network.state_dict().items()}
        if epoch%5==0 or epoch==1:
            print(json.dumps(dict(event='train',mode=mode,device=device,epoch=epoch,validation_nll=nll,validation_size_nll=snll,seconds=time.monotonic()-began)),flush=True)
    network.load_state_dict(weights)
    all_indices=torch.arange(len(data['y']),device=gpu)
    probability,sizing_prob=predict(all_indices)
    sizing=(sizing_prob*data['size_targets']).sum(1)
    label=('refit-' if refit else '')+mode
    artifact=dict(mode=mode,epoch=best_epoch,refit=refit,curve=curve,device=str(gpu),seconds=time.monotonic()-began,
                  peak_allocated_bytes=torch.cuda.max_memory_allocated(gpu),architecture=dict(features=data['x'].shape[1],hidden=[64,64],bot_embedding=12,epoch_embedding=8),
                  epoch_metadata=meta['epochs'][mode],input_actions_sha256=meta['input_audit']['actions_sha256'])
    np.savez_compressed(directory/f'policy-{label}.npz',metadata=np.asarray(json.dumps(artifact)),**{k:v.numpy() for k,v in weights.items()})
    # The untouched test split is evaluated only once, after validation-selected stopping.
    if not refit:
        artifact['validation']=metrics(data,probability,sizing,data['split']==1)
        artifact['test']=metrics(data,probability,sizing,data['split']==2)
        np.savez_compressed(directory/f'predictions-{mode}.npz',probability=probability.astype(np.float32),sizing=sizing.astype(np.float32))
    (directory/f'policy-{label}.json').write_text(json.dumps(artifact,indent=2))
    return dict(mode=mode,epoch=best_epoch,device=str(gpu),seconds=artifact['seconds'],peak_allocated_bytes=artifact['peak_allocated_bytes'])


def compare(directory):
    with np.load(directory/'behavior-data.npz',allow_pickle=False) as source:
        meta=json.loads(str(source['metadata']));data={k:source[k].copy() for k in source.files if k!='metadata'}
    data['primary']=np.asarray([m['kind']=='ladder' for m in meta['matches']])[data['match']]
    models={mode:json.loads((directory/f'policy-{mode}.json').read_text()) for mode in MODES}
    baseline={key:metrics(data,data['baseline'],data['baseline_size'],data['split']==value) for key,value in (('validation',1),('test',2))}
    candidates={mode:min(row['objective'] for row in model['curve']) for mode,model in models.items()}
    selected=min(candidates,key=candidates.get)
    rng=np.random.default_rng(231415)
    pairs=[]
    source={'baseline':baseline}|models
    for left,right in [('baseline',mode) for mode in MODES]+[('none','upload'),('placebo','upload'),('none','change')]:
        a,b=source[left]['test']['by_match'],source[right]['test']['by_match']
        common=sorted(set(a)&set(b));diff=np.asarray([a[k]['nll']-b[k]['nll'] for k in common])
        boot=diff[rng.integers(len(diff),size=(5000,len(diff)))].mean(1)
        interval=np.quantile(boot,[.025,.975]).tolist()
        adjusted=np.quantile(boot,[.025/7,1-.025/7]).tolist()
        pairs.append(dict(reference=left,candidate=right,matches=len(common),mean_match_nll_gain=float(diff.mean()),
                          bootstrap_95_interval=interval,bonferroni_7_comparisons_interval=adjusted))
    compact=lambda d:{k:v for k,v in d.items() if k not in ('by_match','by_bot','calibration','streets')}
    result=dict(generated_at=datetime.now(timezone.utc).isoformat(),input_audit=meta['input_audit'],split_policy=meta['split_policy'],
                validation_audit=meta['validation_audit'],selection='lowest validation action NLL + 0.2 sizing-bin NLL; test excluded from selection',
                selected=selected,selected_epoch=models[selected]['epoch'],validation_objectives=candidates,
                baseline={k:compact(v) for k,v in baseline.items()},
                models={mode:{key:compact(model[key]) for key in ('validation','test')} for mode,model in models.items()},
                paired_comparisons=pairs,
                cautions=['Bootstrap resamples whole test matches, preserving actions and all bots within each game.',
                          'Validation marks uploads, not selection as main. Only passed events with trustworthy play timestamps are epoch candidates.',
                          'The split measures generalization to held-out matches from observed versions; it is not a guarantee for future versions.',
                          'Sizing uses discrete legal target mixtures; the baseline MAE uses a central target approximation.',
                          'Display names may refer to renamed teams or code replacements. Empty/sparse epochs cannot establish behavior.'])
    (directory/'behavior-comparison.json').write_text(json.dumps(result,indent=2))
    (directory/'baseline-prediction-metrics.json').write_text(json.dumps(baseline,indent=2))
    print(json.dumps(result,indent=2))
    return result


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step',choices=['prepare','train','compare','refit'])
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--devices',default='0,1,2,3')
    parser.add_argument('--epochs',type=int,default=35)
    args=parser.parse_args();devices=[int(x) for x in args.devices.split(',')]
    if args.step=='prepare':
        prepare(args.directory,devices)
    elif args.step=='train':
        if len(devices)!=4 or len(set(devices))!=4:
            parser.error('Four distinct GPUs required for the four simultaneous ablations')
        with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn')) as pool:
            for result in pool.map(train_one,[(str(args.directory),mode,device,args.epochs,False) for mode,device in zip(MODES,devices)]):
                print(json.dumps(dict(event='trained',**result)),flush=True)
    elif args.step=='compare':
        compare(args.directory)
    else:
        selected=json.loads((args.directory/'behavior-comparison.json').read_text())
        print(json.dumps(train_one((str(args.directory),selected['selected'],devices[0],selected['selected_epoch'],True))))


if __name__=='__main__':
    main()
