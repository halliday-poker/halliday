# Reproduce the call-calibration comparison

Use branch `feat/call-calibration`, Python 3.12 and the estimator environment
(NumPy 2.3.5, PyTorch 2.10.0+cu128, Matplotlib 3.11.2, and the vendored SDK).
Run commands from the feature worktree root. In this workspace that is:

```sh
cd /mnt/ssd/halliday2/analysis/results/feat-call-calibration
```

The interpreter used for the recorded run is
`/mnt/ssd/halliday2/.venv-estimators/bin/python`. On another machine, substitute
the interpreter from your equivalent environment. CUDA fitting/auditing needs
four visible NVIDIA GPUs; the optional harness backend also needs `nvcc`.

## Full fresh run

Use a fresh checkout/results directory with the matching raw snapshot available.
The recorded actions hash is
`aa24a7cdad88692035f8e8ea8db22be0271b8667c96fd0344f0f78fe023b0b6d`.
The metadata/state hashes are included in the report's snapshot manifest.
The script freezes the source, chooses newest uploads, applies sparse recency
priors, refits the shared policies and generates JSON competitor records.

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /mnt/ssd/halliday2/.venv-estimators/bin/python -B -u \
  analysis/run_call_calibration.py --stage fit \
  --source /mnt/ssd/halliday2/analysis/results/input-snapshot

for stage in freeze verify tests benchmark pilot simulate audit report
do
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    /mnt/ssd/halliday2/.venv-estimators/bin/python -B -u \
    analysis/run_call_calibration.py --stage "$stage" || break
done
```

The frozen main reference defaults to
`6cfdf0f44b332933d88d440791e7151028061849`.
The freeze step checks/reuses the committed snapshots on a fresh checkout.
The pilot uses 500 games per variant and chooses between the core corrections
and those corrections plus a 0.06 tracked-range river call margin. It then
compares the selected version against main on **10,000 games each** using a
different seed. All tables contain Halliday plus 3–5 opponents; every duplicate
set completes all seat rotations. Games use 100 hands, 200-chip resets, 1/2 blinds,
30-second banks and 100 ms per-hand increments.

The backend stage compares 12 CPU workers with 12 CUDA workers on identical
120-game workloads and amortizes measured worker time over the full study, retaining startup/tail
overhead. The recorded final run chose CUDA. Fitting and audit also use all four
GPUs. When simulation uses CUDA, the audit stage first performs a separate
120-game CPU clock check.

Do not refit a study with existing simulation traces. The catalogue is shared
within its checkout: use a separate checkout for different input or fits.
An existing `analysis/results/refresh` is the frozen input for this study;
changing raw uploads does not silently replace it.

## Resume the recorded comparison

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /mnt/ssd/halliday2/.venv-estimators/bin/python -B -u \
  analysis/run_call_calibration.py --stage simulate
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /mnt/ssd/halliday2/.venv-estimators/bin/python -B -u \
  analysis/run_call_calibration.py --stage audit
/mnt/ssd/halliday2/.venv-estimators/bin/python -B \
  analysis/run_call_calibration.py --stage report
```

Resumption verifies source, model and job identities. Fixed seeds reproduce
tables and deals; timed sampling can vary with scheduling/hardware. Audit
sampling is deterministic for a stored trace and checked against code hashes.
Full traces and audit shards remain in
`analysis/results/call-calibration-20261004-r2/`; smaller review CSVs, plots and
provenance files are committed alongside the report.

## Direct simulation command used

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /mnt/ssd/halliday2/.venv-estimators/bin/python -B -u harness/eval.py run \
  snapshots/main_6cfdf0f_call_study snapshots/call_calibration_river \
  --no-league --no-extend --games 10000 --deals 100 --sizes 4,5,5,6 \
  --seed call-calibration-confirm-20261004 \
  --pool sparring/competitors/from_data_patterns/latest-pool.txt \
  --device cuda --gpu-devices 0,1,2,3 --gpu-workers 12 \
  --trace-dir analysis/results/call-calibration-20261004-r2/simulate-traces --resume
```

## Focused checks and wire-protocol smoke test

```sh
/mnt/ssd/halliday2/.venv-estimators/bin/python -B -m unittest discover \
  -s tests -p 'test_call_calibration.py'
/mnt/ssd/halliday2/.venv-estimators/bin/python -B -m unittest discover \
  -s tests -p 'test_call_comparison.py'
/mnt/ssd/halliday2/.venv-estimators/bin/python -B harness/eval.py smoke bot
```

The full test stage includes CPU/CUDA mathematical parity, legal actions,
newest-upload coverage, history-prefix isolation, sparse-prior weights, and
the reviewed pocket-jacks/full-house regression cases.
