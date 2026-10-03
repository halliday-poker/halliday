# Fitted competitors

## Data catalogue and shared loader

`from_data/bots.json` stores all 89 opponents' executable settings: a stable
ID, display name, ten `param.py` scaffold parameters, and optional learned
policy configuration. JSON keeps the nested policy settings readable without
embedding serialized objects in CSV cells. `competitor_base.py` is the shared
implementation; no Python source is generated for individual opponents.
`profiles.json` retains the larger analysis evidence and uncertainty separately.

Pool entries select a record from the catalogue:

```text
fitted:sparring/competitors/from_data/bots.json@catherine 1
```

The same spec works as a candidate in `harness/eval.py`, in tournament pools,
and in JSON table lineups. The loader reads policy paths relative to the
catalogue, shares model weights within a worker, and creates fresh counters,
settings and a seeded RNG for each game. Bot hashes include the selected
record, policy weights and shared implementation. Archived pool entries naming
removed generated `.py` files resolve to their catalogue IDs in the harness;
the SDK's standalone Python-file loader does not load catalogue specs.

Regenerate the catalogue and pools from the current fitted report:

```sh
.venv-estimators/bin/python -B sparring/competitors/build.py analysis/results/refresh-20261004-r3/opponent-estimates.json --policy analysis/results/refresh-20261004-r3/policy-refit-upload.npz
.venv-estimators/bin/python -B harness/eval.py run bot --no-league --no-extend --pool sparring/competitors/from_data/latest-pool.txt --tables 400 --device auto --workers 12
```

For parameter experiments, edit a record's `style` in `bots.json`. If it has a
learned `policy`, its `weight` controls policy use; set it to `0` to use only
the scaffold. A rebuild replaces manual catalogue edits with fitted values,
updates pool membership and removes obsolete generated wrappers. It preserves
unrelated Python helpers. `--destination` selects another directory inside the
repository. `param_reference/bots.json` stores the historical scaffold-only
field using the same format and loader.

## Current data refresh (October 4, r3)

`from_data/` now contains 89 observed identities fitted to the new frozen upload.
The strict newest-field pool is **`from_data/latest-pool.txt`**, with 65 external
identities having reliably dated ladder observations. It excludes Halliday,
the house bot, one validation-only identity and 21 identities without trusted
play timestamps. No included identity has a later successful upload without
observed ladder evidence. These are newest observed intervals, not verified
deployment hashes; old aliases cannot always be resolved to teams.

The general `pool.txt` still includes every observed identity except Halliday;
use `latest-pool.txt` for the requested latest-only comparison. All 89 generated
profiles remain available for inspection. Historical intervals inform shared
model training, while only each selected latest interval is instantiated.

The catalogue now uses the r3 upload of 2,230 replay matches. The
[within-game report](../../analysis/reports/within-game-patterns-20261004-r3.md)
includes refreshed parameters, per-game trajectories and explanations for the
66 reliably dated identities including Halliday. No temporal policy is promoted
from this diagnostic study.

## Previous exact-main performance study (r2)

The previous study used an exact copy of main `6cfdf0f`, hash `26121bc2`.
This command now evaluates it against the refreshed r3 field; the linked r2
results retain their original opponent weights and input hashes:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B harness/eval.py run snapshots/main_6cfdf0f_r2 --no-league --no-extend --pool sparring/competitors/from_data/latest-pool.txt --tables 400 --deals 100 --device auto --workers 12 --seed latest-main-r2-20261004
```

Auto mode selects CPU for this unmodified engine because it lacks the GPU hook.
Four V100s run the model fitting and replay-equity audit. See [the previous
report](../../analysis/reports/latest-analysis-20261004-r2.md) and [complete
reproduction commands](../../analysis/reports/reproduce-latest-20261004-r2.md).

## First October 4 upload (historical)

The October 4 field has **77 observed identities** in `from_data/`, with a
76-opponent pool excluding Halliday. The latest Halliday replica is available
separately. Display names are identities in this dataset; possible renames are
not merged without evidence. `Gladiator` has no action replay and cannot be
recreated; `Gladiator_v3` is a separately observed name. The final entrant list
is unknown. The house validation bot remains in the general pool for stress
testing, but `harness/tournament.py` excludes it from its team roster.

Each replica uses the shared subclass of `sparring/param.py`. The ten estimated scaffold settings
remain an interpretable fallback. A compact NumPy model predicts actions and
legal raise-size mixtures from own cards and public context, plus identity and
candidate upload interval. It uses no hidden cards or future outcomes. Private
per-game sampling is seeded by the harness. Seventy-four identities use this
model; three sparse/validation-only fits use the scaffold. The known `house:call`
behavior is implemented exactly as call/check.

`from_data/profiles.json` preserves interval evidence, input/model hashes,
parameter uncertainty, conditional behavior rates, match IDs and timestamps.
`from_data/behavior-policy.npz` contains the shared NumPy weights.
`param_reference/` preserves the refreshed original ten-parameter replicas for
cross-model tests. None of these opponents or weights is part of a submission.

```sh
python sparring/competitors/build.py analysis/results/refresh-20261004/opponent-estimates.json --policy analysis/results/refresh-20261004/policy-refit-upload.npz
python harness/eval.py run snapshots/analysis_baseline_20261004 --no-league --pool sparring/competitors/from_data/pool.txt --tables 400 --deals 100 --device cuda --gpu-devices 0,1,2,3 --gpu-workers 16 --seed refreshed-latest-field
```

The builder verifies scaffold and policy fingerprints and selects the newest
interval containing a trusted server play time, using collection chronology
when none is available. Legacy reports without policy models remain supported.
Successful validation marks an upload, not a guaranteed deployment; failed
checks and unknown-time validations do not define version boundaries. This
choice improves held-out predictions compared with no segmentation and matched
randomized boundaries. Sparse executable styles shrink toward the full-bot fit.

See [predictive evidence](../../analysis/reports/opponent-refresh-20261004.md),
[Halliday's replay audit](../../analysis/reports/halliday-performance-20261004.md),
and the [historical October 3 evaluation](EVALUATION.md). The replicas are
approximations, not recovered source code. Better held-out action predictions
do not guarantee realistic closed-loop winnings, especially at unseen contexts
or against changed strategies. Original `eval.py run` compares duplicate tables;
`harness/tournament.py` additionally simulates four rounds with regrouping and
explicit roster/tie assumptions.
