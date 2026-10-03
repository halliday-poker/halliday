# Reproduce newest-segment analysis — 20261004-r2

Run from the repository root with Python 3.12, the vendored macpoker SDK,
NumPy and the validated PyTorch 2.10.0+cu128 environment. CUDA analysis needs
four V100 devices and the native harness CUDA toolkit described in its README.
The exact recorded baseline is `6cfdf0f44b332933d88d440791e7151028061849` / `26121bc2`.

These commands reproduce the completed study from its frozen inputs and cached
validation outcomes. They replace derived outputs in the run directories and
regenerate `sparring/competitors/from_data`; they do not change `bot/`.

```sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
analysis_python=.venv-estimators/bin/python
analysis_run=analysis/results/refresh-20261004-r2
analysis_audit=analysis/results/halliday-performance-20261004-r2

$analysis_python -B analysis/run_refresh_models.py --directory "$analysis_run" --epochs 100

$analysis_python -B analysis/halliday_performance.py extract --snapshot "$analysis_run/source" --match-ids "$analysis_run/strict-latest-halliday-matches.json" --directory "$analysis_audit"
$analysis_python -B analysis/halliday_performance.py prepare --directory "$analysis_audit"
$analysis_python -B analysis/halliday_performance.py compute --directory "$analysis_audit" --devices 0,1,2,3
$analysis_python -B analysis/halliday_report.py --directory "$analysis_audit"
$analysis_python -B analysis/verify_halliday_report.py --directory "$analysis_audit"
$analysis_python -B analysis/render_halliday_report.py --directory "$analysis_audit"

$analysis_python -B analysis/run_latest_benchmarks.py --directory "$analysis_run" --tables 400 --events 10 --workers 12
$analysis_python -B analysis/run_latest_fidelity.py --directory "$analysis_run" --workers 12
$analysis_python -B harness/resource_check.py snapshots/main_6cfdf0f_r2 --repeats 3 --output "$analysis_run/main-resource-check.json"
$analysis_python -B -m unittest discover -s tests -v > "$analysis_run/tests-cuda.log" 2>&1
$analysis_python -B analysis/export_latest_analysis.py --directory "$analysis_run" --audit "$analysis_audit"
```

The resource checker requires Linux permissions for its isolation setup.
Input SHA-256 is `5e375a6e55ccec731fbb047758cf47192aeb2c3d89821a14290aa771029a91c1`. Cached
`source/` and `validation-meta.json` must be preserved alongside the code;
raw inputs are not committed. Seeds, selected match IDs, model hashes and
source manifests are in the evidence bundle. Wall-clock equity deadlines can
change completed sample counts under different host load, despite fixed seeds.

For another completed upload, create fresh directories and freeze current main:

```sh
git fetch origin main
analysis_python=.venv-estimators/bin/python
analysis_run=analysis/results/refresh-next
analysis_audit=analysis/results/halliday-performance-next
$analysis_python -B analysis/freeze_snapshot.py --source analysis/results/input-snapshot --directory "$analysis_run" --baseline-ref origin/main --baseline-output snapshots/main-next
$analysis_python -B -m opponent_model.fetch_validation --matches "$analysis_run/source/matches.json" --output "$analysis_run/validation-meta.json"
```

Then run the pipeline above with those new directory variables and use
`snapshots/main-next` for the resource check. New inputs imply new results;
the frozen current-run numbers are not asserted for future snapshots.
