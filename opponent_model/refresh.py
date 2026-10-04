"""Fit interpretable summaries within the empirically selected upload epochs."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import torch

from .compute import Compute
from .data import COL,load_cache
from .fit import BotModel
from .validation import epoch_map


def context_rates(rows,compute,bootstrap=1000):
    c=lambda name:rows[:,COL[name]]
    pre=c('street')==0;facing=c('facing')>0;raised=c('action')==3
    criteria={
        'preflop_shove_when_raise_legal':(pre&(c('can_raise')>0),raised&(c('amount')==c('maximum'))),
        'call_when_facing_preflop_raise':(pre&(c('pre_raises')>0)&facing,c('action')==2),
        'fold_to_large_commitment':(facing&(c('call')>=.3*c('stack')),c('action')==0),
        'multiway_postflop_fold':(~pre&facing&(c('live')>2),c('action')==0),
        'river_call_when_facing_bet':((c('street')==3)&facing,c('action')==2),
        'postflop_bet_when_checked_to':(~pre&~facing&(c('can_raise')>0),raised),
        'postflop_reraise_when_legal':(~pre&facing&(c('can_raise')>0),raised),
    }
    matches=np.unique(c('match')).astype(int);mapping={m:i for i,m in enumerate(matches)}
    index=np.asarray([mapping[int(m)] for m in c('match')])
    weights=compute.bootstrap_weights(list(range(len(matches))),len(matches),bootstrap)
    result={}
    for name,(mask,success) in criteria.items():
        count=np.bincount(index[mask],minlength=len(matches))
        hits=np.bincount(index[mask&success],minlength=len(matches))
        denominator=weights@compute.array(count)
        values=(weights@compute.array(hits))/denominator.clamp(min=1)
        valid=values[1:][denominator[1:]>0]
        observed=int(count.sum());support=int((count>0).sum())
        result[name]=dict(rate=float(values[0]) if observed else None,opportunities=observed,matches=support,
                          confidence_interval=torch.quantile(valid,compute.array([.025,.975])).tolist() if len(valid)>1 and support>1 else None,
                          caution='Whole-match bootstrap; rare contexts and within-version opponent changes remain uncertain.')
    return result


def refresh(directory,devices):
    data=load_cache(directory/'context-features.npz')
    original=json.loads((directory/'baseline-estimates.json').read_text())
    comparison=json.loads((directory/'behavior-comparison.json').read_text())
    metadata=json.loads((directory/'behavior-input.json').read_text())
    mode=comparison['selected']
    if mode=='placebo':
        raise ValueError('Random boundaries must not become claimed bot versions; inspect comparison')
    mapping,epoch_meta=epoch_map(data.matches,metadata['bots'],mode,events=metadata['upload_events'],report=original)
    if mode=='change':
        # The selected model's epoch embeddings are defined by training-only
        # boundaries. Reuse those exact boundaries when refitting the replicas.
        epoch_meta=metadata['epochs'][mode]
        mapping={bot:np.asarray([0]*len(data.matches)) for bot in metadata['bots']}
        for bot in metadata['bots']:
            cuts=epoch_meta['boundaries'][bot]
            keys=[0]+[epoch_meta['keys'].index(f'{bot}::candidate-{j+1}') for j in range(len(cuts))]
            mapping[bot]=np.asarray([keys[np.searchsorted(cuts,m['collected_at'],side='right')] for m in data.matches])
    assert epoch_meta['keys']==metadata['epochs'][mode]['keys'],'Inference epoch indices differ from trained weights'
    names=metadata['bots'];computes=[Compute(f'cuda:{d}',batch_size=128,memory_limit_mib=768) for d in devices]
    def shard(worker_index):
        compute=computes[worker_index];torch.cuda.set_device(compute.device)
        output={}
        for bot in names[worker_index::len(computes)]:
            all_hands=data.hands[bot]
            ladder=[m for m in all_hands if data.matches[m]['kind']=='ladder']
            chosen=ladder or list(all_hands)
            observations=data.observations[bot]
            observations=observations[np.isin(observations[:,COL['match']],chosen)]
            model=BotModel(observations,{m:all_hands[m] for m in chosen},compute)
            groups=defaultdict(list)
            for local,index in enumerate(model.matches):groups[int(mapping[bot][index])].append(local)
            overall=model.estimate(list(range(len(model.matches))),bootstrap=100)
            segments=[]
            for epoch,selected in groups.items():
                match_indices=[model.matches[i] for i in selected]
                local_rows=observations[np.isin(observations[:,COL['match']],match_indices)]
                report=model.estimate(selected,bootstrap=1000)
                if len(selected)<6:
                    blend=len(selected)/6
                    report['surrogate_style']={key:(int(overall['surrogate_style'][key]) if key=='adaptive' else blend*value+(1-blend)*overall['surrogate_style'][key])
                                               for key,value in report['surrogate_style'].items()}
                trusted=[data.matches[i]['played_at'] for i in match_indices if data.matches[i].get('played_at') is not None]
                times=[data.matches[i].get('played_at') or data.matches[i]['collected_at'] for i in match_indices]
                segment=dict(segment=len(segments)+1,epoch=epoch,observed_from=min(times),observed_through=max(times),
                             observed_from_utc=datetime.fromtimestamp(min(times),timezone.utc).isoformat(),
                             observed_through_utc=datetime.fromtimestamp(max(times),timezone.utc).isoformat(),
                             boundary_from=None,boundary_to=None,matches=len(selected),match_ids=[data.matches[i]['id'] for i in match_indices],
                             selection_key=[bool(trusted),max(trusted or times)],
                             timestamp_basis='trusted server play time when present; collection time otherwise',
                             known_play_times=len(trusted),validation_only=not bool(ladder),
                             style_shrinkage_to_full_bot=max(0,1-len(selected)/6),
                             context_rates=context_rates(local_rows,compute),
                             behavior=dict(file='behavior-policy.npz',bot=names.index(bot),epoch=epoch,
                                           weight=1 if ladder and len(selected)>=2 else 0,
                                           model=mode,heldout_comparison='behavior-comparison.json',
                                           status='fitted_public_context_policy' if ladder and len(selected)>=2 else 'sparse_scaffold_fallback'),**report)
                if epoch:
                    j=int(epoch_meta['keys'][epoch].rsplit('-',1)[1])-1
                    cuts=epoch_meta['boundaries'][bot]
                    segment['boundary_from']=cuts[j]
                    segment['boundary_to']=cuts[j+1] if j+1<len(cuts) else None
                segments.append(segment)
            segments.sort(key=lambda s:s['selection_key'])
            for index,segment in enumerate(segments,1):segment['segment']=index
            output[bot]=dict(segmentation=dict(method='predictively_validated_candidate_epochs',mode=mode,
                                               candidate_cut_times=epoch_meta['boundaries'][bot],proposals=[],accepted_cut_times=[],
                                               warning='These are candidate upload intervals, not individually confirmed deployment times.'),segments=segments)
            print(json.dumps(dict(event='refreshed',bot=bot,segments=len(segments),device=str(compute.device))),flush=True)
        return output
    with ThreadPoolExecutor(max_workers=len(computes)) as executor:
        shards=list(executor.map(shard,range(len(computes))))
    result=dict(original)
    result.update(schema_version=2,generated_at_utc=datetime.now(timezone.utc).isoformat(),
                  bots={bot:r for shard in shards for bot,r in shard.items()},
                  segmentation_policy=epoch_meta,predictive_comparison=comparison,
                  behavior_model_sha256=sha256((directory/f'policy-refit-{mode}.npz').read_bytes()).hexdigest(),
                  compute=dict(computes[0].metadata(),devices=[x.metadata() for x in computes]),
                  settings=dict(original['settings'],segmentation=mode),
                  interpretation=[
                      'Scaffold parameters remain surrogate estimates, not recovered source code.',
                      'Successful uploads with trusted timestamps define candidate intervals because this feature improved held-out prediction, including against random-boundary controls.',
                      'Passing validation is not proof of selection as main; no individual boundary is asserted to be a deployment.',
                      'Unknown-time games stay in a base interval. Latest selection prioritizes a segment with trusted play times.',
                      'Team validation hands are excluded where ladder data exists. Identities with only validation evidence use a marked scaffold fallback.',
                      'Intervals with fewer than six matches shrink the executable scaffold style toward the full-bot estimate; reported parameter uncertainty is still the within-interval fit.',
                      'The learned replica sees its own hole cards and public context. It never sees opponents\' hidden cards or future outcomes.',
                      'Display names can be renames or same-name replacements; these files cannot resolve all team identities.',
                  ])
    (directory/'opponent-estimates.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--devices',default='1,2,3')
    args=parser.parse_args();refresh(args.directory,[int(x) for x in args.devices.split(',')])
