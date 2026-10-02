# MAC poker bot scaffold

Everything you need to start building.

## Setup

```
pip install https://poker.monashcoding.com/dl/macpoker-0.1.0-py3-none-any.whl
```

Python 3.10 or newer. The tournament sandbox runs Python 3.12 with the SDK
and numpy preinstalled. Nothing else is available at runtime.

## Develop

Edit `main.py`. Split logic into extra modules in this folder if you like;
`main.py` can import them.

Test against the house bots (`house:call`, `house:checkfold`, `house:allin`, `house:random`). Every argument after `play` is one seat at the table, so you can mix several of your own files and house bots:

```
macpoker play main.py house:call house:random --deals 50
macpoker play main.py house:call --deals 100 --subprocess --history out.json
```

## Odds calculator

`MyBot.calculate_odds(state, *, samples=1000, seed=None,
starting_stacks=None, time_budget_ms=None)` returns a dictionary. All
probabilities are **fractions from 0 to 1**, from our bot's information.
Multiply by 100 for percentages. The ten final best-five categories are
exclusive: `Straight Flush` excludes `Royal Flush`, and a full house does
not also count as a pair or three of a kind.

Use it inside `act()` or an observer hook with an available `GameState`:

```python
odds = self.calculate_odds(state, samples=1000, seed=42)
hero = odds["players"][state.player]
flush_probability = hero["hand_probabilities"]["Flush"]
equity = hero["equity"]
for player_id, player in odds["players"].items():
    final_hands = player["hand_probabilities"]
    win_probability = player["win"]
```

The scaffold's `act()` already calculates and caches a report in
`self.last_odds`. Its existing check/call/fold policy remains unchanged;
the calculator supplies inputs for a later strategy. Direct calls return
a report without changing this cache.

### Report fields

| Field | Meaning |
|---|---|
| `hero` | Our stable player id; `players` is keyed by ids, not rotating seats |
| `cards_to_come` | Number of community cards still to be dealt |
| `players[id].hand_probabilities` | Probability of each final best-five category |
| `players[id].hand_method` | `exact` or `monte_carlo` for that distribution |
| `players[id].hand_evaluations` | Number of hands counted for that distribution |
| `players[id].win` | Probability of being the **sole** strongest live player |
| `players[id].tie` | Probability of sharing the strongest hand; ties below a winner do not count |
| `players[id].loss` | `1 - win - tie`; folded seats always have loss 1 |
| `players[id].equity` | Expected fractional share of one common pot; a three-way tie contributes 1/3 |
| `players[id].equity_standard_error` | Estimated Monte Carlo standard error of equity; 0 for exact results, `None` for one sampled deal |
| `showdown_method`, `showdown_trials` | Method and deal count for full-table win/tie/equity and call-value estimates |
| `sampled_deals` | Actual jointly sampled deals, which may be fewer than `samples` with a time budget |
| `hero_heads_up[id]` | Our win/tie/loss/equity against that one live opponent, with `method` and `trials` |
| `hero_draws.current_hand` | Current best-five category, or `None` preflop |
| `hero_draws.category_improvement_by_river` | Probability of reaching a higher category; `None` preflop |
| `hero_draws.at_least_by_river` | Cumulative categories, e.g. Flush includes full houses, quads and straight flushes |
| `hero_draws.next_card` | Exact next-card distribution, category-improvement probability and list of improving cards on flop/turn; otherwise `None` |

Every player also has `seat` and `folded`. Folded players have zero win,
tie and equity, but their hand distributions are hypothetical hands if
the board were completed. Players with zero chips are still live unless
folded. Pairwise odds omit folded seats; other seats' unknown cards remain
blockers in the joint model and are integrated out in exact marginals.
Do not multiply pairwise win rates to obtain multiway win rates: hands
share a board and cards cannot appear in two players' holdings.

### Strategy inputs and chip value

`strategy` provides:

- `call_cost`: our actual additional chips, capped at our remaining stack.
- `pot_odds`: `call_cost / (state.pot + call_cost)`, or zero for a free check.
  This is the familiar single-pot break-even equity. It is **not** an
  eligibility-adjusted threshold when side pots exist.
- `checkdown_expected_payout`: expected gross chips returned after our
  call if the board runs out and everyone still live checks to showdown.
- `checkdown_call_ev`: that payout minus the new call cost. Previous
  contributions are sunk costs. This is a conditional chip-value estimate,
  not a prediction of future betting or tournament placement points.
