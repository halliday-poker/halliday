# Offline analysis

## Current rerun: newest intervals and exact main

[Newest-segment analysis](reports/latest-analysis-20261004-r2.md) uses the
completed new upload (actions SHA-256
`5e375a6e55ccec731fbb047758cf47192aeb2c3d89821a14290aa771029a91c1`).
The baseline is the exact `bot/` tree from main `6cfdf0f`, preserved as
`snapshots/main_6cfdf0f_r2`, hash `26121bc2`. It contains no analysis-branch
engine hook. The strict field has 65 external identities with trusted latest
ladder intervals; its pool is `sparring/competitors/from_data/latest-pool.txt`.

The primary [replay audit](reports/halliday-performance-20261004-r2.md) selects
44 games where Halliday and every opponent are in their newest observed
intervals. It reports +275 chips, 82.30% hands folded, one probable bad terminal
call and three probable missed calls. These are model-dependent review flags.
Neither upload timing nor display names identify the deployed Git source.

[Complete reproduction commands](reports/reproduce-latest-20261004-r2.md)
cover freezing input, fitting, explicit match selection, four-GPU auditing,
exact-main field/tournament/fidelity runs and verification. The exact main
engine currently needs CPU simulation; model fitting and replay auditing use
four parallel V100s. [Evidence](reports/evidence/20261004-r2/index.json) records
the actual devices, source fingerprints and selection. The general `pool.txt`
also includes unknown-time and validation identities and is not this strict pool.

## Earlier study

- [Halliday performance and decision audit](reports/halliday-performance-20261004.md)
  ([HTML](reports/halliday-performance-20261004.html)): fold rates, model-supported
  blunders, every losing game, runout effects and concrete hand histories.
- [Opponent estimates and predictive comparison](reports/opponent-refresh-20261004.md):
  successful-upload hypothesis, held-out tests and latest interval per identity.
- [Simulation fidelity](reports/simulation-fidelity-20261004.md): observed versus
  recreated behavior, including opponents' historical intervals and model sensitivity.
- [Strategy experiments](reports/strategy-benchmarks-20261004.md): isolated strategy
  changes, weighted bluffing, independent confirmation and submission checks.

Reports describe the frozen October 4 snapshot with actions SHA-256
`10331deef87e5cacb4e09ac79c5ebe2d4aeb4ff477b153d20cdb7de8fbd01d9a`.
The older October 3 reports remain historical artifacts. Generated raw inputs,
feature caches and full game/decision records live under ignored `results/`.
Opponent replicas live separately in `sparring/competitors/from_data/`. Compact
[flagged-action CSV](reports/halliday-blunders-20261004.csv) and
[match-review CSV](reports/halliday-match-reviews-20261004.csv) are versioned
alongside the report; full action classifications remain in local results.

The [compact evidence bundle](reports/evidence/20261004/index.json) records source
digests, frozen experiment plans, comparative results, tournament checks and CPU
resource checks. `python -B analysis/export_evidence.py` rebuilds it from the
completed local runs. Large raw inputs and game logs are intentionally excluded.
In JSON, `mean_ci95` is `[mean, half_width]`; bootstrap intervals are endpoints.
All simulation intervals exclude error in the opponent models.

The completed strategy study contains 103,027 full 100-hand simulations and
18 restricted CPU games, plus smoke tests. None of the eighteen isolated
strategy variants established an improvement; the merged main bot remains the
selected source. See the strategy report for failed and inconclusive results.

The later steal experiments are reproducible with `build_steal_variants.py`;
their frozen seeds, table counts and candidate hashes are in the evidence
bundle. `trace_steals.py` records the additional-open hand diagnostic,
`verify_steal_trace.py` checks its accounting and bootstrap summary, and
`verify_scalar_features.py` checks the optimized inference features against
the unchanged batch calculation on every replay decision.

## Reproduce the earlier replay audit

Use Python 3.12 with NumPy and the vendored/installed macpoker SDK. CUDA work
requires an NVIDIA driver and nvcc as described in the harness documentation.
Freeze `actions.jsonl`, `matches.json` and `state.json` together before starting.

```sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
python -B analysis/halliday_performance.py extract --snapshot analysis/results/refresh-20261004/source
python -B analysis/halliday_performance.py prepare
python -B analysis/halliday_performance.py compute --devices 0,1,2,3
python -B analysis/halliday_report.py
python -B analysis/verify_halliday_report.py
python -B analysis/render_halliday_report.py
```

All stages accept `--directory` to isolate a separate run. The report distinguishes
public-information decision models from actual-hidden-card hindsight. Most folds
have unresolved future betting, so terminal missed-call flags are not an estimate
of the exact unnecessary-fold rate for every decision.

See [opponent-model workflow](../opponent_model/README.md) and
[harness workflow](../harness/README.md) for model refreshes, paired experiments,
four-round simulations and Linux resource checks. `build_variants.py --only NAME`
creates a fresh experiment and refuses to overwrite existing candidates. The
baseline and candidate source directories remain separate from the production bot.
