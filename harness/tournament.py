"""Four-round field simulation using eval.py's engine and CPU/CUDA workers.

The final roster and exact server tie/table allocation rules are unavailable.
Use balanced tables nearest five seats and seeded ordering for exact grouping
ties. Final prize ties are reported unresolved, not silently awarded.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import datetime as dt
import json
import os
from pathlib import Path
import random
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import eval as harness


def groups(order: list[int]) -> list[list[int]]:
    """Balanced contiguous groups, preserving cumulative-score ordering."""
    if len(order) < 2:
        raise ValueError('A tournament needs at least two entrants')
    count = max(1, (len(order) + 2) // 5)
    size, extra = divmod(len(order), count)
    result, offset = [], 0
    for index in range(count):
        n = size + (index < extra)
        result.append(order[offset:offset+n])
        offset += n
    return result


def score_round(tables, game_rows, placement, game_points):
    """Rank each game's chips, then each table's total game points."""
    for ti, table in enumerate(tables):
        rows = sorted(game_rows[ti], key=lambda row: row['game'])
        if [r['game'] for r in rows] != list(range(len(table))):
            raise ValueError('Incomplete or duplicated rotation set')
        total = [0.] * len(table)
        for row in rows:
            if len(row['chips']) != len(table) or sum(row['chips']) != 0:
                raise ValueError('Invalid game chip accounting')
            for seat, points in enumerate(harness.placement_points(row['chips'])):
                total[seat] += points
        for seat, points in enumerate(harness.placement_points(total)):
            placement[table[seat]] += points
            game_points[table[seat]] += total[seat]


def standings(placement):
    """Shared average ranks; retain prize ties for a real playoff."""
    points = harness.placement_points(placement)
    return [len(points) + 1 - p for p in points]


def run(args):
    field = [spec for spec, _ in harness.read_pool(Path(args.pool), [])]
    # The validation house bot is not a team entrant.
    field = [s for s in field if s != 'house:call' and Path(s).stem != 'house_call']
    if len(field) != len(set(field)) or any(c in field for c in args.bots):
        raise ValueError('Entrants must be unique; exclude candidates from the pool')
    count = len(field) + 1
    events = []
    for repeat in range(args.repeat_start,args.repeat_start+args.repeats):
        order = list(range(count))
        random.Random(f'{args.seed}:initial:{repeat}').shuffle(order)
        tie_order = {bot: index for index, bot in enumerate(order)}
        for ci, candidate in enumerate(args.bots):
            events.append(dict(repeat=repeat, candidate=ci, specs=[candidate]+field,
                               order=order[:], tie_order=tie_order,
                               placement=[0.]*count, game_points=[0.]*count, rounds=[]))
    plan = harness.compute_plan(args)
    pool, plan = harness.worker_pool(plan, args)
    output_games = []
    started = time.perf_counter()
    try:
        for round_number in range(args.rounds):
            jobs, lookup = [], {}
            for ei, event in enumerate(events):
                tables = groups(event['order'])
                event['rounds'].append(dict(tables=tables))
                for ti, table in enumerate(tables):
                    key = len(lookup)
                    lookup[key] = (ei, ti)
                    specs = [event['specs'][bot] for bot in table]
                    for rotation in range(len(table)):
                        jobs.append(dict(cand_idx=ei, candidate=specs[0], opponents=specs[1:],
                                         table=key, game=rotation, deals=args.deals,
                                         time_ms=30_000, increment_ms=100,
                                         seed=f'{args.seed}:repeat:{event["repeat"]}:round:{round_number}:group:{ti}'))
            # play_game incorporates table into the deck seed. Make this key
            # identical across candidate substitutions, then restore lookup.
            for job in jobs:
                ei, ti = lookup[job['table']]
                job['table'] = ti
            print(f'Round {round_number+1}: {len(jobs)} games on {plan["workers"]} {plan["device"]} workers', flush=True)
            rows = pool.imap_unordered(harness.play_game, jobs, chunksize=1) if pool else map(harness.play_game, jobs)
            by_event = defaultdict(lambda: defaultdict(list))
            step = max(1, len(jobs)//10)
            for done, row in enumerate(rows, 1):
                by_event[row['cand_idx']][row['table']].append(row)
                output_games.append(dict(round=round_number, **row))
                if done % step == 0:
                    print(f'  {done}/{len(jobs)} games; {time.perf_counter()-started:.0f}s total', flush=True)
            for ei, event in enumerate(events):
                score_round(event['rounds'][-1]['tables'], by_event[ei], event['placement'], event['game_points'])
                event['rounds'][-1].update(placement=event['placement'][:], game_points=event['game_points'][:])
                event['order'] = sorted(range(count), key=lambda b: (-event['placement'][b], -event['game_points'][b], event['tie_order'][b]))
    except BaseException:
        if pool:
            pool.terminate()
        raise
    finally:
        if pool:
            pool.close()
            pool.join()
    summary = []
    for event in events:
        event['rank'] = standings(event['placement'])
        event['unresolved_prize_ties'] = []
        for value in sorted(set(event['placement']), reverse=True):
            tied = [i for i, p in enumerate(event['placement']) if p == value]
            best = 1 + sum(p > value for p in event['placement'])
            if best <= 3 and len(tied) > 1:
                event['unresolved_prize_ties'].append(tied)
    for ci, candidate in enumerate(args.bots):
        mine = [e for e in events if e['candidate'] == ci]
        summary.append(dict(bot=candidate, hash=harness.bot_hash(candidate),
                            mean_rank=harness.mean_ci([e['rank'][0] for e in mine]),
                            placement=harness.mean_ci([e['placement'][0] for e in mine]),
                            strictly_top_three=sum(sum(p>e['placement'][0] for p in e['placement'])+
                                                  sum(p==e['placement'][0] for p in e['placement'])<=3 for e in mine),
                            repeats=len(mine)))
    bad = [(i, g['verdicts'], g['errors']) for i,g in enumerate(output_games) if any(v!='OK' for v in g['verdicts'])]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result = dict(args=vars(args), compute=plan, elapsed_s=time.perf_counter()-started,
                  commit=harness.git_commit(), summary=summary, bad_games=bad, events=events, games=output_games,
                  assumptions=['All observed external display identities are entrants, excluding house:call.',
                               'Balanced tables nearest five; initial seeded order breaks exact regrouping ties.',
                               'Final ranks use cumulative placement only. Prize ties need playoffs and remain unresolved.',
                               'Pairing by event seed persists; regrouping can produce different opponents after round one.'])
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(summary=summary, bad_games=len(bad), output=str(output)), indent=2))
    return bool(bad)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('bots', nargs='+')
    p.add_argument('--pool', default='sparring/competitors/from_data/pool.txt')
    p.add_argument('--repeats', type=int, default=20)
    p.add_argument('--repeat-start', type=int, default=0,
                   help='First event index; use disjoint intervals to shard one fixed-seed experiment')
    p.add_argument('--rounds', type=int, default=4)
    p.add_argument('--deals', type=int, default=100)
    p.add_argument('--seed', default='four-round-field')
    p.add_argument('--device', choices=['auto','cpu','cuda'], default='auto')
    p.add_argument('--workers', type=int, default=max(1,(os.cpu_count() or 2)-1))
    p.add_argument('--gpu-workers', type=int)
    p.add_argument('--gpu-devices')
    p.add_argument('--gpu-batch-size', type=int, default=128)
    p.add_argument('--output', default=f'harness/results/tournament-{dt.datetime.now():%Y%m%d-%H%M%S}.json')
    args=p.parse_args()
    if min(args.repeats,args.rounds,args.deals)<1:
        p.error('repeats, rounds and deals must be positive')
    if args.repeat_start<0:
        p.error('repeat-start must be nonnegative')
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
