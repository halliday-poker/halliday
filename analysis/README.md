# Offline analysis

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

## Reproduce the replay audit

Use Python 3.12 with NumPy and the vendored/installed macpoker SDK. CUDA work
requires an NVIDIA driver and nvcc as described in the harness documentation.
Freeze `actions.jsonl`, `matches.json` and `state.json` together before starting.

```sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
python -B analysis/halliday_performance.py extract --snapshot analysis/results/input-snapshot
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
