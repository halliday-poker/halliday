"""Upload events are candidate behavioral epochs, never asserted deployments."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

import numpy as np


def match_split(matches, seed=20261004):
    """One split per complete match, shared across every bot at that table."""
    result=[]
    for match in matches:
        number=int.from_bytes(sha256(f'{seed}|{match["id"]}'.encode()).digest()[:8],'big')%100
        result.append(0 if number<60 else 1 if number<80 else 2)
    return np.asarray(result,dtype=np.int64)


def upload_events(matches, replay_metadata):
    by_bot=defaultdict(list)
    counts=Counter()
    for match in matches:
        if match['kind']!='validation':
            continue
        counts['validation_matches']+=1
        names=match['names']
        if len(names)!=2 or 'house:call' not in names:
            counts['not_house_call_pair']+=1
            continue
        slot=1-names.index('house:call')
        value=replay_metadata.get(match['id'],{}).get('value',{})
        verdicts=value.get('result',{}).get('verdicts',[])
        same_house_slot=value.get('names',[None,None])[1-slot]=='house:call'
        verdict=verdicts[slot] if len(verdicts)==2 and same_house_slot else 'UNKNOWN'
        passed=verdict=='OK'
        counts['passed' if passed else 'failed_or_unknown']+=1
        trusted=match.get('played_at') is not None
        counts['trusted_play_time' if trusted else 'collection_time_only']+=1
        by_bot[names[slot]].append(dict(match=match['id'],at=match.get('played_at'),
                                      collected_at=match['collected_at'],passed=passed,verdict=verdict,
                                      trusted_time=trusted))
    return dict(by_bot),dict(counts)


def epoch_map(matches, bots, mode, *, events=None, report=None, seed=93821):
    """Map each bot/match to a predeclared candidate epoch without action labels.

    Unknown play times stay in the base epoch. Failed/unknown validations are
    excluded. Validation may describe an unselected upload: this is an ablation
    feature, not proof of code replacement.
    """
    mapping,keys,boundaries={},['shared-base'],{}
    rng=np.random.default_rng(seed)
    for bot in bots:
        if mode in ('upload','placebo'):
            cuts=sorted(set(e['at'] for e in (events or {}).get(bot,[]) if e['passed'] and e['trusted_time']))
            if mode=='placebo':
                times=sorted(m['played_at'] for m in matches if bot in m['names'] and m['kind']=='ladder' and m.get('played_at') is not None)
                gaps=[(a+b)/2 for a,b in zip(times,times[1:]) if a<b]
                interior=sum(bool(times) and times[0]<t<times[-1] for t in cuts)
                outside=[t for t in cuts if times and (t<=times[0] or t>=times[-1])]
                cuts=sorted(outside+rng.choice(gaps,size=min(interior,len(gaps)),replace=False).tolist()) if gaps else cuts
        elif mode=='change':
            cuts=(report or {}).get('bots',{}).get(bot,{}).get('segmentation',{}).get('accepted_cut_times',[])
        elif mode=='none':
            cuts=[]
        else:
            raise ValueError(f'Unknown epoch mode {mode}')
        boundaries[bot]=cuts
        local=[0]
        for j in range(len(cuts)):
            local.append(len(keys));keys.append(f'{bot}::candidate-{j+1}')
        ids=[]
        for match in matches:
            time=match.get('played_at') if mode in ('upload','placebo') else match['collected_at']
            index=int(np.searchsorted(cuts,time,side='right')) if time is not None else 0
            ids.append(local[index])
        mapping[bot]=np.asarray(ids,dtype=np.int64)
    return mapping,dict(mode=mode,keys=keys,boundaries=boundaries,
                        warning='Epoch features are candidate upload/change intervals; actual deployment is unobserved.')
