"""Check single-action inference against the unchanged batched feature path."""
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from opponent_model.data import load_cache
from sparring.competitors.policy import features


def main():
    run = ROOT/'analysis/results/refresh-20261004'
    data = load_cache(run/'context-features.npz')
    outcomes = []
    for dtype in (np.float32, np.float64):
        began = time.perf_counter()
        count = 0
        for bot, source in data.observations.items():
            rows = source.astype(dtype)
            expected = features(rows)
            for index, row in enumerate(rows):
                actual = features(row)
                if not np.array_equal(actual[0], expected[index]):
                    raise AssertionError(f'Feature mismatch: {dtype}, {bot}, row {index}')
            count += len(rows)
            print(f'{np.dtype(dtype)} {bot}: {count} exact rows', flush=True)
        outcomes.append(dict(dtype=str(np.dtype(dtype)),rows=count,bitwise_equal=True,
                             seconds=time.perf_counter()-began))
    result = dict(source_sha256=data.audit['actions_sha256'],
                  policy_sha256=sha256((ROOT/'sparring/competitors/policy.py').read_bytes()).hexdigest(),
                  checks=outcomes,scope='All replay decision rows; single-action features equal the unchanged multi-row feature path exactly. This checks values, not end-to-end game speed.')
    (run/'scalar-features-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
