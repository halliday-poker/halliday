# Person A handoff: equity engine

Person A owns card evaluation and probability calculation. Person B owns
preflop ranges, decisions, sizing and strategy parameters. Person C owns
opponent profiles and parameter adjustments. The engine has no SDK,
GameState, pot, stack, history or profile dependency.

## Agreed integration API

```python
from engine import equity

eq = equity(hole, board, opp_ranges, n_iters, time_budget_ms)
```

The result is a **float in [0, 1]**: expected share of one common pot at
showdown, assuming every supplied opponent stays in. A sole win contributes
1, a two-way tie 1/2, a three-way tie 1/3, and a loss 0. It is not the
probability of a particular hand category, outright-win probability, chip
EV, fold equity or equity realization. It does not price side pots, future
betting, implied odds or tournament placement. Those are strategy concerns.

All five arguments may be positional or keyword arguments. Defaults are
`n_iters=1000` and `time_budget_ms=25.0`. The function does no file/network
I/O, uses no background work and does not modify inputs or global RNG state.
Call it from SDK callbacks. The code uses only the Python standard library.

## Range contract for B and C

- `hole`: two card strings, e.g. `["As", "Kd"]`.
- `board`: 0, 3, 4 or 5 community-card strings. Known cards must be distinct.
- `opp_ranges`: a list/tuple with **one entry per live opponent**, in an
  order chosen by the caller. Include all-in opponents; omit folded seats.
  Zero opponents returns equity 1. Up to eight opponents are supported.
- Each entry is either `None` for uniformly random unseen cards, or a
  mapping `{("card1", "card2"): weight, ...}`. Missing combinations have
  zero weight. Weights must be finite and nonnegative; they need not sum to
  one. Zero-weight and known-card-blocked combinations are excluded.
- Combo order is irrelevant: `("As", "Kd")` and `("Kd", "As")` are the same
  holding. Including both is an input error, as is repeating a card inside
  one combo. Use two-character SDK cards (`T`, not `10`).
- Weights apply **per concrete combination**, not per 169-hand class. B's
  range parser must expand class selections into combos: a pair has six,
  a suited unpaired class four, and an offsuit class twelve before blockers.
  The engine does not choose range widths or parse strategy strings such
  as `"22+,A2s+"`.

For example, two opponents, one weighted and one unknown:

```python
opp_ranges = [
    {("Qh", "Jh"): 3.0, ("9c", "9d"): 1.0},
    None,
]
eq = equity(["As", "Ks"], ["Qs", "7s", "2d"], opp_ranges, 1000, 25)
```

The weighting model is the product of each opponent's supplied combo
weight, **conditioned on all hands being disjoint**. Incompatible draws are
rejected as a whole. Renormalizing the next opponent's range separately
after each draw would bias the joint distribution. Uniform opponents and
the future board are drawn without replacement after restricted hands.

Consequently a range can change both our equity and our final-hand
distribution by blocking future board cards. These are exact calculations
or Monte Carlo estimates **under the supplied range model**, not a claim
that the model knows what an opponent actually holds. The caller must
update ranges when public actions or C's profiles change; the engine has
no stateful cache or knowledge carried across fresh decks.

## Minimal B/C integration

The caller joins seats to C's stable player ids. `ranges_by_player` below
is prepared by B/C from their chosen range model, not inferred by A:

```python
from engine import equity, EquityTimeout, EquitySamplingError

live_ids = [state.players[s] for s, folded in enumerate(state.folded)
            if s != state.seat and not folded]
opp_ranges = [ranges_by_player.get(player_id) for player_id in live_ids]

try:
    eq = equity(state.hole, state.board, opp_ranges,
                n_iters=256, time_budget_ms=min(25, max(0, state.clock_ms - 100)))
except (ValueError, EquityTimeout, EquitySamplingError):
    # Invalid/missing estimates must not be treated as measured equity 0 or 0.5.
    return state.check() if state.to_call == 0 else state.fold()

return decide(state, eq, opp_profiles, params)
```

B can replace that fallback with its documented stub estimate. C's
`adjust_params` remains independent of this engine. No versions of B's
`strategy.py`, `preflop.py`, `params.py` or C's `opponents.py` are supplied
by this change.

## Budget and failure contract

`n_iters` is a positive integer limiting completed Monte Carlo deals.
`time_budget_ms` includes range validation/compilation and feasibility
checking. Preparation checks the deadline in batches of at most 32 range
entries/search steps; the sampler checks before **every** attempt,
including rejected attempts. A started deal and the small output report
finish before returning, so this is a cooperative deadline, not a hard
real-time scheduling guarantee. Keep a reserve on the game clock.

When the deadline expires after one or more deals, their estimate is
returned. A small sample can be noisy; use diagnostics if the distinction
matters. Range preparation can consume the entire budget on large inputs.
Use `None` for an any-two range instead of constructing 1,326 equal weights.

| Condition | Behavior |
|---|---|
| Budget is zero, or expires before any sample | Raises `EquityTimeout` (a `TimeoutError`) |
| Malformed cards, weights, range format or iteration limits | Raises `ValueError` |
| All positive combos are blocked, or ranges provably cannot coexist | Raises `ImpossibleRangeError` (a `ValueError`) |
| Valid but extremely conflicting ranges exhaust the attempt cap with no sample | Raises `EquitySamplingError` (a `RuntimeError`) |
| Attempt cap reached after some samples | Returns those samples; diagnostics mark `attempt_limit` |

