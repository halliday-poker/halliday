# Updated Halliday against the fitted field

Completed 3 October 2026 after merging origin/main `e10a7ef` into
`codex/opponent-estimators` (merge `717b206`). Candidate `bot/` content hash:
`3165289f`. The run used the latest segment of each of the 66 external
identities, with equal sampling weight. The historical Halliday fit was excluded
from this pool and remains available as `from_data/halliday.py`.

## Result

| Metric | Result |
|---|---:|
| Duplicate tables | 400 |
| Games | 2,005 |
| Hands | 200,500 |
| Winnings, milli big blinds per hand | +262.8 ± 50.4 (95% CI) |
| Winnings, big blinds per 100 hands | +26.28 ± 5.04 |
| Game points | 3.386 ± 0.074 |
| Round placement points | 3.744 ± 0.135 |
| First place in a table's duplicate set | 36.50% |
| Candidate or opponent failures | 0 |
| Slowest Halliday decision | 44.69 ms |
| Maximum Halliday clock use | 6.42% |
| Wall time reported by harness | 132 seconds |

The intervals are calculated across independent duplicate tables. Every one of
the 66 profiles appeared, on 14–36 tables each. All
10,241 player-game verdicts were OK, with no crashes,
timeouts or protocol violations. The full game records were checked for complete
seat rotations and zero-sum chips, and the headline winnings interval was
recomputed from the saved games.

These results apply to the fitted surrogate field. They do not establish the
same win rate against real source bots or predict final tournament standings.
The harness uses tournament game/round scoring on random tables; it does not
implement the four-round cumulative-score regrouping. This was a field evaluation,
not a league promotion gate.

## Execution and reproducibility

The command below uses the current `from_data/` layout. The archived run keeps
the original paths; moving the generated files did not change any fitted style.
A fresh four-table, 21-game check after the move completed without failures,
and the full suite again passed 94 tests with two GPU-only checks skipped.

The earlier profile analysis used all four V100s in parallel. This simulation
used eight CPU workers; at the time the harness had no CUDA execution path.
The subsequently added [GPU workers](../../harness/README.md#gpu-workers) have
separate [validation results](../../harness/GPU_VALIDATION.md). The results above
remain the original CPU evaluation.

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B -u harness/eval.py run bot --no-league --pool sparring/competitors/from_data/pool.txt --tables 400 --deals 100 --sizes 4,5,5,6 --workers 8 --seed competitors-latest-20261003 --label latest-competitor-segments
```

The merged test suite passed 94 tests; two GPU-only tests were skipped in the
sandbox. The six competitor tests cover latest-segment selection, filename
collisions, every generated profile, SDK loading, independent seeded RNGs,
fresh game state, and legal repeatable games across the entire fitted field.

Local artifacts (ignored by Git):

- [Full harness results](../../harness/results/20261003-215259.json)
- [Frozen profile snapshot](../../harness/results/20261003-215259-competitors.json)
- [Output validation](../../harness/results/20261003-215259-validation.json)
- [Run log](../../harness/results/competitors-latest.log)
- [Test log](../../analysis/results/competitor-tests.log)

The profile manifest is [profiles.json](from_data/profiles.json); its
source report SHA-256 is `90206a2cd6cdee1bfc8630dd39488184e293e823b7f50afeb7d1135d653c62f3`.
