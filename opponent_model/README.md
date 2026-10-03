# Offline opponent estimates and behavior replicas

## October 4 refresh

The V100 analysis was validated with Python 3.12.14, NumPy 2.3.5 and PyTorch
2.10.0+cu128. An isolated Linux environment can be prepared with:

```sh
uv venv .venv-estimators --python 3.12
uv pip install --python .venv-estimators/bin/python numpy==2.3.5
uv pip install --python .venv-estimators/bin/python torch==2.10.0 --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv-estimators/bin/python vendor/macpoker-*.whl
```

Use that interpreter for the commands below. The simulation harness uses a
separate native CUDA kernel compiled for `sm_70` with CUDA toolkit 12.8; its
workers do not import PyTorch. See [GPU validation](../harness/GPU_VALIDATION.md).
The historical RTX configuration later in this document is a different setup.

The current field uses successful-upload intervals and a compact public-context
action/raise-size model. The original ten-parameter estimates below remain the
interpretable scaffold and sparse-data fallback. See the [predictive comparison
and provenance](../analysis/reports/opponent-refresh-20261004.md).

Validation against `house:call` marks an upload, not a confirmed deployment:
passing uploads must still be selected as main. Failed validation and unknown
play-time events cannot define intervals. `validation.py` tests this distinction;
timestamp provenance distinguishes server milliseconds from collection-time
seconds. Unknown-time games use the shared base interval. Segmentation is
supported by whole-held-out-match predictions and a randomized-boundary control.

Reproduce using a frozen directory with `source/{actions.jsonl,matches.json,state.json}`
and `validation-meta.json` (public `tournament:replay` API responses keyed by ID):

```sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
python -B -m opponent_model.fetch_validation --matches analysis/results/refresh-20261004/source/matches.json --output analysis/results/refresh-20261004/validation-meta.json
python -B -m opponent_model --data-dir analysis/results/refresh-20261004/source --save-cache analysis/results/refresh-20261004/context-features.npz --output analysis/results/refresh-20261004/baseline-estimates.json --devices cuda:0 cuda:1 cuda:2 cuda:3 --bootstrap 1000 --permutations 4999 --batch-size 128 --memory-limit-mib 768
python -B -m opponent_model.behavior prepare --directory analysis/results/refresh-20261004
python -B -m opponent_model.behavior train --directory analysis/results/refresh-20261004 --epochs 100
python -B -m opponent_model.behavior compare --directory analysis/results/refresh-20261004
python -B -m opponent_model.behavior refit --directory analysis/results/refresh-20261004 --devices 0
python -B -m opponent_model.refresh --directory analysis/results/refresh-20261004 --devices 1,2,3
python sparring/competitors/build.py analysis/results/refresh-20261004/opponent-estimates.json --policy analysis/results/refresh-20261004/policy-refit-upload.npz
```

The four ablations train simultaneously on four distinct GPUs. They use a
60/20/20 split by whole match, exclude team validation hands, and choose stopping
and model only on validation data. The test split assesses interpolation to
unseen matches from observed versions; it cannot validate future versions.
Runtime replicas use NumPy, own cards and public game context only. They do not
load PyTorch or hidden opponent cards. The candidate submission uses neither the
replica model nor historical opponent profiles.

Fresh feature caches have 37 raw context columns. Legacy caches remain readable
for the original estimator, with extra fields explicitly missing; neural
training refuses missing-context caches. The original report format remains
supported by `build.py`, without `--policy`.

## Original scaffold estimator

This package maps each bot display name to estimates of all ten settings in
`sparring/param.py`, observed poker statistics, model diagnostics and statistically
supported collection-time segments. It is separate from `bot/`; no profiles, dependencies or private
replay cards are added to the tournament submission.

## Run with the RTX 5070 Ti

Use an isolated Python environment with NumPy and a CUDA-enabled PyTorch build.
The 5070 Ti needs a Blackwell-capable build. The tested environment used Python
3.12.13, NumPy 2.5.2 and PyTorch 2.14.1+cu130; its bundled CUDA runtime is 13.0.
No driver or system CUDA toolkit was installed or changed.

```powershell
uv venv .venv-estimators --python 3.12
uv pip install --python .venv-estimators/Scripts/python.exe torch numpy --index-url https://download.pytorch.org/whl/cu130

.venv-estimators/Scripts/python.exe -B -m opponent_model `
  --data-dir 'Y:/home/omid/work/poker-data' `
  --save-cache analysis/results/opponent-features.npz `
  --output analysis/results/opponent-estimates.json `
  --bootstrap 2000 --permutations 9999
```

