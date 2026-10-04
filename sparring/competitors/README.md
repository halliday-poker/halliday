# Opponents reconstructed from match data

`from_data_patterns/` contains JSON catalogue records and two shared NumPy
policy files. The harness loads every competitor through `competitor_base.py`
and the `sparring/param.py` scaffold; no Python file is generated per opponent.
`profiles.json` records input hashes, upload boundaries, fit parameters,
uncertainty and prior weights. `latest-pool.txt` excludes Halliday, which is
replaced by the candidate under evaluation.

## Newest submissions and sparse data

Every timestamped `validation` against `house:call` starts a new upload interval,
regardless of verdict. All available observations in the newest interval have
weight one, including the upload game. For sparse parameters, older versions
receive at most `0.1 ** version_age * 2 ** (-upload_gap_hours / 6)`, stopping at
the effective support target for that parameter.

If a known newest upload has no replay, available earlier-version observations
can still supply a prior. Such identities are marked `prior_only`; their newest
behavior is unobserved, historical weights remain discounted, and their support
and uncertainty remain visible. Identities without a trusted upload boundary
are excluded because version age cannot be assigned reliably.

The shared policy uses public context and learned bot embeddings. Selected
preflop progress adjustments and history-dependent sizing use only observations
available before the current hand. Hidden opponent cards and future outcomes
never enter simulated bot decisions. Parameters describe replicas, not recovered
source code or guaranteed live behavior.

## Build and evaluate

```sh
python sparring/competitors/build.py \
  analysis/results/call-calibration-20261004-r2/fit/runtime-fit.json \
  --runtime-patterns --destination sparring/competitors/from_data_patterns
python harness/eval.py run bot --no-league \
  --pool sparring/competitors/from_data_patterns/latest-pool.txt
```

The policy files must match the hashes in the fit report. Changing a catalogue
invalidates existing simulation trace identities; use a separate checkout for
different fitting experiments.

See the [call-calibration report](../../analysis/reports/call-calibration-20261004.md)
and [reproduction commands](../../analysis/reports/call-calibration-20261004-reproduce.md).
