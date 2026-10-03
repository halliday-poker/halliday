"""Compare real latest Halliday tables with independently dealt duplicate games."""
from collections import defaultdict
import json
from pathlib import Path
import sys

import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harness.eval import mean_ci
from opponent_model.data import load_cache,COL

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'analysis/results/refresh-20261004'


def simulated_rates(simulation,profiles):
    names={profile['file']:name for name,profile in profiles.items()}
    simulated=defaultdict(lambda:dict(matches=0,hands=0,folds=0,vpip=0,pfr=0))
    for game in simulation['games']:
        if game['cand_idx']!=1:continue
        lineup=['Halliday']+[names[Path(s).stem.rsplit('_epoch_',1)[0]+'.py'] for s in game['opponents']]
        for name,behavior in zip(lineup,game['behavior']):
            totals=simulated[name]
            totals['matches']+=1;totals['hands']+=simulation['args']['deals']
            totals['folds']+=sum(street.get('fold',0) for street in behavior['actions'].values())
            totals['vpip']+=behavior['vpip_hands'];totals['pfr']+=behavior['pfr_hands']
    return simulated


def main():
    data=load_cache(DIRECTORY/'context-features.npz')
    profiles=json.loads((ROOT/'sparring/competitors/from_data/profiles.json').read_text())['profiles']
    ids=set(profiles['Halliday']['match_ids'])
    selected={i for i,m in enumerate(data.matches) if m['id'] in ids and m['kind']=='ladder'}
    observed={}
    for name,counts in data.hands.items():
        matches=selected&counts.keys()
        if not matches:continue
        hands,vpip,pfr=np.asarray([counts[m] for m in matches]).sum(0)
        rows=data.observations[name]
        rows=rows[np.isin(rows[:,COL['match']],list(matches))]
        observed[name]=dict(matches=len(matches),hands=int(hands),
                            folds=int((rows[:,COL['action']]==0).sum()),vpip=int(vpip),pfr=int(pfr))
    simulation=json.loads((ROOT/'harness/results/20261004-014228.json').read_text())
    simulated=simulated_rates(simulation,profiles)
    historical=json.loads((ROOT/'harness/results/20261004-033206.json').read_text())
    historical_rates=simulated_rates(historical,profiles)
    rows=[]
    for name,real in observed.items():
        replica=simulated[name]
        rates=lambda values:{key:values[key]/values['hands'] for key in ['folds','vpip','pfr']}
        rows.append(dict(name=name,observed=real,simulated=replica,
                         observed_rates=rates(real),simulated_rates=rates(replica),
                         historical_interval_rates=rates(historical_rates[name])))
    metadata=json.loads((DIRECTORY/'source/matches.json').read_text())
    chips=[m['chips'][m['names'].index('Halliday')] for m in metadata if m['id'] in ids and m['kind']=='ladder']
    result=dict(source_sha256=data.audit['actions_sha256'],simulation='harness/results/20261004-014228.json',
                observed_halliday=dict(matches=len(chips),chips=sum(chips),bb100=mean_ci([c/2 for c in chips])),
                simulated_halliday=simulation['summary'],historical_interval_halliday=historical['summary'],rows=rows,
                caveats=['Fresh decks and eight duplicate games per observed table, not reconstructed replay actions.',
                         'All replicas use newest available intervals; opponents may have changed during Halliday\'s observed interval.',
                         'Similar marginal action rates do not prove comparable conditional policies or winnings.',
                         'Real source hashes/deployment state are unknown; observed Halliday cannot be identified with current bot/.'])
    (DIRECTORY/'closed-loop-fidelity.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# Simulation fidelity — 4 October 2026','',
           'The replicas predict recorded actions substantially better. Matching historical opponent intervals brings simulated Halliday results closer to the observed interval, but frozen-baseline results remain more optimistic. Do not treat simulated win rates as forecasts of the live leaderboard.','',
           '## Matching the observed table composition','',
           'The 43 latest Halliday ladder games were replayed as table compositions on fresh duplicate deals: 344 games per candidate. These preserve eight-seat lineups, not original decks or actions.','',
           '| Halliday source | bb/100, approximate 95% interval | Folded hands | VPIP | PFR |',
           '|---|---:|---:|---:|---:|']
    hero=next(row for row in rows if row['name']=='Halliday')
    mean,ci=result['observed_halliday']['bb100'];real=hero['observed_rates']
    lines.append(f'| Observed latest interval | {mean:+.2f} ± {ci:.2f} | {real["folds"]:.2%} | {real["vpip"]:.2%} | {real["pfr"]:.2%} |')
    for sample,index,label in [(simulation,1,'Halliday replica / newest opponents'),(simulation,0,'Frozen baseline / newest opponents'),
                               (historical,1,'Halliday replica / observed opponent intervals'),(historical,0,'Frozen baseline / observed opponent intervals')]:
        summary=sample['summary'][index];games=[g for g in sample['games'] if g['cand_idx']==index]
        count=len(games)*100
        folds=sum(sum(a.get('fold',0) for a in g['behavior'][0]['actions'].values()) for g in games)/count
        vpip=sum(g['behavior'][0]['vpip_hands'] for g in games)/count
        pfr=sum(g['behavior'][0]['pfr_hands'] for g in games)/count
        lines.append(f'| {label} | {summary["mbb"][0]*.1:+.2f} ± {summary["mbb"][1]*.1:.2f} | {folds:.2%} | {vpip:.2%} | {pfr:.2%} |')
    lines+=['','134 of the 301 opponent seats belong to earlier intervals than the newest available one. A separate fresh-deck run used each opponent’s estimated interval for the actual historical match. Its Halliday-replica point estimate is closer to observed returns. The two simulations use different seeds, so this is not an isolated causal estimate of changing intervals. Matching observed contexts is a descriptive check on a refitted model, separate from the whole-match held-out predictive test.','',
            'The latest interval’s 30 auditable all-ins were 1,027.8 chips below expectation against the recorded hands. Subtracting only that runout effect leaves -528.2 chips (-6.14 bb/100), rather than the observed -1,556. This is not a complete skill-adjusted return. The gap between the frozen baseline and the learned replica can reflect approximation error or an unknown code version; it does not establish which source ran historically.','',
            '## Opponent action-rate discrepancies','',
            'Below are the largest absolute VPIP differences among identities present in at least three observed matches. More detail is retained in `closed-loop-fidelity.json`. These marginal rates include lineup effects and differing opponent versions.','',
            '| Identity | Real matches | Real VPIP | Newest-interval VPIP | Matched-interval VPIP | Real PFR | Matched-interval PFR |',
            '|---|---:|---:|---:|---:|---:|---:|']
    for row in sorted((r for r in rows if r['observed']['matches']>=3),key=lambda r:abs(r['observed_rates']['vpip']-r['simulated_rates']['vpip']),reverse=True)[:12]:
        a,b,c=row['observed_rates'],row['simulated_rates'],row['historical_interval_rates']
        lines.append(f'| {row["name"]} | {row["observed"]["matches"]} | {a["vpip"]:.2%} | {b["vpip"]:.2%} | {c["vpip"]:.2%} | {a["pfr"]:.2%} | {c["pfr"]:.2%} |')
    lines+=['','## Sensitivity to the opponent model','',
            'On the same 400 randomly drawn 4–6-seat duplicate tables (1,970 games each), the frozen Halliday baseline (`8015e4b3`) earned +85.70 ±14.06 bb/100 against the learned replicas and +28.73 ±4.97 against the original scaffold fits. Round placement points were much closer: 3.704 ±0.122 and 3.718 ±0.134. A small number of large pots can materially change chip returns without improving placement.','',
            'The broader small-table pool includes every observed external name, including old aliases and the validation house bot. It differs from Halliday’s recent eight-seat opponents. Neither model is calibrated by forcing Halliday’s aggregate win rate to match observed losses. Strategy selection must use independent paired deals, tournament points, both model families and eight-seat stress tests.','',
            'Source artifacts: `harness/results/20261004-014228.json`, `20261004-015231.json`, `20261004-015019.json`, `20261004-033206.json`. No candidate or opponent failures occurred in these runs. Confidence intervals measure simulation sampling uncertainty and exclude opponent-model error.','']
    (ROOT/'analysis/reports/simulation-fidelity-20261004.md').write_text('\n'.join(lines))


if __name__=='__main__':main()