`--device cuda` is the default and **fails if CUDA is unavailable**. It executes
a real GPU probe. Likelihood grids, fits, whole-match bootstrap, covariance,
segment-cost tensors and held-out permutations run on CUDA in float64. JSON
parsing, replay reconstruction, SDK hand-strength features, grouping, the small
dynamic-programming control loop and JSON serialization run on the CPU.
The report records the device, GPU name, runtime versions and peak allocation.
Each run writes JSON plus a readable `<output-stem>-summary.md` companion.
`--device cpu` exists for explicit correctness/parity tests, not as a fallback.

Freeze a validated input snapshot once; reuse it for repeatable runs while the
collector continues writing:

```powershell
.venv-estimators/Scripts/python.exe -B -m opponent_model `
  --cache analysis/results/opponent-features.npz `
  --output analysis/results/opponent-estimates.json `
  --bootstrap 2000 --permutations 9999

.venv-estimators/Scripts/python.exe -B -m unittest discover -s tests -v
```

The cache uses NumPy without pickle, includes a schema and `param.py` fingerprint,
and is invalidated when that surrogate changes. Input SHA-256 hashes identify
the frozen dataset. `analysis/results/` and the analysis environment are ignored
by Git. Large raw logs and full analysis reports are not committed. The latest
segment profiles exported to `sparring/competitors/from_data/` are versioned
for reproducible offline simulations; see [the competitor documentation](../sparring/competitors/README.md).

## Reusable API

```python
from opponent_model.compute import Compute
from opponent_model.data import load_dataset
from opponent_model.pipeline import analyze, lookup

data = load_dataset("actions.jsonl", "matches.json", "state.json")
report = analyze(data, Compute("cuda", seed=42), seed=42,
                 bootstrap=2000, permutations=9999)