- `uncalled_refund`: any unmatched part of our contribution returned before
  settlement.
- `pots_after_call`: each pot's `amount`, `eligible_players` and
  `hero_equity`. Folded money stays in the pots, short stacks can only win
  eligible layers, and chip payouts include the SDK's odd-chip ordering
  starting left of the button.

Contributions are reconstructed from starting stacks and current stacks.
Observer hooks capture the public per-hand starting stacks; the match
configuration sets the fallback (200 by tournament default). For a manually
built state with different starting stacks, pass `starting_stacks=[...]`.
Inconsistent stacks/pot values raise `ValueError` instead of returning a
misleading EV.

The checkdown model freezes **everyone else's contributions now**. Players
who still owe a call are not assumed to contribute it later. This is most
useful when our call closes the betting, especially on the river or when
opponents are all in. Earlier decisions need a model for future bets,
calls, folds and equity realization. Full-table equity and pot equity may
differ because side pots have different eligible players.

### Exact counts, sampling and assumptions

| Stage | Our final hand distribution | Each opponent's distribution | Full-table showdown |
|---|---|---|---|
| Preflop | Sampled | Sampled | Sampled |
| Flop | Exact: 1,081 board completions | Sampled | Sampled |
| Turn | Exact: 46 river cards | Sampled | Sampled |
| River | Exact: current hand | Exact: 990 hole-card pairs | Exact heads-up involving us; sampled multiway |

One remaining live player wins with certainty at any stage. Heads-up
comparisons on the river are exact even at a multiway table.

- Unknown holes and future boards are uniform over unseen cards. No
  information about hidden cards or the engine deck is accessed. Betting
  actions do **not** yet reweight opponent ranges, so all unknown opponents
  have the same marginal hand distribution. Sampled opponent marginals
  pool all opponents' hands to reduce noise; those hands within one deal
  are correlated, so `hand_evaluations` is not an independent trial count.
- Each simulated deal uses one shared board and disjoint hole cards for
  all seats. Only nonfolded seats compete. Exact methods integrate unknown
  folded cards out; removing arbitrary folded cards would bias the odds.
- A sampled zero is not proof of impossibility. Rare hands need many more
  offline samples. Standard errors describe observed sampling variability,
  do not include model error, and can be zero when a rare event was missed.
- Improvement means a **higher category**, not a better kicker or a
  guaranteed winning out. A card can improve our category and help an
  opponent more. The final category may be made entirely by the board.
- `seed` controls a private simulation RNG, never the engine's RNG. With
  no time budget, the same inputs and seed reproduce the report. There is
  no disk persistence and no card knowledge carried between fresh decks.

### Time bank and validation

`act()` requests at most 256 deals with a soft 25 ms budget; below 5 seconds
remaining it uses 64 deals and 10 ms. Below 250 ms it skips new calculations
and leaves `last_odds` as `None` unless the identical decision is cached.
The cache includes hand, cards, seats, folds, stacks, pot, call cost and
button, and clears at hand/match start, so betting cannot leave stale EV.

The deadline is checked every 16 simulated deals. Small exact passes and
report construction finish regardless of the budget; it is **not a hard
real-time guarantee**. Direct calls without `time_budget_ms` use the
requested samples regardless of `state.clock_ms`. All work is synchronous
inside the SDK callbacks, using only the standard library and SDK.

From the project root, tests use the checked-in SDK automatically:

```powershell
python -B -m unittest discover -s tests -v
```

To run production-protocol validation without installing the SDK locally:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'vendor\macpoker-src')
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m macpoker play bot/main.py house:call house:random --deals 100 --subprocess
```

Local verification passed 16 tests and 800 subprocess hands across
heads-up, five-player and nine-player games, all with `OK` verdicts.
The available local interpreter was Python 3.13.3; execution under the
tournament's Python 3.12 remains unverified. At 256 requested samples,
median runtimes across tested streets/table sizes were about 3-16 ms on
this machine; runtime and sampling counts depend on the host.

## Submit

Zip this folder with `main.py` at the root and upload it at
https://poker.monashcoding.com/app. Every upload plays a validation game
against the house; pick a passing upload as your **main** before the
deadline. That is your tournament entry.

## Rules that matter here

No network calls, no AI/LLM calls at runtime, standard library plus numpy
only. The sandbox has no internet and submissions are audited.

Questions: https://discord.gg/kkv2hJyzGp
Docs: https://docs.poker.monashcoding.com