Feasibility search is bounded at 10,000 nodes. Reaching that cap is
inconclusive; it does not label a valid range impossible. Rejection sampling
is bounded at `max(1000, 100 * n_iters)` attempts even with no deadline.
Extremely disparate weights that lose positive CDF mass in floating-point
arithmetic raise `ValueError`. No failure silently substitutes uniform
opponents or fabricated equity.

## Diagnostics and optional hand probabilities

```python
from engine import estimate_equity, evaluate_hand

report = estimate_equity(hole, board, opp_ranges, 10000, None, seed=42)
eq = report.equity
hero = report.players[0]
flush_probability = hero.hand_probabilities["Flush"]
current_value = evaluate_hand(hole + board)  # Only when 5-7 cards are available.
```

`estimate_equity` has the same arguments plus a keyword-only `seed`. Its
`EquityEstimate` includes:

- `equity`: hero's expected pot share.
- `players`: hero first, followed by opponents in **input order**. Each
  `PlayerOdds` has `win`, `tie`, `loss`, `equity`, and `hand_probabilities`.
  Win means sole strongest hand; tie means sharing the strongest hand.
  The ten final best-five categories are exclusive; Straight Flush excludes
  Royal Flush. Different supplied ranges can yield different distributions.
- `samples`, `attempts`: completed deals/outcomes and attempted assignments.
- `method`: `monte_carlo` or `exact`.
- `stop_reason`: `iteration_limit`, `time_budget`, `attempt_limit`,
  `enumerated` or `no_opponents`.
- `standard_error`: estimated Monte Carlo error in hero equity; `None` for
  one sample and 0 for an exact result. It excludes errors in the range
  model. An observed zero or zero error does not prove a rare event impossible.

No-opponent calls skip simulations: equity/win are 1, samples are 0, and
hand probabilities are `None`. `evaluate_hand` returns a comparison tuple
with category 0..8 and all tiebreaker ranks 2..14; higher wins. Royal flush
is `(8, 14)`. It includes wheel straights and never uses suits to break ties.

Timed calls use Monte Carlo, except a completely specified river showdown
or no opponents. With `time_budget_ms=None`, small outcome spaces with an
upper bound no larger than `min(n_iters, 2000)` are enumerated exactly with
product weights. Larger cases use sampling. An unfinished enumeration is
never returned as an estimate. With no deadline, the same inputs and seed
give the same result and sample count. `seed` has no connection to game decks.

### Offline batch hook

The evaluation harness may provide private keyword arguments `_evaluate_batch`
and `_batch_size` to `estimate_equity`. The callback receives complete seven-card
hands encoded as integers 0–51 and returns comparison tuples in the same order.
Sampling, rejection, weights and aggregation remain in this engine, preserving
fixed-sample seeded results. The default evaluator and public five-argument
`equity` API remain standard-library-only.

With this hook, the deadline is still checked before every sampling attempt.
A pending batch is evaluated and aggregated before returning, including when
the deadline or attempt limit is reached. Thus a timed call may overrun by one
batch rather than one deal. The harness defaults to 128 deals per batch and uses
CPU execution for tournament promotion gates. See [GPU workers](../harness/README.md#gpu-workers).

## Changes from the first odds-calc implementation

The large `MyBot.calculate_odds`, `last_odds` cache, contribution tracking,
pot-odds/checkdown-EV/side-pot calculations and forced exact passes were
removed from `main.py`. The reusable evaluator and hand distributions now
live in `engine.py` and support opponent ranges.

`main.py` now calls the fixed baseline's `decide` with equity from
`estimate_equity`. The engine and agreed five-argument `equity` API are
unchanged. Caller-specific budgets, minimum samples, diagnostic clearing
and fallback rules are documented in [BASELINE.md](BASELINE.md).

## Verification

From the repository root:

```powershell
python -B -m unittest discover -s tests -v
python -B tests/benchmark_engine.py
$env:PYTHONPATH = (Join-Path (Get-Location) 'vendor\macpoker-src')
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m macpoker play bot/main.py house:call house:random --deals 100 --subprocess
```

Tests use the checked-in SDK as an independent evaluator/enumeration oracle.
They cover weighted products, blockers, shared boards, collision rejection,
ties, range-dependent runouts, impossible inputs, seeded repeatability,
deadline/attempt exhaustion and SDK loading. The merged harness and the
fixed baseline also have strategy, real-game legality and subprocess tests.
See [the baseline validation report](../docs/baseline-strategy-validation.md).

Verified locally on Python 3.12.13 (the tournament's minor version) and
3.13.3: all 24 tests passed. Subprocess validation completed 1,100 hands
with `OK` verdicts: two five-player duplicate sets of 500 hands and one
nine-player game of 100 hands. The Python 3.12 run covered a complete
five-player set. The isolated test runtime did not change PATH or the
Windows registry and is not part of the submission.

On Python 3.12, median times for 256 samples were about 3-11 ms for the
tested uniform/mixed cases. Nine-player tables with eight full 1,326-combo
mappings consumed roughly 25 ms and returned fewer samples. These are local observations, not timing
guarantees on the tournament host.