segments = report["bots"]["example-bot"]["segments"]
first_estimator = segments[0]["parameters"]["vpip"]
segment = lookup(report, "example-bot", segments[0]["observed_from"])
surrogate_style = segment["surrogate_style"]  # pass explicitly to ParamBot(style=...)
```

Every segment contains the ten parameter estimators, full bootstrap covariance,
observed rates, between-match parameter variance, fit residuals, match IDs and
UTC timestamps. `lookup` uses the inferred boundaries but refuses extrapolation
beyond the bot's observed timeline. `surrogate_style` is always a usable best-fit
configuration; **check parameter statuses before treating it as reliable**.
Unidentified values can be arbitrary equivalent fits. Ties prefer the TAG
reference, and an absent estimate is `null`, not a known zero.

The API also exposes `BotModel`, `reconstruct_hand`, `optimal_partition` and
`propose_changes` for other datasets or offline experiments. `--bot NAME` may
be repeated to restrict a run; the report's multiple-test family then covers
only that invocation's proposed boundaries.

## Estimators and opportunity definitions

The input action log stores pot **after** each action. The loader reconstructs
pot before action, to-call, street bets, stacks, legal raise bounds, reopening,
folds, current board and aggressor. It checks every recorded pot and action.
The known tournament defaults are button at physical seat 0, stacks reset to
200 and blinds 1/2; API callers can override stack/blinds. Seat identities are
inferred from actual action rows and match names, never dict ordering.
Missing hole cards exclude only the affected latent-parameter observations;
observed action/hand rates remain available. Duplicates, incomplete/out-of-order
hands, missing joins and files changing during ingestion are errors, not silently
counted evidence. Load from a stable copy or retry ingestion if the collector
updates one of the joined files mid-read.

| Setting | Estimation opportunity and model |
|---|---|
| `vpip` | No previous preflop raise, known starting cards, positive price to continue. Fit the Chen-percentile participation threshold. |
| `pfr`, `limp` | Joint threshold/probability fit on unraised preflop decisions where raising is legal. Raise probability is `1-limp` below `pfr`; `pfr <= vpip`. |
| `threebet` | Known cards, exactly one earlier preflop raise and raising is legal. Fit the reraising percentile threshold, constrained to `<= pfr`. |
| `aggression`, `cbet`, `bluff` | Joint probability model on postflop decisions checked to the bot where betting is legal. Marginalizes the surrogate's value, continuation, draw and bluff branches in their actual order. |
| `stickiness` | Postflop call/fold decisions facing a price, with raising legal. Invert the surrogate's strength/draw/pot-odds calling rule. Excludes raises and coerced calls when raising is closed. |
| `size` | Opening postflop raises outside cbet-eligible spots. Uniform 0.85–1.15 jitter, integer truncation and min/max censoring are included in the likelihood. Reraises and latent 0.8-cbet sizes are excluded. |
| `adaptive` | Compare the surrogate's two modes, rebuilding its public opponent counters within each match. Fit separate postflop/calling parameters per mode; the adaptive mode must overcome a `0.5 log(n)` negative-log-likelihood complexity penalty. |

The strength heuristic and hand percentiles come from the actual `param.py`.
These are opportunity-specific component estimators, not one full-game generative
model. In particular, empirical VPIP/PFR, cbet and bluff frequencies are **not**
the latent inputs of that file. The output reports empirical rates separately.

Fine thresholds use 0.01 grids, pot sizing uses 0.005, and the joint probability
grid defaults to 0.05 (`--grid-step`). A fixed 5% contamination component allows
actions which this simple surrogate cannot explain (`--contamination`). This is
a robustness convention, not proof that only 5% of actions are unexplained.

## Uncertainty and significance

- Parameter `variance`, `standard_error` and percentile `confidence_interval`
  resample **whole matches**, preserving within-match dependence. The same
  resampled match weights feed all estimators and their covariance. Sparse
  opportunities are labelled `insufficient_data`.
- Flat likelihood ranges and diagnostic profile support (`delta NLL <= 1.920729`)
  expose non-identifiability. The latter is an approximate likelihood-support
  region, **not** a guaranteed-coverage confidence interval for these step rules.
  `weakly_identified`, `not_identified` and `grid_limited` distinguish problems a
  small bootstrap variance alone would hide.
- Each parameter includes a TAG reference and whether it is outside both the
  bootstrap interval and likelihood support. This is descriptive evidence, not
  a causal test of the opponent's internal setting. Parameter `p_value` is
  deliberately `null`: no regular Wald test is justified for discontinuous,
  partially identified surrogate settings. Actual change tests have explicit
  null hypotheses and corrected p-values below.
- Empirical rates report Bernoulli observation variance separately from the
  variance of the match-cluster estimate. A degenerate bootstrap is flagged;
  all-zero/all-one samples do not establish certainty about rare events.
- Residual RMS, log loss, Brier scores, incompatible actions/amounts, censoring
  fractions and between-match variance expose strategy behaviour the model
  misses. They cannot account for every unknown variable. A narrow interval
  around a misspecified model can still be misleading.
- `adaptive_selection_frequency` is a bootstrap model-selection frequency,
  **not** the probability that the opponent adapts or a recovered source flag.

## Timestamp segmentation without chasing tiny variances

1. Join `actions.match` to `matches.id` and `state.collected[id]`, using
   **`state.collected[id].collected_at`**. Report disagreements; state wins.
2. Fit a parameter vector per match; insufficiently observed coordinates become
   missing for segmentation. The discrete adaptive flag is excluded.
3. Hash match IDs/timestamp groups into discovery and held-out sets without
   looking at actions. Equal collection timestamps stay together.
4. On discovery matches, use dynamic programming to globally minimize
   standardized within-segment squared error plus a BIC-style cut penalty
   `(usable_dimensions + 1) log(discovery_matches)`. Minimum lengths and a cap
   on segments prevent the zero-variance-one-match-per-segment solution.
5. Keep the proposed boundaries fixed. Test each on held-out adjacent ranges
   by permuting whole match vectors. By default each side needs at least six
   discovery and six held-out matches. There is no held-out search for a better
   cut. Apply Holm adjustment across **all candidate boundaries/all bots** in
   the report; remove unsupported cuts. Adjacent rejected ranges are pooled.
6. Estimate each retained range using all its matches and cluster-bootstrap
   uncertainty. Intervals are **conditional on those selected boundaries**;
   they do not include change-location/selection uncertainty. The discovery
   gap around each cut is reported, not an invented exact update time.

This optimizes a penalized variance criterion on discovery data and confirms
changes independently. It does not promise an absolute minimum variance for
every parameter, or tune boundaries to maximize significance. More data can
move or remove a proposed cut. Permutation inference assumes exchangeable
independent match units under no change; correlated duplicate games or changing
opponent mixes can violate this. More generally a detected behavioural change
can arise from opponents, hand contexts, failures or adaptation, not a code update.

`collected_at` is collection chronology. Backfills and delayed collection can
scramble play chronology. The report identifies seed-from-raw matches; it never
silently substitutes `at` or presents collection boundaries as deployment times.
Likewise names are the identities available here: renames/same-name replacements
cannot be resolved from these files.

Method references: [penalized multiple changepoint costs](https://arxiv.org/abs/1101.1438),
[percentile resampling intervals](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html),
[permutation-test conventions](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html),
and [PyTorch CUDA installation](https://pytorch.org/get-started/locally/).
The implementation uses PyTorch/NumPy, not SciPy or the PELT algorithm.
