"""Recreate observed lineups using each identity's interval at that match."""
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sparring.competitors.build import latest_profiles
from sparring.competitors.catalog import record, spec, write_catalog
DIRECTORY=ROOT/'analysis/results/refresh-20261004'


def main():
    report=json.loads((DIRECTORY/'opponent-estimates.json').read_text())
    profiles=latest_profiles(report)
    matches=json.loads((DIRECTORY/'source/matches.json').read_text())
    ids=set(profiles['Halliday']['match_ids'])
    destination=DIRECTORY/'fidelity-opponents'
    destination.mkdir(exist_ok=True)
    # Resolve historical policies beside their own catalogue, so a later field
    # refresh cannot silently substitute different model weights.
    policy=DIRECTORY/'policy-refit-upload.npz'
    shutil.copyfile(policy,destination/'behavior-policy.npz')
    catalog=destination/'bots.json'
    tables=[];provenance=[];bots={}
    for match in sorted((m for m in matches if m['id'] in ids and m['kind']=='ladder'),key=lambda m:(m['at'],m['id'])):
        lineup=[];segments={}
        for name in match['names']:
            if name=='Halliday':continue
            segment=next(s for s in report['bots'][name]['segments'] if match['id'] in s['match_ids'])
            identity=profiles[name]['id']+f'_epoch_{segment["epoch"]}'
            value=record(name,segment)
            if identity in bots and bots[identity]!=value:raise ValueError(f'Changed epoch: {identity}')
            bots[identity]=value
            lineup.append(spec(catalog.relative_to(ROOT),identity))
            segments[name]=dict(epoch=segment['epoch'],latest=segment['epoch']==profiles[name]['epoch'])
        tables.append(lineup);provenance.append(dict(match=match['id'],segments=segments))
    write_catalog(catalog,bots)
    (DIRECTORY/'historical-interval-tables.json').write_text(json.dumps(tables,indent=2)+'\n')
    (DIRECTORY/'historical-interval-table-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(f'{len(tables)} observed tables; '+str(sum(not s['latest'] for m in provenance for s in m['segments'].values()))+' opponent seats differed from newest interval')


if __name__=='__main__':main()
