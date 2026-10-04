"""Describe main's tactical choices from saved public observations; play no games."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from analysis.run_main_calibration import STEM,verify,dump
from analysis.halliday_performance import has_any_draw
from harness.eval import _cached_module,resolve_path


def review(run):
    plan=verify(run)
    main=_cached_module(resolve_path(plan['main_snapshot']))[0]
    package=SimpleNamespace(**main.terminal_call.__globals__)
    old=_cached_module(resolve_path('snapshots/call_calibration_e186308_group_study'))[0]
    old_pre=SimpleNamespace(**old.terminal_call.__globals__)
    opponent_module=SimpleNamespace(**main.is_shover.__globals__)
    engine=SimpleNamespace(**main.estimate_equity.__globals__)
    params=main.DEFAULT_PARAMS
    counts=Counter();cases=[];air_hands={};below_hands={}
    paths=sorted((run/'traces').glob('*.json.gz'))
    assert len(paths)==10000
    for number,path in enumerate(paths,1):
        with gzip.open(path,'rt') as f:trace=json.load(f)
        tracker=opponent_module.OpponentTracker()
        decisions={(d['view']['hand'],len(d['view']['history'])+1):d for d in trace['decisions']}
        for hand in trace['hands']:
            players=hand['seat_map'];hero=players.index(0)
            tracker.on_hand_start(dict(players=players,seat=hero,stacks=[200]*len(players)))
            action_index=0
            for ei,event in enumerate(hand['events']):
                if event['type']=='street':tracker.on_street(event)
                if event['type']!='action':continue
                action_index+=1
                if event['seat']==hero:
                    d=decisions.pop((hand['hand'],action_index));v=d['view']
                    assert v['players']==players and v['seat']==hero
                    kind=event['action'];raises=[a for a in v['history'] if a[0]=='preflop' and a[2]=='raise']
                    if not v['board']:
                        hc=package.hand_class(v['hole'])
                        if (not raises and hero==(v['button']+1)%len(players)
                                and not any(a[2]=='call' for a in v['history']) and kind=='raise'
                                and hc not in old_pre.SB_STEAL):
                            counts['additional_small_blind_opens']+=1
                            counts['additional_small_blind_open_chips']+=hand['deltas_by_bot'][0]
                            counts['additional_small_blind_fold_benchmark']-=200-v['stacks'][hero]
                        if len(raises)==2 and raises[0][1]==hero and kind=='call':
                            villain=raises[-1][1];profile=tracker.profiles[players[villain]]
                            if (hc in package.CALL_THREE_BET_WIDE and hc not in package.CALL_THREE_BET
                                    and max(v['street_bets'])<params['large_bet_bb']*2
                                    and opponent_module.frequent_threebettor(profile,params)):
                                counts['additional_wide_threebet_calls']+=1
                                counts['wide_threebet_call_chips']+=hand['deltas_by_bot'][0]
                                counts['wide_threebet_calls_at_four_chances']+=profile['threebet_chances']==4
                        if raises and v['stacks'][raises[-1][1]]==0 and kind=='call':
                            in_pot={a[1] for a in v['history'] if a[2] in ('call','raise')}
                            behind=[s for s,f in enumerate(v['folded']) if not f and s!=hero and s not in in_pot]
                            if behind:
                                counts['preflop_shove_calls_with_players_behind']+=1
                                counts['preflop_shove_calls_behind_chips']+=hand['deltas_by_bot'][0]
                    else:
                        opponents=[s for s,f in enumerate(v['folded']) if not f and s!=hero]
                        risk=event['amount']-v['street_bets'][hero]
                        if (kind=='raise' and v['to_call']==0 and len(opponents)==1 and v['pot']>0
                                and risk>=1.3*v['pot'] and engine.evaluate_hand(v['hole']+v['board'])[0]==0
                                and not has_any_draw(v['hole'],v['board'])):
                            villain=opponents[0]
                            profile=tracker.profiles[players[villain]]
                            fold_rate=opponent_module.fold_to_us(profile,params)
                            breakeven=risk/(v['pot']+risk)
                            response=next((e['action'] for e in hand['events'][ei+1:]
                                if e['type']=='action' and e['street']==v['street'] and e['seat']==villain),None)
                            counts['pure_air_overbets']+=1
                            counts['pure_air_overbets_folded_to']+=response=='fold'
                            air_hands[path.name,hand['hand']]=hand['deltas_by_bot'][0]
                            if fold_rate<breakeven:
                                counts['air_overbets_below_immediate_breakeven_estimate']+=1
                                counts['below_gate_folded_to']+=response=='fold'
                                below_hands[path.name,hand['hand']]=hand['deltas_by_bot'][0]
                                cases.append(dict(id=f"{path.name.removesuffix('.json.gz')}:{hand['hand']}:{action_index}",
                                    street=v['street'],hole=v['hole'],board=v['board'],pot=v['pot'],risk=risk,
                                    estimated_fold=fold_rate,zero_equity_breakeven=breakeven,
                                    observed_responses=profile['faced_us'],response=response,
                                    hand_chips=hand['deltas_by_bot'][0],equity=d['equity']))
                tracker.on_action(dict(event,players=players))
        assert not decisions
        if number%1000==0:print(f'{number}/10000 public-event reviews',flush=True)
    counts.update(pure_air_distinct_hands=len(air_hands),pure_air_distinct_hand_chips=sum(air_hands.values()),
        below_gate_distinct_hands=len(below_hands),below_gate_distinct_hand_chips=sum(below_hands.values()))
    result=dict(counts=counts,examples=cases,games=len(paths),
        scope='Observed tactical contexts, not causal ablations or proof of negative EV. The zero-equity one-bet benchmark ignores future improvement, later betting and size-specific fold rates. No bot action is executed.',
        params={k:params[k] for k in ('bluff_min_fold','overbet_bluff_fraction','wide_call_min_chances','wide_call_min_rate')})
    dump(run/'tactical-review.json',result)
    print(json.dumps(counts,indent=2))


def review_cases(run):
    """Explain selected flags using the saved estimate and public counters."""
    from macpoker.sdk import GameState
    from analysis.halliday_report import BLUNDERS
    plan=verify(run)
    module=_cached_module(resolve_path(plan['main_snapshot']))[0]
    pre=SimpleNamespace(**module.terminal_call.__globals__)
    opp=SimpleNamespace(**module.is_shover.__globals__)
    p=module.DEFAULT_PARAMS
    summaries=json.loads((run/'audit-summary.json').read_text())['games']
    flags=[]
    for g in summaries:
        if not g['flags']:continue
        with gzip.open(run/'audit'/(g['match']+'.json.gz'),'rt') as f:
            flags.extend(r for r in json.load(f)['decisions'] if r['classification'] in BLUNDERS)
    predicates={
        'sparse_premium_fold':lambda r:r['action']=='fold' and r['street']=='preflop'
            and r['diagnostic'].get('equity') is not None and (r['diagnostic'].get('estimate') or {}).get('samples',1000)<128,
        'river_range_fold':lambda r:r['action']=='fold' and r['street']=='river' and r['diagnostic'].get('ranged'),
        'uniform_river_call':lambda r:r['action']=='call' and r['street']=='river' and not r['diagnostic'].get('ranged'),
        'tracked_river_call':lambda r:r['action']=='call' and r['street']=='river' and r['diagnostic'].get('ranged')}
    result={}
    for label,predicate in predicates.items():
        candidates=[r for r in flags if predicate(r)]
        if not candidates:continue
        row=max(candidates,key=lambda r:(r['public_ev_lower'] or 0) if r['action']=='fold' else -(r['public_ev_upper'] or 0))
        mid,hand,index=row['id'].split(':');hand,index=int(hand),int(index)
        with gzip.open(run/'traces'/(mid+'.json.gz'),'rt') as f:trace=json.load(f)
        view=next(d['view'] for d in trace['decisions'] if d['view']['hand']==hand and len(d['view']['history'])+1==index)
        tracker=module.OpponentTracker();found=False
        for h in trace['hands']:
            if h['hand']>hand:break
            players=h['seat_map'];hero=players.index(0)
            tracker.on_hand_start(dict(players=players,seat=hero,stacks=[200]*len(players)))
            ai=0
            for event in h['events']:
                if event['type']=='street':tracker.on_street(event)
                if event['type']!='action':continue
                ai+=1
                if h['hand']==hand and ai==index:
                    found=True;break
                tracker.on_action(dict(event,players=players))
            if found:break
        assert found
        state=GameState(view);live=[i for i,f in enumerate(state.folded) if not f and i!=state.seat]
        profiles={i:dict(tracker.profiles[state.player_at(i)]) for i in live}
        known=[i for i in live if opp.is_shover(tracker.profiles[state.player_at(i)],p)]
        price=pre.pot_odds(state);ranged=row['diagnostic']['ranged']
        if state.board:
            margin=p[('range_' if ranged else '')+'call_margin_'+state.street]
            margin+=(len(live)-1)*p['multiway_call_margin']
            margin+=p[('range_' if ranged else '')+'large_bet_margin']*min(1,state.to_call/max(1,state.pot-state.to_call))
            if sum(a[0]==state.street and a[2]=='raise' for a in state.history)>1:
                margin+=p[('range_' if ranged else '')+'reraise_margin']
        else:margin=p[('range_' if ranged else '')+'preflop_call_margin']
        result[label]=dict(decision=row,view=view,profiles=profiles,known_shover_seats=known,
            price=price,call_margin=margin,call_threshold=price+margin,
            source_scope='Read frozen source formulas and replayed public counters; no equity simulation or bot action rerun.')
    dump(run/'case-review.json',result)
    print(json.dumps({k:dict(id=v['decision']['id'],threshold=v['call_threshold'],
        bot_equity=v['decision']['diagnostic']['equity'],known_shover_seats=v['known_shover_seats']) for k,v in result.items()},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,default=ROOT/'analysis/results'/STEM)
    p.add_argument('--cases',action='store_true')
    args=p.parse_args()
    (review_cases if args.cases else review)(args.directory.resolve())
