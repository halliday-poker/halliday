# Reproduce the new-main comparison

This study evaluates main **a707565** once against the same 69 fitted opponents,
2,009 ordered duplicate tables and deck seed used by the completed call-calibration
study. The **10,000 calibration games are archived inputs**; none of the commands
below simulate calibration again. The evaluated source is
`snapshots/main_a707565_calibration_study`, exported exactly from main, not the
analysis branch's `bot/` directory. No strategy was tuned for this run.

Use the `analysis/main-calibration-20261004` checkout. The original environment is
Python 3.12, NumPy 2.3.5 and Matplotlib 3.11.2 in `.venv-estimators`, plus the
repository's `vendor/macpoker-src` SDK. The native CUDA audit needs the CUDA compiler
and runtime described in `harness/GPU_VALIDATION.md`. It uses eight workers across
four V100s and small device buffers. There is no GPU dependency in the submitted
main bot. The earlier matched backend benchmark favored 16 CPU simulation workers;
the exact main engine also has no batched CUDA entry point.

Run from the repository root:

```sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export OPPONENT_CUDA_MEMORY_MIB=512
```

## Reuse the committed control, then simulate only main

Use a fresh output directory so the original results remain intact. `restore`
copies the exact table list, frozen source manifest and compressed archived
calibration results from `analysis/reports/evidence/main-calibration-20261004`.
It validates SHA-256 hashes of the snapshot, harness, opponents and audit model.
It does not execute a bot.

```sh
.venv-estimators/bin/python -B analysis/run_main_calibration.py \
  --directory analysis/results/main-calibration-replication --stage restore
.venv-estimators/bin/python -B analysis/run_main_calibration.py \
  --directory analysis/results/main-calibration-replication --stage resources
.venv-estimators/bin/python -B -u analysis/run_main_calibration.py \
  --directory analysis/results/main-calibration-replication --stage simulate
.venv-estimators/bin/python -B -u analysis/run_main_calibration.py \
  --directory analysis/results/main-calibration-replication --stage audit
.venv-estimators/bin/python -B -u analysis/run_main_calibration.py \
  --directory analysis/results/main-calibration-replication --stage tactics
.venv-estimators/bin/python -B -u analysis/run_main_calibration.py \
  --directory analysis/results/main-calibration-replication --stage cases
.venv-estimators/bin/python -B analysis/report_main_calibration.py \
  --directory analysis/results/main-calibration-replication \
  --output analysis/results/main-calibration-replication/report
```

The six resource-check games run the actual wire protocol with one CPU,
a 512 MiB address-space limit, a read-only chroot, and private namespaces.
They are separate validation games and are excluded from the 10,000-game estimate.
Run this stage where Linux `unshare` user/mount/network namespaces are permitted.
If working inside a sandbox that forbids them, run that stage on the host.

`simulate` passes **only the frozen main candidate** to `harness/eval.py`.
It resumes completed, matching traces after interruption and preserves a completed
result rather than rerunning it. Do not edit any frozen source or catalogue while
simulating or auditing. To repeat independently, use a new directory.

Every table has 4–6 total seats, completes all seat rotations, and uses 100 hands
per game, fresh stacks of 200 chips each hand, 1/2 blinds, and 30 seconds plus
100 ms per hand. This is the tournament's duplicate-table format, not a simulation
of its four rounds of regrouping. Placement points follow the two-stage ranking
documented in `docs/game-format-scoring.md`.

## Direct simulation command

After restoring the table list, the underlying simulation command is:

```sh
.venv-estimators/bin/python -B -u harness/eval.py run \
  snapshots/main_a707565_calibration_study \
  --no-league --no-extend --deals 100 \
  --time-ms 30000 --increment-ms 100 \
  --seed opponent-groups-confirm-20261004 \
  --tables-json analysis/results/main-calibration-replication/tables.json \
  --pool sparring/competitors/from_data_groups/latest-pool.txt \
  --device cpu --workers 16 \
  --trace-dir analysis/results/main-calibration-replication/traces --resume
```

The table file fixes exactly 10,000 games. Do not combine `--tables-json` with
`--games`; the harness rejects those mutually exclusive selection methods.
The runner saves the harness result as `simulate.json` and records the command,
exit status and elapsed time. Prefer the runner when also producing the report.

## Original preparation and report regeneration

The initial run used these commands with the complete older study present locally:

```sh
.venv-estimators/bin/python -B analysis/run_main_calibration.py --stage prepare
.venv-estimators/bin/python -B analysis/run_main_calibration.py --stage resources
.venv-estimators/bin/python -B -u analysis/run_main_calibration.py --stage simulate
.venv-estimators/bin/python -B -u analysis/run_main_calibration.py --stage audit
.venv-estimators/bin/python -B -u analysis/run_main_calibration.py --stage tactics
.venv-estimators/bin/python -B -u analysis/run_main_calibration.py --stage cases
.venv-estimators/bin/python -B -u analysis/run_main_calibration.py --stage report
```

Preparation reads candidate 1 from
`analysis/results/opponent-groups-20261004/simulate.json`, plus its saved audits
and trace identities. It checks a rotation from every archived table against the
current opponent sources, harness, seed and rules. It freezes main's Git source
without an engine patch. Preparation requires the original local archives;
`restore` is the portable alternative using the committed compressed control.

For an existing completed study, rerun only `--stage report` to regenerate the
tables, figures and report from the saved simulation and audit files. Reports
include paired game/table CSVs, every strict decision flag, opponent-composition
statistics, PNG/SVG figures, source hashes, execution logs and compressed results
for both versions. No raw collector replay is needed to simulate the frozen field.

The comparison checks can be run independently:

```sh
.venv-estimators/bin/python -B -m unittest discover -s tests \
  -p test_main_calibration_comparison.py -v
```

The return interval uses 5,000 paired whole-table bootstrap draws; it weights
games equally while keeping all seat rotations together. Placement weights
duplicate tables equally. The harness console's average table rate may differ
slightly from the report's total-chips/total-hands rate when table sizes vary.
The frozen replica parameters are held fixed, so these
intervals exclude uncertainty from fitting or reconstructing real submissions.
The audit applies identical public-range models to both policies. Its probable
error labels are model-dependent, and failed bluffs or losing all-ins are not
automatically mistakes. Timed Monte Carlo samples can vary with hardware/load:
identical deck seeds do not promise bitwise-identical bot decisions.
