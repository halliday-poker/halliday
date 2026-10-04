"""Fit executable newest-upload replicas, including validated public-history effects.

All validation matches against house:call mark uploads, regardless of verdict.
Training diagnostics hold out whole games; the final runtime refit uses every
available replay in the newest interval, including its validation game.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
import multiprocessing as mp
from pathlib import Path
import shutil
import time

import numpy as np
import torch
from torch import nn

from .behavior import Network
from .compute import Compute, memory_limit_mib
from .data import COL, load_cache, load_dataset
from .fit import BotModel
from .validation import match_split
from .recency_prior import age_rows,prior_weights,scaffold_fit,version_time_gaps,DECAY,TARGETS,HALF_LIFE_HOURS
from .within_game import design, prepare as prepare_history, read, SEED
from sparring.competitors.build import latest_profiles, slug
from sparring.competitors.policy import features, legal_actions, size_labels, size_targets
from sparring.param import ARCHETYPES


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def newest_selection(matches, bots):
    """Use the latest upload itself, never silently fall back to an older one."""
    result={}
    for bot in bots:
        uploads=[m for m in matches if m.get('kind')=='validation' and
                 len(m['names'])==2 and bot in m['names'] and 'house:call' in m['names']]
        trusted=[m for m in uploads if isinstance(m.get('at'),(int,float)) and m['at']>1e11]
        newest=max(trusted,key=lambda m:(m['at'],m['id'])) if trusted else None
        selected=[m['id'] for m in matches if newest and bot in m['names'] and
                  isinstance(m.get('at'),(int,float)) and m['at']>=newest['at']]
        result[bot]=dict(upload=None if newest is None else newest['id'],
            boundary_ms=None if newest is None else newest['at'],match_ids=selected,
            exclusion_reason=('House bot' if bot.startswith('house:') else
                              'No validation upload with a trusted server timestamp' if newest is None else None))
    return result


def prepare(source, directory):
    directory.mkdir(parents=True,exist_ok=True)
    if not (source/'context-features.npz').exists():
        from .data import save_dataset
        data=load_dataset(source/'source/actions.jsonl',source/'source/matches.json',source/'source/state.json')
        save_dataset(data,source/'context-features.npz')
    data=load_cache(source/'context-features.npz')
    raw_matches=json.loads((source/'source/matches.json').read_text())
    bots=sorted(data.observations); selection=newest_selection(raw_matches,bots)
    old=latest_profiles(json.loads((source/'opponent-estimates.json').read_text())) if (source/'opponent-estimates.json').exists() else {}
    profiles={}; row_groups=[]; ids=[]; available={m['id']:i for i,m in enumerate(data.matches)}
    full_weights=[];training_weights=[];primary=[];prior_evidence={};splits=match_split(data.matches)
    for b,bot in enumerate(bots):
        chosen=selection[bot]
        observed=[available[mid] for mid in chosen['match_ids'] if mid in available and available[mid] in data.hands[bot]]
        chosen['prior_only'] = not observed and not chosen['exclusion_reason']
        if chosen['prior_only']:
            chosen['uncertainty'] = 'Newest upload has no replay; estimate uses only explicitly discounted earlier versions, not observed newest behavior.'
        chosen['observed_match_ids']=[data.matches[m]['id'] for m in observed]
        chosen['missing_replays']=sorted(set(chosen['match_ids'])-set(chosen['observed_match_ids']))
        chosen['ladder_matches']=sum(data.matches[m]['kind']=='ladder' for m in observed)
        chosen['validation_matches']=sum(data.matches[m]['kind']=='validation' for m in observed)
        chosen['hands']=sum(data.hands[bot][m][0] for m in observed)
        if chosen['exclusion_reason']:
            rows=np.empty((0,len(COL)))
            weights=np.empty(0);train_weights=np.empty(0);is_latest=np.empty(0,dtype=bool)
        else:
            original=data.observations[bot]
            cuts=[m['at']/1000 for m in raw_matches if m.get('kind')=='validation' and
                  len(m['names'])==2 and bot in m['names'] and 'house:call' in m['names'] and
                  isinstance(m.get('at'),(int,float)) and m['at']>1e11]
            ages=age_rows(original,data.matches,cuts)
            gaps=version_time_gaps(original,data.matches,cuts)
            _,weights,evidence=prior_weights(original,ages,gaps)
            training=splits[original[:,COL['match']].astype(int)]==0
            _,wtrain,training_evidence=prior_weights(original[training],ages[training],gaps)
            train_weights=np.zeros(len(original));train_weights[training]=wtrain
            keep=(weights>0)|(train_weights>0)
            rows=original[keep];weights=weights[keep];train_weights=train_weights[keep];is_latest=ages[keep]==0
            if not len(rows):
                chosen['exclusion_reason']='No newest replay or usable discounted historical observations'
            prior_evidence[bot]=dict(parameters=evidence,training_parameters=training_evidence,
                newest_rows=int(is_latest.sum()),older_rows=int((~is_latest).sum()),
                older_effective_action_rows=float(weights[~is_latest].sum()),
                training_older_effective_action_rows=float(train_weights[~is_latest].sum()))
        row_groups.append(rows); ids.extend([b]*len(rows))
        full_weights.extend(weights);training_weights.extend(train_weights);primary.extend(is_latest)
        prior={k:v for k,v in old.get(bot,dict(surrogate_style=ARCHETYPES['tag'],observed_from=0,observed_through=0)).items() if k!='id'}
        profiles[bot]={'segments':[dict(prior, segment=1,epoch=0,known_play_times=len(observed),
            match_ids=[data.matches[int(m)]['id'] for m in np.unique(rows[:,COL['match']])],matches=len(observed),validation_only=False,
            exclusion_reason=chosen['exclusion_reason'],boundary_from=chosen['boundary_ms'],prior_only=chosen['prior_only'])]}
    rows=np.concatenate(row_groups).astype(np.float32); match=rows[:,COL['match']].astype(np.int64)
    meta=dict(bots=bots,matches=data.matches,input_audit=data.audit,
        split_policy='Whole-match deterministic 60/20/20; validation-only model choice; runtime refit uses all selected rows.',
        upload_selection=selection)
    np.savez_compressed(directory/'behavior-data.npz',metadata=np.asarray(json.dumps(meta)),rows=rows,
        x=features(rows),legal=legal_actions(rows),y=rows[:,COL['action']].astype(np.int64),
        size_y=size_labels(rows),size_targets=size_targets(rows),bot=np.asarray(ids,dtype=np.int64),match=match,
        split=match_split(data.matches)[match],baseline=np.zeros((len(rows),4),np.float32),baseline_size=np.zeros(len(rows)))
    dump(directory/'opponent-estimates.json',dict(segmentation_policy={'mode':'upload'},bots=profiles))
    if (directory/'source').is_symlink() and (directory/'source').resolve()!=(source/'source').resolve():
        if (directory/'traces').exists():raise ValueError('Cannot replace a running study snapshot')
        (directory/'source').unlink()
    if not (directory/'source').exists():
        (directory/'source').symlink_to((source/'source').resolve(),target_is_directory=True)
    shutil.copyfile(source/'snapshot-manifest.json',directory/'snapshot-manifest.json')
    prepare_history(directory,include_validation=True)
    saved_meta,saved=read(directory)
    saved['sample_weight']=np.asarray(full_weights,dtype=np.float32)
    saved['training_weight']=np.asarray(training_weights,dtype=np.float32)
    saved['primary']=np.asarray(primary,dtype=bool)
    assert len(saved['y'])==len(primary)
    saved_meta['selection']='All newest-version observations at full weight; opportunity-specific older priors decayed tenfold per validation upload. Primary validation/test metrics use newest versions only.'
    np.savez_compressed(directory/'dynamics-data.npz',metadata=np.asarray(json.dumps(saved_meta)),**saved)
    dump(directory/'recency-priors.json',dict(decay=DECAY,half_life_hours=HALF_LIFE_HOURS,targets=TARGETS,bots=prior_evidence,
        rule='Full weight for all newest data. Add previous-version observations only for sparse parameters, at most 0.1^age * 2^(-upload_gap_hours/6), stopping at the effective opportunity target. Before the first known upload, the earliest observed trusted match proxies version start. Unknown-time rows are excluded. Training support uses training games only; final refit uses all newest games. Time gaps proxy possible changes, not observed source-code differences.'))
    dump(directory/'upload-selection.json',dict(source=str(source),actions_sha256=data.audit['actions_sha256'],
        rule='Most recent validation against house:call, regardless of verdict; include the upload game and every subsequent observed match. Older versions contribute only explicitly recorded, decayed sparse-parameter priors.',
        bots=selection,excluded={b:v['exclusion_reason'] for b,v in selection.items() if v['exclusion_reason']}))
    dump(directory/'runtime-plan.json',dict(source=str(source),seed=SEED,
        action_patterns=['RaiseYourEdge','orcabot'],action_parameter='Per-action preflop log-odds slope times (hand/99 - 0.5), clipped to +/-4.',
        selection='Fit slopes on training games. Enable only when validation log loss improves. Select sizing mixture on validation raise MSE. Test is descriptive; earlier exploration used this archive.',
        sizing_weights=[0,.25,.5,.75,1],refit='Use all newest-version observations at validation-selected epochs. Sparse parameters receive older-version priors with tenfold decay per upload, recorded separately.',
        comparisons='Static-context reconstruction versus selected progress correction and history sizing. Historical discoveries are not an independent confirmation sample.'))
    print(json.dumps(dict(bots=sum(not v['exclusion_reason'] for v in selection.values()),actions=len(rows),
                         bot_games=sum(len(v['observed_match_ids']) for v in selection.values() if not v['exclusion_reason']),
                         validation_games=sum(v['validation_matches'] for v in selection.values() if not v['exclusion_reason'])),indent=2))


def fit_slopes(probability, rows, truth, mask, device):
    if mask.sum()<50:
        return np.zeros(4)
    logits=torch.as_tensor(np.log(probability[mask].clip(1e-12)),device=device)
    progress=torch.as_tensor(rows[mask,COL['hand']]/99-.5,device=device)
    y=torch.as_tensor(truth[mask],device=device)
    legal=torch.as_tensor(legal_actions(rows[mask]),device=device)
    beta=nn.Parameter(torch.zeros(4,device=device)); optimizer=torch.optim.Adam([beta],lr=.04)
    for _ in range(250):
        scores=(logits+progress[:,None]*beta).masked_fill(~legal,-1e9)
        loss=nn.functional.cross_entropy(scores,y)+.002*(beta**2).sum()
        optimizer.zero_grad();loss.backward();optimizer.step()
        with torch.no_grad():beta.clamp_(-4,4)
    return beta.detach().cpu().numpy()


def corrected(probability, rows, beta):
    from sparring.competitors.policy import softmax
    return softmax(np.log(probability.clip(1e-12))+(rows[:,COL['hand']]/99-.5)[:,None]*beta,legal_actions(rows))


def select(directory):
    torch.set_num_threads(1);torch.cuda.set_device(0)
    meta,data=read(directory);rows=data['rows'];y=data['y']
    predictions={}
    for mode in ('static','history'):
        with np.load(directory/f'dynamics-predictions-{mode}.npz') as a:
            predictions[mode]={key:a[key].copy() for key in a.files}
    base=predictions['static']['probability']; output={}; final_probability=base.copy()
    for b,bot in enumerate(meta['bots']):
        if bot in meta['excluded']:continue
        mask=(data['bot']==b)&(rows[:,COL['street']]==0)&data['primary']
        beta=fit_slopes(base,rows,y,mask&(data['split']==0),'cuda:0') if bot in ('RaiseYourEdge','orcabot') else np.zeros(4)
        candidate=corrected(base[mask],rows[mask],beta); local_y=y[mask]; splits=data['split'][mask]
        old=-np.log(base[mask,np.asarray(local_y)].clip(1e-9));new=-np.log(candidate[np.arange(len(candidate)),local_y].clip(1e-9))
        validation=splits==1; test=splits==2
        enabled=bool(validation.sum()>=100 and np.mean(old[validation]-new[validation])>0 and np.any(beta))
        output[bot]=dict(coefficients=beta.tolist(),enabled=enabled,validation_actions=int(validation.sum()),
            validation_nll_gain=float(np.mean(old[validation]-new[validation])) if validation.any() else None,
            test_nll_gain=float(np.mean(old[test]-new[test])) if test.any() else None)
        if enabled:final_probability[mask]=candidate
    raised=(y==3); validation=raised&(data['split']==1)&data['primary']; target=rows[:,COL['amount']]
    weights=[0,.25,.5,.75,1];errors={}
    for weight in weights:
        prediction=(1-weight)*predictions['static']['sizing']+weight*predictions['history']['sizing']
        errors[str(weight)]=float(np.mean((prediction[validation]-target[validation])**2))
    weight=min(weights,key=lambda w:errors[str(w)])
    comparisons={}
    for name,mask in (('validation',(data['split']==1)&data['primary']),('test',(data['split']==2)&data['primary'])):
        sizing=(1-weight)*predictions['static']['sizing']+weight*predictions['history']['sizing'];idx=np.flatnonzero(mask)
        comparisons[name]=dict(actions=len(idx),static_nll=float(-np.log(base[idx,y[idx]].clip(1e-9)).mean()),
            adjusted_nll=float(-np.log(final_probability[idx,y[idx]].clip(1e-9)).mean()),raises=int((mask&raised).sum()),
            static_size_mse=float(np.mean((predictions['static']['sizing'][mask&raised]-target[mask&raised])**2)),
            adjusted_size_mse=float(np.mean((sizing[mask&raised]-target[mask&raised])**2)))
    result=dict(preflop=output,sizing_weight=weight,validation_sizing_mse=errors,comparisons=comparisons,
        epochs={mode:json.loads((directory/f'dynamics-{mode}.json').read_text())['epoch'] for mode in ('static','history')})
    dump(directory/'runtime-selection.json',result);print(json.dumps({k:v for k,v in result.items() if k!='preflop'},indent=2))


def refit_one(job):
    directory,mode,device,epochs=job;directory=Path(directory);began=time.monotonic()
    torch.set_num_threads(1);torch.cuda.set_device(device);torch.manual_seed(SEED)
    torch.cuda.set_per_process_memory_fraction(memory_limit_mib()*2**20/torch.cuda.get_device_properties(device).total_memory,device)
    meta,data=read(directory);gpu=f'cuda:{device}'
    t={key:torch.as_tensor(data[key],device=gpu) for key in ('y','size_y','bot','legal')}
    t['x']=torch.as_tensor(design(data,mode),device=gpu);t['epoch']=torch.zeros(len(data['y']),dtype=torch.long,device=gpu)
    t['weight']=torch.as_tensor(data['sample_weight'],device=gpu)
    indices=torch.as_tensor(np.flatnonzero(data['sample_weight']>0),device=gpu)
    network=Network(t['x'].shape[1],len(meta['bots']),1).to(gpu)
    optimizer=torch.optim.AdamW(network.parameters(),lr=.003,weight_decay=.005)
    for _ in range(epochs):
        for idx in indices[torch.randperm(len(indices),device=gpu)].split(8192):
            a,s=network(t['x'][idx],t['bot'][idx],t['epoch'][idx],t['legal'][idx]);raising=t['y'][idx]==3
            w=t['weight'][idx]
            loss=(nn.functional.cross_entropy(a,t['y'][idx],reduction='none')*w).sum()/w.sum()
            if raising.any():loss+=.2*(nn.functional.cross_entropy(s[raising],t['size_y'][idx][raising],reduction='none')*w[raising]).sum()/w[raising].sum()
            optimizer.zero_grad(set_to_none=True);loss.backward();optimizer.step()
    network.eval();prob=[]
    with torch.no_grad():
        for idx in torch.arange(len(data['y']),device=gpu).split(8192):
            a,_=network(t['x'][idx],t['bot'][idx],t['epoch'][idx],t['legal'][idx]);prob.append(a.softmax(1).cpu().numpy())
    metadata=dict(temporal_mode=mode,input_sha256=meta['input_audit']['actions_sha256'],epochs=epochs,seed=SEED,
                  scope='All newest-upload observations at full weight, plus opportunity-specific older priors decayed tenfold per version.')
    np.savez_compressed(directory/f'runtime-{mode}.npz',metadata=np.asarray(json.dumps(metadata)),
                        **{k:v.detach().cpu().numpy() for k,v in network.state_dict().items()})
    np.savez_compressed(directory/f'runtime-predictions-{mode}.npz',probability=np.concatenate(prob))
    return dict(mode=mode,device=gpu,epochs=epochs,rows=len(indices),newest_rows=int(data['primary'].sum()),
                older_effective_rows=float(data['sample_weight'][~data['primary']].sum()),seconds=time.monotonic()-began,
                peak_allocated_bytes=torch.cuda.max_memory_allocated(device))


def refit(directory):
    selection=json.loads((directory/'runtime-selection.json').read_text())
    with ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('spawn')) as pool:
        jobs=[(str(directory),mode,device,selection['epochs'][mode]) for device,mode in enumerate(('static','history'))]
        compute=list(pool.map(refit_one,jobs))
    meta,data=read(directory);torch.set_num_threads(1)
    upload_selection=json.loads((directory/'upload-selection.json').read_text())
    source=Path(upload_selection['source']);cache=load_cache(source/'context-features.npz')
    raw_matches=json.loads((source/'source/matches.json').read_text())
    bots=sorted(set(data['bot'].tolist()));shards=[]
    with np.load(directory/'runtime-predictions-static.npz') as a:probability=a['probability']
    def shard(device):
        torch.cuda.set_device(device);compute=Compute(f'cuda:{device}',batch_size=128,memory_limit_mib=memory_limit_mib(),seed=72861)
        result={}
        for b in bots[device::4]:
            bot=meta['bots'][b];mask=(data['bot']==b)&data['primary']
            cuts=[m['at']/1000 for m in raw_matches if m.get('kind')=='validation' and len(m['names'])==2 and
                  bot in m['names'] and 'house:call' in m['names'] and isinstance(m.get('at'),(int,float)) and m['at']>1e11]
            original=cache.observations[bot];ages=age_rows(original,cache.matches,cuts);keep=ages>=0
            rows=original[keep];ages=ages[keep]
            counts={int(m):cache.hands[bot][int(m)] for m in np.unique(rows[:,COL['match']])}
            estimate=scaffold_fit(rows,counts,ages,compute,version_time_gaps(rows,cache.matches,cuts))
            latest_ids=upload_selection['bots'][bot]['observed_match_ids']
            latest_hands=upload_selection['bots'][bot]['hands']
            progress=selection['preflop'][bot];beta=np.zeros(4)
            if progress['enabled']:
                beta=fit_slopes(probability,data['rows'],data['y'],mask&(data['rows'][:,COL['street']]==0),f'cuda:{device}')
            result[bot]=dict(style=estimate['surrogate_style'],estimate=estimate,bot_index=b,
                preflop_progress=beta.tolist(),sizing_weight=selection['sizing_weight'],matches=len(latest_ids),hands=latest_hands,
                all_data_refit=True,selected_match_ids=latest_ids,prior=estimate['prior'])
            print(json.dumps(dict(bot=bot,matches=len(latest_ids),hands=latest_hands,device=device)),flush=True)
        return result,compute.metadata()
    with ThreadPoolExecutor(max_workers=4) as pool:shards=list(pool.map(shard,range(4)))
    dump(directory/'runtime-fit.json',dict(schema_version=1,source_sha256=meta['input_audit']['actions_sha256'],
        generated_at_utc=datetime.now(timezone.utc).isoformat(),selection=json.loads((directory/'upload-selection.json').read_text()),
        policy_files={mode:dict(path=str((directory/f'runtime-{mode}.npz').resolve()),sha256=sha256((directory/f'runtime-{mode}.npz').read_bytes()).hexdigest()) for mode in ('static','history')},
        bots={name:fit for fits,_ in shards for name,fit in fits.items()},compute=compute,
        recency_priors=json.loads((directory/'recency-priors.json').read_text()),
        scaffold_compute=[v for _,v in shards],predictive_selection=selection))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('step',choices=['prepare','select','refit'])
    parser.add_argument('--source-directory',type=Path);parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args()
    if args.step=='prepare':prepare(args.source_directory,args.directory)
    elif args.step=='select':select(args.directory)
    else:refit(args.directory)
