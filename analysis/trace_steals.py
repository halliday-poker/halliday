"""Inspect outcomes of added opens without confusing them with whole-policy EV."""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import random
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from harness import eval as harness


def trace_game(job):
    if harness._worker_init_error:
        raise RuntimeError(harness._worker_init_error)
    specs=[job['candidate']]+job['opponents']
    seed=f"{job['seed']}:{job['table']}:{job['game']}"
    random.seed(seed)
    np.random.seed(int(hashlib.md5(seed.encode()).hexdigest()[:8],16))
    bots=[harness.make_bot(s,f'{seed}:{i}') for i,s in enumerate(specs)]
    baseline=harness._cached_module(harness.resolve_path('snapshots/analysis_main_20261004'))[0]
    marks={}
    original=bots[0].act
    def act(state):
        action=original(state)
        if (not state.board and action.kind=='raise'
                and not any(a[0]=='preflop' and a[2] in ('call','raise') for a in state.history)
                and baseline.decide(state,None,bots[0].opponents.profiles).kind=='fold'):
            marks[state.hand]=dict(hand=state.hand,seat=state.seat,hole=state.hole,
                                   invested=state.street_bets[state.seat],target=action.amount,
                                   public_profiles={str(state.player_at(s)):dict(bots[0].opponents.profiles[state.player_at(s)])
                                                    for s,f in enumerate(state.folded) if not f and s!=state.seat})
        return action
    bots[0].act=act
    transports=[harness.TimedTransport(bot,spec) for bot,spec in zip(bots,specs)]
    before=harness._gpu_evaluator.metadata() if harness._gpu_evaluator else None
    result=harness.MatchRunner(harness.MatchConfig(seats=len(specs),deals=100,offset=job['game'],
                                                  seed=f"{job['seed']}:{job['table']}",base_time_ms=30000,increment_ms=100),transports).run()
    for hand in result.hands:
        mark=marks.get(hand['hand'])
        if mark is None:continue
        mark['chips']=hand['deltas_by_bot'][0]
        mark['margin_over_folding']=mark['chips']+mark['invested']
        mark['events']=hand['events']
        mark['flop']=any(e['type']=='street' and e['street']=='flop' for e in hand['events'])
        mark['category']=('postflop_win' if mark['chips']>0 else 'postflop_loss') if mark['flop'] else ('won_preflop' if mark['chips']>0 else 'lost_preflop')
    compute=dict(device='cpu')
    if before:
        compute=harness._gpu_evaluator.metadata()
        for k in ('batches','ranked_hands','gpu_seconds'):compute[k]-=before[k]
        compute['worker_pid']=os.getpid()
    return dict(table=job['table'],game=job['game'],chips=result.chips,verdicts=result.verdicts,
                errors=[t.error for t in transports],marks=list(marks.values()),compute=compute)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',default='analysis/candidates/adaptive_steal')
    p.add_argument('--tables',type=int,default=128)
    p.add_argument('--seed',default='steal-action-diagnostics-20261004')
    p.add_argument('--device',default='cuda',choices=['cpu','cuda','auto'])
    p.add_argument('--workers',type=int,default=16)
    p.add_argument('--gpu-workers',type=int,default=16)
    p.add_argument('--gpu-devices',default='0,1,2,3')
    p.add_argument('--gpu-batch-size',type=int,default=128)
    p.add_argument('--output',default='analysis/results/refresh-20261004/steals-action-trace.json')
    args=p.parse_args()
    field=harness.read_pool(ROOT/'sparring/competitors/from_data/pool.txt',[])
    tables=harness.draw_tables(field,args.tables,[4,5,5,6],args.seed)
    jobs=[dict(candidate=args.candidate,opponents=table,table=ti,game=rotation,seed=args.seed)
          for ti,table in enumerate(tables) for rotation in range(len(table)+1)]
    pool,compute=harness.worker_pool(harness.compute_plan(args),args)
    try:
        games=list(pool.imap_unordered(trace_game,jobs,chunksize=1)) if pool else list(map(trace_game,jobs))
    finally:
        if pool:pool.close();pool.join()
    categories=defaultdict(lambda:dict(hands=0,margin=0))
    per_table=np.zeros((len(tables),2))
    for game in games:
        assert sum(game['chips'])==0
        for mark in game['marks']:
            categories[mark['category']]['hands']+=1
            categories[mark['category']]['margin']+=mark['margin_over_folding']
            per_table[game['table']]+= [1,mark['margin_over_folding']]
    totals=per_table.sum(0)
    rng=np.random.default_rng(6019)
    boot=per_table[rng.integers(len(tables),size=(5000,len(tables)))].sum(1)
    valid=boot[:,0]>0
    interval=np.quantile(boot[valid,1]/boot[valid,0],[.025,.975]).tolist() if valid.any() else None
    summary=dict(games=len(games),added_opens=int(totals[0]),margin_over_folding=float(totals[1]),
                 per_added_open=float(totals[1]/totals[0]) if totals[0] else None,
                 table_bootstrap_ci95=interval,categories=dict(categories),
                 failures=sum(any(v!='OK' for v in g['verdicts']) or any(g['errors']) for g in games))
    result=dict(args=vars(args),hash=harness.bot_hash(args.candidate),compute=compute,summary=summary,games=games,
                scope='Diagnostic new deals. Compare each added-open hand with folding at that same decision, including sunk blinds. This omits how a different action affects later opponent adaptation and game/tournament placement; it is not whole-policy superiority evidence.')
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    return bool(summary['failures'])


if __name__=='__main__':
    raise SystemExit(main())
