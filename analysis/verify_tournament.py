"""Independently recompute complete tournament rotations, points and regrouping."""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import random
from statistics import mean


def points(values):
    # Independent pair-count formula, rather than harness sorted rank groups.
    return [1+sum(other<value for other in values)+.5*(sum(other==value for other in values)-1)
            for value in values]


def verify(path):
    raw=Path(path).read_bytes();data=json.loads(raw)
    start=data['args'].get('repeat_start',0)
    expected={(repeat,ci) for repeat in range(start,start+data['args']['repeats'])
              for ci in range(len(data['args']['bots']))}
    actual=[(e['repeat'],e['candidate']) for e in data['events']]
    assert len(actual)==len(expected) and set(actual)==expected
    grouped=defaultdict(list)
    for game in data['games']:
        assert sum(game['chips'])==0
        assert all(v=='OK' for v in game['verdicts']) and not any(game['errors'])
        grouped[game['cand_idx'],game['round'],game['table']].append(game)
    rank_by_candidate=defaultdict(list);by_opponent=defaultdict(lambda:defaultdict(list))
    checked=0;candidate_rows=[]
    for ei,event in enumerate(data['events']):
        assert event['specs'][0]==data['args']['bots'][event['candidate']]
        assert event['specs'][1:]==data['events'][0]['specs'][1:]
        n=len(event['specs']);placement=[0.]*n;game_points=[0.]*n
        order=list(range(n))
        random.Random(f'{data["args"]["seed"]}:initial:{event["repeat"]}').shuffle(order)
        tie_order={b:i for i,b in enumerate(order)}
        assert len(event['rounds'])==data['args']['rounds']
        for ri,round_data in enumerate(event['rounds']):
            tables=round_data['tables']
            assert sum(tables,[])==order
            assert max(map(len,tables))-min(map(len,tables))<=1
            for ti,table in enumerate(tables):
                rows=grouped[ei,ri,ti];size=len(table)
                assert sorted(r['game'] for r in rows)==list(range(size))
                total=[0.]*size
                for row in rows:
                    assert len(row['chips'])==len(row['verdicts'])==len(row['errors'])==size
                    total=[a+b for a,b in zip(total,points(row['chips']))]
                    checked+=1
                for seat,p in enumerate(points(total)):
                    placement[table[seat]]+=p
                    game_points[table[seat]]+=total[seat]
            assert placement==round_data['placement']
            assert game_points==round_data['game_points']
            order=sorted(range(n),key=lambda b:(-placement[b],-game_points[b],tie_order[b]))
        assert placement==event['placement'] and game_points==event['game_points']
        ranks=[1+sum(o>v for o in placement)+.5*(sum(o==v for o in placement)-1) for v in placement]
        assert ranks==event['rank']
        candidate=event['specs'][0]
        rank_by_candidate[candidate].append(ranks[0])
        best=1+sum(p>placement[0] for p in placement)
        worst=sum(p>=placement[0] for p in placement)
        candidate_rows.append(dict(candidate=candidate,repeat=event['repeat'],rank=ranks[0],
                                   rank_min=best,rank_max=worst,placement=placement[0],game_points=game_points[0]))
        for name,rank in zip(event['specs'],ranks):
            by_opponent[candidate][name].append(rank)
    assert checked==len(data['games'])
    for row in data['summary']:
        assert abs(mean(rank_by_candidate[row['bot']])-row['mean_rank'][0])<1e-10
    return dict(passed=True,source=str(path),sha256=sha256(raw).hexdigest(),games=checked,
                tournaments=len(data['events']),rounds=data['args']['rounds'],
                candidate_results=candidate_rows,
                field_mean_ranks={candidate:sorted([(name,mean(ranks)) for name,ranks in values.items()],key=lambda p:p[1])
                                  for candidate,values in by_opponent.items()},
                checks=['Zero-sum chips, every verdict OK, no transport errors.',
                        'Every entrant occurs once per round; all seat rotations present.',
                        'Game/round/final points recomputed by independent pair-count formula.',
                        'Initial seeded order and cumulative-placement/game-point regrouping reproduced.',
                        'Unresolved prize ties retained; no invented playoff winners.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('result')
    p.add_argument('--output',required=True)
    args=p.parse_args();result=verify(args.result)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['candidate_results','field_mean_ranks']},indent=2))


if __name__=='__main__':main()
