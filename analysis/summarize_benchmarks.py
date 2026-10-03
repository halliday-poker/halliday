"""Audit and combine paired duplicate-table experiments, preserving seed blocks."""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
from statistics import NormalDist
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harness.eval import score_set,mean_ci


def summarize(paths,purpose):
    evidence=[];series=defaultdict(lambda:defaultdict(list));hashes={}
    for path in paths:
        raw=Path(path).read_bytes();data=json.loads(raw)
        games=data['games'];sets=defaultdict(list)
        for game in games:
            if sum(game['chips'])!=0:raise ValueError('Nonzero chip sum')
            sets[game['cand_idx'],game['table']].append(game)
        metrics={}
        for (ci,table),rows in sets.items():
            seats=len(data['tables'][table])+1
            if sorted(r['game'] for r in rows)!=list(range(seats)):
                raise ValueError('Incomplete duplicate rotation set')
            metrics[ci,table]=score_set(rows,data['args']['deals'],2,
                                      data['args']['time_ms']+data['args']['increment_ms']*data['args']['deals'])
        for ci,summary in enumerate(data['summary']):
            name=summary['bot']
            if name in hashes and hashes[name]!=summary['hash']:raise ValueError('Candidate changed across runs')
            hashes[name]=summary['hash']
            for table in range(len(data['tables'])):
                for key in ['mbb','game_pts','round_pts']:
                    factor=.1 if key=='mbb' else 1
                    series[name][key].append(metrics[ci,table][key]*factor)
                    series[name]['delta_'+key].append((metrics[ci,table][key]-metrics[0,table][key])*factor)
        evidence.append(dict(file=str(path),sha256=sha256(raw).hexdigest(),seed=data['seed'],args=data['args'],
                             tables=len(data['tables']),games=len(games),summary=data['summary'],compute=data['compute'],
                             failures=sum(any(v!='OK' for v in g['verdicts']) for g in games),
                             player_verdicts=sum(len(g['verdicts']) for g in games)))
    tests=max(1,len(series)-1);z=NormalDist().inv_cdf(1-.05/(2*tests))
    summary=[]
    for name,values in series.items():
        summary.append(dict(bot=name,hash=hashes[name],tables=len(values['mbb']),
                            metrics={key:dict(mean_ci95=mean_ci(x),family_adjusted_mean_ci=mean_ci(x,z)) for key,x in values.items()}))
    return dict(purpose=purpose,units={'mbb':'bb/100 after multiplying harness mbb/hand by 0.1',
                                     'game_pts':'per game','round_pts':'per duplicate set'},
                inference='Paired complete duplicate tables; seed blocks retained. Intervals exclude opponent model error. Tuning results cannot confirm selected performance.',
                comparisons=tests,summary=summary,evidence=evidence,table_metrics=series)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('files',nargs='+')
    p.add_argument('--purpose',required=True)
    p.add_argument('--output',required=True)
    args=p.parse_args();report=summarize(args.files,args.purpose)
    Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
    for row in report['summary']:
        print(Path(row['bot']).name,row['tables'],{key:metric['mean_ci95'] for key,metric in row['metrics'].items() if key.startswith('delta')})


if __name__=='__main__':main()
