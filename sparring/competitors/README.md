# Fitted competitors

The October 4 field has **77 observed identities** in `from_data/`, with a
76-opponent pool excluding Halliday. The latest Halliday replica is available
separately. Display names are identities in this dataset; possible renames are
not merged without evidence. `Gladiator` has no action replay and cannot be
recreated; `Gladiator_v3` is a separately observed name. The final entrant list
is unknown. The house validation bot remains in the general pool for stress
testing, but `harness/tournament.py` excludes it from its team roster.

Each replica subclasses `sparring/param.py`. The ten estimated scaffold settings
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
