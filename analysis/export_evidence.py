"""Export compact, reviewable evidence while leaving raw replay/game files local."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'analysis/results/refresh-20261004'
AUDIT = ROOT / 'analysis/results/halliday-performance-20261004'
OUT = ROOT / 'analysis/reports/evidence/20261004'


def export():
    OUT.mkdir(parents=True, exist_ok=True)
    files = [
        'source-audit.json', 'behavior-comparison.json', 'closed-loop-fidelity.json',
        'confirmation-plan.json', 'stress-plan.json', 'tournament-replication-plan.json',
        'field-priors-plan.json', 'main-integration-plan.json',
        'tuning-all-summary.json', 'tuning-reference-summary.json',
        'confirmation-summary.json', 'reference-confirm-summary.json',
        'eight-seat-confirm-summary.json', 'default-confirm-summary.json',
        'tournament-replication-summary.json', 'four-round-verification.json',
        'tournament-replication-00-09-verification.json',
        'tournament-replication-10-19-verification.json',
        'tournament-replication-20-39-verification.json',
        'field-priors-summary.json', 'main-integration-summary.json',
        'baseline-resource-check.json', 'mixed65-resource-check.json',
        'main-resource-check.json', 'feature-batching-check.json', 'package-checks.json',
        'main-package-check.json',
        'steals-plan.json', 'steals-summary.json', 'steal-hypothesis-exact.json',
        'steals-action-summary.json', 'minimum-steal-plan.json',
        'minimum-steal-summary.json', 'minimum-steal-resource.json',
        'scalar-features-check.json',
    ]
    index = {}
    for name, source in [(name, RUN/name) for name in files] + [
        ('halliday-summary.json', AUDIT/'summary.json'),
        ('halliday-verification.json', AUDIT/'verification.json'),
    ]:
        raw = source.read_bytes()
        data = json.loads(raw)
        removed = []
        # Full table vectors and per-match hand counts are large, reproducible
        # local artifacts. Keep their source digest, all summaries and metadata.
        for key in ('table_metrics', 'match_hands'):
            if key in data:
                data.pop(key)
                removed.append(key)
        target = OUT/name
        target.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')
        index[name] = dict(source=str(source.relative_to(ROOT)),
                           source_sha256=sha256(raw).hexdigest(), omitted_keys=removed,
                           exported_sha256=sha256(target.read_bytes()).hexdigest())
    for name in ('final-tests.log', 'gpu-concurrency.txt', 'followup-tests-cuda.log'):
        source = RUN/name
        raw = source.read_bytes()
        (OUT/name).write_bytes(raw)
        index[name] = dict(source=str(source.relative_to(ROOT)), sha256=sha256(raw).hexdigest())
    source = RUN/'four-round-confirm.json'
    raw = source.read_bytes()
    data = json.loads(raw)
    compact = {key:data[key] for key in ('args', 'compute', 'elapsed_s', 'commit',
                                        'summary', 'bad_games', 'assumptions')}
    compact['games'] = len(data['games'])
    compact['events'] = len(data['events'])
    name = 'initial-tournament-summary.json'
    (OUT/name).write_text(json.dumps(compact, indent=2)+'\n')
    index[name] = dict(source=str(source.relative_to(ROOT)), source_sha256=sha256(raw).hexdigest(),
                       omitted_keys=['per-game records', 'per-event standings'])
    (OUT/'index.json').write_text(json.dumps(index, indent=2)+'\n')
    print(f'Exported {len(index)} evidence files to {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    export()
