"""Verify newest-version coverage, runtime/training parity and GPU baseline math."""
import argparse
from dataclasses import asdict
from hashlib import sha256
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from opponent_model.behavior import Network
from opponent_model.data import COL,load_cache
from opponent_model.within_game import read,design
from sparring.competitors.policy import Policy
from harness.gpu_equity import CudaEvaluator


def verify_priors(run):
    priors=json.loads((run/'recency-priors.json').read_text());checked=0
    for record in priors['bots'].values():
        for scope in ('parameters','training_parameters'):
            for evidence in record[scope].values():
                newest=evidence['latest_opportunities'];target=evidence['target_opportunities']
                if newest>=target:assert not evidence['older_versions']
                total=float(newest)
                for version in evidence['older_versions']:
                    cap=priors['decay']**version['age']*2**(-version['gap_hours']/priors['half_life_hours'])
                    assert version['weight']<=cap+1e-12
                    assert math.isclose(cap,version['age_discount']*version['time_discount'],rel_tol=1e-12)
                    assert math.isclose(version['weight']*version['raw_opportunities'],version['effective_opportunities'],rel_tol=1e-12)
                    total+=version['effective_opportunities'];checked+=1
                assert math.isclose(total,evidence['effective_opportunities'],rel_tol=1e-12)
                if newest<target:assert total<=target+1e-8
    result=dict(passed=True,prior_contributions_checked=checked,
                rule='Newest weight 1; older maximum 0.1^age * 2^(-gap_hours/6), with parameter target cap')
    (run/'prior-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def verify(run):
    prior_verification=verify_priors(run)
    meta,data=read(run);fit=json.loads((run/'runtime-fit.json').read_text())
    source=Path(fit['selection']['source']);cache=load_cache(source/'context-features.npz')
    selection=fit['selection']['bots'];ids={m['id']:i for i,m in enumerate(cache.matches)}
    totals={'actions':0,'hands':0,'bot_games':0,'validation_games':0}
    for b,name in enumerate(meta['bots']):
        if name not in fit['bots']:continue
        chosen=selection[name];fitted=fit['bots'][name]
        observed=set(chosen['observed_match_ids'])
        assert set(fitted['selected_match_ids'])==observed
        if chosen['upload'] in ids and ids[chosen['upload']] in cache.hands[name]:
            assert chosen['upload'] in observed,'Available upload validation replay must be included'
        else:
            assert chosen['upload'] in chosen['missing_replays'],'Unavailable upload replay must be explicit'
        for mid in observed:assert cache.matches[ids[mid]]['at']>=chosen['boundary_ms']
        source_rows=cache.observations[name][np.isin(cache.observations[name][:,COL['match']],[ids[mid] for mid in observed])]
        rows=data['rows'][(data['bot']==b)&data['primary']]
        np.testing.assert_allclose(source_rows.astype(np.float32),rows,equal_nan=True)
        hands=sum(cache.hands[name][ids[mid]][0] for mid in observed)
        assert fitted['hands']==hands
        totals['actions']+=len(rows);totals['hands']+=hands;totals['bot_games']+=len(observed)
        totals['validation_games']+=chosen['validation_matches']
    torch.set_num_threads(1)
    assert np.all(data['sample_weight'][data['primary']]==1)
    assert np.all(data['sample_weight'][~data['primary']]<=.100001)
    assert np.all(data['training_weight'][~data['primary']]<=.100001)
    parity={}; rng=np.random.default_rng(49257)
    chosen=np.unique(np.concatenate([rng.choice(len(data['y']),min(8192,len(data['y'])),replace=False),
                                    np.array([np.flatnonzero(data['bot']==b)[0] for b in np.unique(data['bot'])])]))
    for mode in ('static','history'):
        policy=Policy(run/f'runtime-{mode}.npz');w=policy.weights
        network=Network(design(data,mode).shape[1],len(meta['bots']),1)
        network.load_state_dict({k:torch.as_tensor(v) for k,v in w.items()});network.eval()
        max_error=0
        for b in np.unique(data['bot'][chosen]):
            idx=chosen[data['bot'][chosen]==b]
            p,s=policy.predict(data['rows'][idx],b,0,history=data['history'][idx],hand=data['rows'][idx,COL['hand']])
            with torch.no_grad():
                a,z=network(torch.as_tensor(design(data,mode)[idx]),torch.as_tensor(data['bot'][idx]),
                    torch.zeros(len(idx),dtype=torch.long),torch.as_tensor(data['legal'][idx]))
            np.testing.assert_allclose(p,a.softmax(1).numpy(),atol=2e-6,rtol=2e-5)
            np.testing.assert_allclose(s,z.softmax(1).numpy(),atol=2e-6,rtol=2e-5)
            max_error=max(max_error,float(np.max(abs(p-a.softmax(1).numpy()))))
        parity[mode]=dict(actions=len(chosen),max_probability_error=max_error)
    manifest=json.loads((run/'baseline-manifest.json').read_text())
    for name,digest in manifest['runtime_files'].items():assert sha256((ROOT/manifest['baseline']/name).read_bytes()).hexdigest()==digest
    original=subprocess.check_output(['git','show',manifest['main_commit']+':bot/engine.py'],cwd=ROOT)
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'engine.py';path.write_bytes(original)
        spec=importlib.util.spec_from_file_location('_main_parity_engine',path);cpu=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=cpu;spec.loader.exec_module(cpu)
        from bot import engine
        gpu=CudaEvaluator(0,128); comparisons=0
        for number in range(48):
            cards=rng.choice(52,9,replace=False)
            text=lambda c:'23456789TJQKA'[int(c)//4]+'cdhs'[int(c)%4]
            hole=[text(c) for c in cards[:2]];board=[text(c) for c in cards[2:2+(0,3,4,5)[number%4]]]
            ranges=[None]*(1+number%3)
            left=cpu.estimate_equity(hole,board,ranges,192,None,seed=number)
            right=engine.estimate_equity(hole,board,ranges,192,None,seed=number,
                _evaluate_batch=gpu.evaluate,_batch_size=128)
            assert asdict(left)==asdict(right),(left,right);comparisons+=1
    result=dict(coverage=totals,all_latest_observations_used=True,upload_games_included=True,prior_verification=prior_verification,
                excluded=fit['selection']['excluded'],runtime_policy_parity=parity,
                main_gpu_fixed_sample_parity_cases=comparisons,gpu=gpu.metadata(),
                limitation='Fixed-sample parity does not imply bit-identical timed decisions or tournament CPU clock compliance.')
    (run/'runtime-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True)
    verify(p.parse_args().directory)
