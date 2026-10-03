"""Describe latest-interval first responses to small preflop opens."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from opponent_model.data import COL, load_cache


def main():
    run = ROOT/'analysis/results/refresh-20261004'
    profiles = json.loads((ROOT/'sparring/competitors/from_data/profiles.json').read_text())['profiles']
    data = load_cache(run/'context-features.npz')
    ids = {m['id']:i for i,m in enumerate(data.matches)}
    rows = []
    for name, profile in profiles.items():
        if name in ('Halliday', 'house:call') or profile['validation_only']:
            continue
        r = data.observations[name]
        r = r[np.isin(r[:,COL['match']], [ids[m] for m in profile['match_ids']])]
        r = r[r[:,COL['street']] == 0]
        # A player's first action in the hand cannot have followed its own
        # voluntary call/open. In particular, exclude limpers facing a raise.
        _, first = np.unique(r[:,[COL['match'],COL['hand']]],axis=0,return_index=True)
        r = r[np.sort(first)]
        mask = ((r[:,COL['pre_raises']] == 1) & (r[:,COL['top']] > 2)
                & (r[:,COL['top']] <= 6) & (r[:,COL['facing']] > 0))
        selected = r[mask]
        count = len(selected)
        rows.append(dict(bot=name,opportunities=count,
                         matches=int(len(np.unique(selected[:,COL['match']]))),
                         folds=int((selected[:,COL['action']] == 0).sum()),
                         fold_rate=float((selected[:,COL['action']] == 0).mean()) if count else None))
    qualified = [r['fold_rate'] for r in rows if r['opportunities'] >= 30]
    report = dict(source_sha256=data.audit['actions_sha256'],
                  context='First preflop response to exactly one raise, to more than 2 and at most 6 chips; latest selected ladder interval per identity.',
                  qualified_identities=len(qualified),minimum_opportunities=30,
                  median=float(np.median(qualified)),mean=float(np.mean(qualified)),rows=rows,
                  caveat='Descriptive observed-context rates. Not a causal estimate of new steals; defender position, open position, cards, and later betting can change returns.')
    (run/'steal-hypothesis-exact.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))


if __name__ == '__main__':
    main()
