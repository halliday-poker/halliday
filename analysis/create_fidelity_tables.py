"""Recreate observed lineups using each identity's interval at that match."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'analysis/results/refresh-20261004'


def main():
    report=json.loads((DIRECTORY/'opponent-estimates.json').read_text())
    profiles=json.loads((ROOT/'sparring/competitors/from_data/profiles.json').read_text())['profiles']
    matches=json.loads((DIRECTORY/'source/matches.json').read_text())
    ids=set(profiles['Halliday']['match_ids'])
    destination=DIRECTORY/'fidelity-opponents'
    destination.mkdir(exist_ok=True)
    tables=[];provenance=[]
    for match in sorted((m for m in matches if m['id'] in ids and m['kind']=='ladder'),key=lambda m:(m['at'],m['id'])):
        lineup=[];segments={}
        for name in match['names']:
            if name=='Halliday':continue
            segment=next(s for s in report['bots'][name]['segments'] if match['id'] in s['match_ids'])
            filename=Path(profiles[name]['file']).stem+f'_epoch_{segment["epoch"]}.py'
            path=destination/filename
            source=('import importlib.util\nfrom pathlib import Path\n'
                    '_path=Path(__file__).resolve().parents[4]/"sparring/competitors/from_data/competitor_base.py"\n'
                    '_spec=importlib.util.spec_from_file_location("_observed_competitor_base",_path)\n'
                    '_base=importlib.util.module_from_spec(_spec)\n_spec.loader.exec_module(_base)\n'
                    'class CompetitorBot(_base.FittedBot):\n'
                    f'    DISPLAY_NAME={name!r}\n    STYLE={segment["surrogate_style"]!r}\n    POLICY={segment["behavior"]!r}\n'
                    'def make_seeded_bot(seed):\n    return CompetitorBot(seed=seed)\n')
            if path.exists() and path.read_text()!=source:raise ValueError(f'Changed epoch: {path}')
            path.write_text(source)
            lineup.append(str(path.relative_to(ROOT)))
            segments[name]=dict(epoch=segment['epoch'],latest=segment['epoch']==profiles[name]['epoch'])
        tables.append(lineup);provenance.append(dict(match=match['id'],segments=segments))
    (DIRECTORY/'historical-interval-tables.json').write_text(json.dumps(tables,indent=2)+'\n')
    (DIRECTORY/'historical-interval-table-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(f'{len(tables)} observed tables; '+str(sum(not s['latest'] for m in provenance for s in m['segments'].values()))+' opponent seats differed from newest interval')


if __name__=='__main__':main()
