# Reproduce the opponent-group experiment

Run from the repository root on Linux with Python 3.12. The original run used
NumPy 2.3.5, PyTorch 2.10.0+cu128 and Matplotlib 3.11.2. Four shared V100s each
had about 1 GiB free. Refitting and decision auditing use all four; the measured
fastest simulation configuration was 16 CPU workers. No GPU is required by the
submitted bot.

The feature branches are `feat/opponent-groups` (main-based call behavior) and
`feat/opponent-groups-call-calibration` (calibrated call behavior). Frozen bot
directories allow all four policies to be compared from either checkout.
Main is pinned to `6cfdf0f44b332933d88d440791e7151028061849`; call calibration is
pinned to `e186308ade4a05778d68a82b9fd636adb46e999b`. No promotion or PR is part
of this experiment.

## Environment

Use an isolated checkout when rebuilding parameters. The commands below assume
the existing `.venv-estimators` environment. To create an equivalent environment:

```sh
python3.12 -m venv .venv-estimators
.venv-estimators/bin/python -m pip install numpy==2.3.5 matplotlib==3.11.2
.venv-estimators/bin/python -m pip install torch==2.10.0 \
  --index-url https://download.pytorch.org/whl/cu128
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export OPPONENT_CUDA_MEMORY_MIB=512
```

The repository's `vendor/macpoker-src` supplies the tournament SDK. CUDA auditing
also needs the compiler/runtime described in `harness/GPU_VALIDATION.md`.
`unshare` user/mount/network namespaces must be available for resource checks;
run these commands outside an enclosing sandbox that forbids those namespaces.

## Re-run the comparison using the committed replicas

This route uses the recorded fitted catalogue, public group priors, candidate
selection and frozen sources. It does not require the private raw replay file.
The initial manifest restoration intentionally refuses an existing study
directory; use a fresh checkout for a separate run.

```sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export OPPONENT_CUDA_MEMORY_MIB=512
.venv-estimators/bin/python -B - <<'PY'
import json, shutil
from pathlib import Path
evidence=Path('analysis/reports/evidence/opponent-groups-20261004')
run=Path('analysis/results/opponent-groups-20261004')
run.mkdir(parents=True,exist_ok=False)
(run/'input').mkdir()
for name in ('study-plan.json','study-extension.json','baseline-manifest.json',
             'calibration-manifest.json','variants-manifest.json',
             'candidate-selection.json','backend-selection.json','groups-fit.json',
             'group-integration-verification.json'):
    shutil.copyfile(evidence/name,run/name)
# Existing manifest skips raw-input freezing; the simulation uses only replicas.
shutil.copyfile(evidence/'snapshot-manifest.json',run/'input/snapshot-manifest.json')
PY
.venv-estimators/bin/python -B -u analysis/run_opponent_groups.py --stage smoke
.venv-estimators/bin/python -B -u analysis/run_opponent_groups.py --stage simulate-four
.venv-estimators/bin/python -B -u analysis/run_opponent_groups.py --stage audit
```

This runs **10,000 games per policy**, 40,000 executions and 4,000,000 hands.
Each table has Halliday plus three to five distinct random opponents from the
69-identity pool. Every 100-hand game resets stacks to 200 per hand, uses 1/2
blinds and the tournament clock (30 s + 100 ms per hand); every selected table
completes all seat rotations. This models duplicate tables, not the entire
four-round tournament or its regrouping/podium distribution.

The policy order is main, calibration, groups + calibration, groups + main.
The final seed is `opponent-groups-confirm-20261004`. Results and resumable
traces are written under the study directory. The optional three-policy
`simulate` stage exists to preserve the original run; use **`simulate-four`**
for the complete experiment. Repeating it resumes matching completed games.
Do not edit bot snapshots, harness or replica catalogue during a run.

## Refit from the raw snapshot and rebuild the complete report

Raw replay files are local data, not committed artifacts. Provide the recorded
`actions.jsonl`, `matches.json` and `state.json` together under
`analysis/results/input-snapshot`. The recorded actions SHA-256 is:

```text
0d095948334a0464ddc27e138feb8c3ea5fcf5964cc965636187518f9951e44c
```

The snapshot contains 2,647,907 records, 2,654 replays and 2,664 metadata matches;
ten metadata matches lack a replay. Check every raw file against the input
manifest. Freezing validates complete replays and preserves original collector
state if recovery is necessary. Use a **fresh checkout and empty study directory**
for this route, rather than the restored directory above.

```sh
git fetch origin main feat/call-calibration
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export OPPONENT_CUDA_MEMORY_MIB=512
for stage in freeze refit groups snapshots tests smoke resources benchmark pilot extend integration simulate-four audit report
do
  .venv-estimators/bin/python -B -u analysis/run_opponent_groups.py --stage "$stage" || break
done
```

`refit` expands to `prepare`, `train`, `select`, `refit-models`, `build`, and
`verify`; each also runs separately with `--stage` for diagnosis. Training uses
four parallel GPU jobs for the static/progress/history/combined models. The
parameter estimator uses every newest-version observation at full weight, with
parameter-specific discounted older support when sparse. Selection checks
within-game history patterns and runtime/training parity. The replica builder
writes JSON plus shared NumPy model files, never one Python file per bot.

`groups` extracts public prefixes, chooses the group model on validation games,
checks held-out identification and exports compact priors. `snapshots` freezes
five pilot policies; `pilot` uses 600 games each with seed
`opponent-groups-pilot-20261004`. Full or half counter strength is selected by
total paired pilot chips; range-only adaptation is diagnostic. The selected
strength is shared by both final grouped variants. The main-based version
disables the two call rescues and shifts both base and target river margin by
-0.04, so its grouping adjustments match those of the calibrated version.

The checked-in snapshots are immutable. Exact source equality is required when
reusing their names. A different input or a refit that differs numerically needs
a fresh experiment name (pass `--directory analysis/results/NEW_NAME` at every
stage) in a separate checkout; never overwrite traces from the old experiment.
Compare the selection and manifests before treating such a run as a replication.
Model outputs, timed equity sample counts and GPU numerical details can differ
across hardware. Same seeds guarantee matched tables/deals, not bitwise-identical
decisions when time limits change sampling.

The report stage needs the refit files and `group-prefixes.npz`, so use the full
raw-data route to regenerate classification diagnostics. Final artifacts appear
in `analysis/reports`: paired return and placement intervals, game reviews,
blunder cases, parameter variances, public-prefix classification and figures.
Each stage writes its exact command, exit status and elapsed time to the study
directory. Evidence files and artifact hashes accompany the committed report.

## Direct simulation command

For a standalone comparison without refitting or regenerating report artifacts:

```sh
.venv-estimators/bin/python -B -u harness/eval.py run \
  snapshots/main_6cfdf0f_opponent_groups \
  snapshots/call_calibration_e186308_group_study \
  snapshots/opponent_groups_full snapshots/opponent_groups_main \
  --no-league --no-extend --games 10000 --deals 100 --sizes 4,5,5,6 \
  --seed opponent-groups-confirm-20261004 \
  --pool sparring/competitors/from_data_groups/latest-pool.txt \
  --device cpu --workers 16 \
  --trace-dir analysis/results/group-comparison-traces --resume
```

To benchmark CUDA instead, replace the backend options with `--device cuda
--gpu-devices 0,1,2,3 --gpu-workers 8`. Use a separate trace directory when changing
the experiment. The offline audit uses eight GPU workers (two per V100); a
nonzero device counter for each GPU is checked before a report is produced.
