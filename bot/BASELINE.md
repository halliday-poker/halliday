# Non-adaptive baseline

> The field exploits change the c-bet, c-bet defence, turn, river and
> all-in rules below and add per-game opponent counters; see
> [FIELD_EXPLOITS.md](FIELD_EXPLOITS.md). This file still describes the base.

This branch starts from `feat/odds-calc` at `d8c1a2c`, including the merged
evaluation harness. The equity engine and its public API are unchanged.
The scaffold's pot-odds-only action rule is replaced with a fixed strategy.

## Policy

- **Preflop:** fixed hand-class tables by position; open to 2.5 big blinds
  plus one big blind per limper. Value three-bets use 3x in position and 4x
  out of position, with extra sizing for callers. Four-bets use about 2.3x.
  Separate ranges cover calls, big-blind defence and reraises. The heads-up
  button is correctly treated as the small blind and has a wider opening range.
- **Large preflop bets:** AA continues; QQ/KK/AK require estimated equity
  above pot odds plus a fixed margin. Other hands fold. This conservative
  rule deliberately does not learn which players shove too wide.
- **Postflop:** bet strong equity, raise very strong equity, and otherwise
  compare equity to pot odds plus fixed street, multiway and pressure margins.
  Value thresholds tighten with more live opponents. Bet sizes are 40% on
  dry boards and 67% on boards with suit or straight connectivity. Strong
  hands can shove at low stack-to-pot ratios.
- **Continuation bets:** a modest heads-up flop bet needs preflop initiative,
  at least 50% equity, and a pair involving our cards or a meaningful draw.
  There are no unconditional continuation bets or pure bluffs.
- **Legality:** every raise uses street-total semantics and the SDK's
  `can_raise`, minimum and maximum limits. A closed raise option becomes a
  call/check. Short all-in call prices exclude current-street chips the bot
  cannot win. A royal-flush board is always checked/called.

The bot targets chips in the documented 200-chip-reset, 1/2-blind game.
It does not use tournament survival/ICM calculations or cumulative scores.
Charts and thresholds are heuristics, not an equilibrium solution.

## What non-adaptive means here

The same current observation and available compute budget use the same fixed
policy. No player profiles, identity recognition, learning across hands,
persisted statistics, or online parameter changes exist. Public actions in
the **current hand** identify opens, reraises and the preflop aggressor.
`decide(state, equity, opp_profiles=None, params=DEFAULT_PARAMS)` keeps the
planned strategy interface; `opp_profiles` is intentionally ignored.

All live opponents, including all-ins, get uniform unknown-card ranges
(`None` in the engine API). Folded players are excluded. This is a transparent
reference model: it does **not** infer an opponent's hand range from their
betting. The fixed margins cannot fully compensate for that simplification.
Equity is showdown share, not future betting EV, implied odds, fold equity,
or exact side-pot chip EV. Counting a short all-in player against every pot
can make the policy too conservative in pots that player cannot contest.

`DEFAULT_PARAMS` is read-only. Alternate fixed configurations can be passed
to `decide` in offline experiments. Preflop charts are in `preflop.py`.

## Compute and diagnostics

Ordinary preflop decisions skip simulation. Postflop and large preflop bets
request 768 samples within 35 ms. Below 5 seconds remaining this becomes
192 samples / 10 ms; below 250 ms the bot skips simulation. Fewer than 128
completed Monte Carlo samples are treated as unavailable. These are cooperative
deadlines; a deal already being evaluated may finish after the deadline.

Unavailable equity means check/fold, except preflop table decisions and a
guaranteed royal-board split. `last_equity` and `last_estimate` are diagnostics,
cleared on every action and hand; they are never used as stored strategy state.
The latter still provides per-player category probabilities and win/tie/loss.

Sampling has a private seed derived only from visible cards and current-hand
state, independent of game/deck seeds and the global random generator. Repeated
states reproduce samples when they complete the same iteration count. Clock
cutoffs or machine load can change that count and therefore close decisions.

## Reproduce validation

From the repository root, using Python 3.12 and the vendored SDK:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'vendor/macpoker-src')
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m unittest discover -s tests -v
python -B harness/eval.py smoke bot --deals 100 --seed baseline-v1-smoke
python -B harness/eval.py run bot --tables 40 --no-extend --workers 2 --seed baseline-v1-a
python -B harness/eval.py run bot --tables 40 --no-extend --workers 2 --seed baseline-v1-b
```

See [the validation report](../docs/baseline-strategy-validation.md) for results.
The reduced 40-table runs are implementation validation; the harness defaults
to 400 tables for a broader gate. They do not establish strength against
unseen tournament entrants. Before tuning thresholds, reserve new seeds and
opponent configurations and compare paired table-level intervals. Range-aware
bet responses and proper side-pot EV are useful future comparisons to this baseline.
