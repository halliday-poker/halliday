"""Cache public replay metadata for validation outcomes in a frozen snapshot."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from urllib.request import Request,urlopen


def fetch(match_id):
    request=Request('https://convex.poker.monashcoding.com/api/query',
                    data=json.dumps({'path':'tournament:replay','args':{'matchId':match_id}}).encode(),
                    headers={'Content-Type':'application/json'})
    for attempt in range(3):
        try:
            with urlopen(request,timeout=30) as response:
                value=json.load(response)
            if value.get('status')!='success' or not value.get('value'):
                raise ValueError(f'No successful replay metadata for {match_id}')
            return match_id,value
        except Exception:
            if attempt==2:raise
            time.sleep(attempt+1)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--matches',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    matches=json.loads(args.matches.read_text())
    if isinstance(matches,dict):matches=matches.get('matches',list(matches.values()))
    ids=sorted({m['id'] for m in matches if m.get('kind')=='validation'})
    existing=json.loads(args.output.read_text()) if args.output.exists() else {}
    missing=[i for i in ids if i not in existing]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for key,value in pool.map(fetch,missing):
            existing[key]=value
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(existing,indent=2)+'\n')
    print(f'{len(ids)} validation matches; fetched {len(missing)}; {args.output}')


if __name__=='__main__':main()
