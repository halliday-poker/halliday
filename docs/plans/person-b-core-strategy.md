# Person B: core strategy, getting started

Person B owns **what the right play is against an average opponent**: preflop ranges, postflop
decisions and bet sizing. Person A supplies equity numbers; Person C supplies opponent
profiles and adjusts B's parameters. B's code must play sensibly with A's and C's parts stubbed,
so B never waits on them.

## Files B owns

| File | Contents |
|---|---|
| `bot/strategy.py` | `decide(state, equity, opp_profiles, params) -> Action`, plus the helpers below |
| `bot/preflop.py` | Range tables (169-hand strings per position and spot) and the preflop decision |
| `bot/params.py` | `DEFAULT_PARAMS`: every number C is allowed to adjust, in one dict |
| `bot/main.py` | Thin glue only (shared file: keep edits small, coordinate at merges) |

Agreed interfaces from hour 1. Stub the other two until they land:

```python
equity(hole, board, opp_ranges, n_iters, time_budget_ms) -> float   # A: engine.py
profile(player_id) -> dict ; adjust_params(params, profiles) -> dict  # C: opponents.py
decide(state, equity, opp_profiles, params) -> Action               # B: strategy.py
```

Until A's engine exists, use a preflop lookup (Chen score as in `sparring/tag.py`) and a
postflop made-hand estimate (category from `macpoker.evaluator`, which is fine locally but too
slow for the real bot) mapped to a rough equity. Until C's model exists, `adjust_params`
returns the defaults unchanged.

## Engine facts to build on (checked in `vendor/macpoker-src/macpoker/hand.py`)

- **Position:** `pos = (state.seat - state.button) % state.num_players`. 0 = button,
  1 = small blind, 2 = big blind, 3 = UTG (first to act preflop), and so on round to the
  cutoff (`n - 1`). Postflop, the small blind acts first and the button acts last.
- **`state.pot`** includes every chip committed so far, including the current street's bets.
  Pot odds = `to_call / (pot + to_call)`.
- **`raise_to(n)`** is the street total, not the increment. Always clamp to
  `[min_raise_to, max_raise_to]` and check `can_raise` first, or the engine silently turns the
  raise into a call.
- **`state.history`** rows are `[street, seat, kind, amount]`. For `raise`, the amount is the
  raise-to total; for `call`, it is the chips added. Blinds are not in history.
- Stacks reset to 200 (100 bb) every hand, so this is deep-stacked cash-game strategy. There
  are no tournament survival considerations inside a hand.

## Step 1 (first ~2 hours): skeleton that never breaks

1. `bot/params.py` with `DEFAULT_PARAMS` (open sizes, range widths, value and bluff
   thresholds, sizing fractions). Every magic number goes here from day one.
2. `bot/strategy.py`:
   - `spot(state)`: classifies the situation from `history`: unopened, limped, facing an open,
     facing a 3-bet or 4-bet, facing an all-in. Also counts players in the pot and who the
     preflop aggressor was.
   - `bet(state, fraction_of_pot)`: computes a legal `raise_to`, clamped, or falls back to
     check or call.
   - `decide(...)`: dispatches to preflop or postflop. The whole thing sits in try/except, with
     check-if-free-else-fold as the fallback.
3. Wire it into `bot/main.py`, run `python harness/eval.py smoke bot`, and commit. From here on
   the bot is always submittable.

## Step 2 (hours 2-10): preflop

- **Ranges as data:** a 13x13 grid or strings like `"22+,A2s+,KTs+,QTs+,JTs,ATo+,KJo+"`, plus a
  parser that expands them to the 169 hand classes. Separate ranges for: open by position
  (scaled tighter for more players behind), 3-bet, call vs open, 4-bet and call vs 3-bet.
- **Starting widths for 4-6 handed:** UTG ~15-18%, CO ~25%, BTN ~40-45%, SB ~35% open or
  complete. Defend the BB wide against small opens (pot odds).
- **Sizing:** open to 2.5 bb (5 chips) plus 1 bb per limper. 3-bet to 3x in position, 4x out of
  position. 4-bet to about 2.3x. Shove when the raise would commit more than about a third of
  the stack.
- **Calling an all-in:** call when equity vs the shover's range beats pot odds. Against
  `house:allin`-style bots (any two cards), that is roughly the top 20-25% of hands heads up,
  tighter with more players still to act. Make the shover's range a parameter so C can set it
  per opponent.

## Step 3 (hours 10-24): postflop v1, decisions from expected value

For each decision: `eq = equity(...)` against the likely ranges, `n` opponents still in.

| Situation | Rule (thresholds live in params) |
|---|---|
| Checked to us | Bet for value if `eq > value_threshold(n)` (about 0.60 heads up, higher multiway). Bluff or semi-bluff with frequency `bluff_freq` only heads up and with some equity (draws). Otherwise check. |
| Facing a bet | Raise if `eq > raise_threshold`. Call if `eq > pot_odds + call_margin`, with implied odds for draws on the flop and turn. Otherwise fold. |
| Sizing | Default to 1/3 pot on dry boards and 2/3 on wet boards, pot or overbet for value against stations. Go all in when the stack-to-pot ratio is under ~1. |
| C-bet | As preflop aggressor heads up, c-bet the flop at `cbet_freq` and rely on equity checks after that. |

Board texture helpers (flush or straight possible, paired board) feed both sizing and the
semi-bluff choice.

## Parameters to expose for Person C

`open_width[pos]`, `threebet_width`, `call_vs_open_width`, `shove_call_range`,
`value_threshold`, `raise_threshold`, `call_margin`, `bluff_freq`, `cbet_freq`,
`size_dry`, `size_wet`, `size_value_vs_station`. C changes these per opponent; B never reads
opponent stats directly.

## Testing

- **Unit tests for spots:** build states by hand with `GameState(msg)` from `macpoker.sdk`. A
  dict with the `act` fields (`hole`, `board`, `street`, `pot`, `to_call`, `min_raise_to`,
  `max_raise_to`, `can_raise`, `stacks`, `street_bets`, `folded`, `button`, `seat`, `players`,
  `history`, `hand`) is enough. Assert that AA raises, that 72o folds to a 3-bet, and that a
  raise is never below `min_raise_to`.
- **A/B every change** with the harness:
  `python harness/eval.py snapshot b1` and then `python harness/eval.py run snapshots/b1 bot`.
  Only merge changes marked `BETTER` on two seeds.
- Watch the opponent-present breakdown. The first targets are big positive numbers against
  `station` and `allin`, and not losing to `tag`.

## Milestones

| By hour | B delivers |
|---|---|
| 2 | Skeleton bot in `main.py` passes smoke, submitted as main |
| 10 | Preflop ranges and sizing plus postflop v1 on stub equity; clearly beats `snapshots/v0` |
| 12 | Merge 1 with A's equity engine |
| 24 | Sizing, multiway adjustments, c-bets and semi-bluffs; parameters ready for C |
| 26-38 | Parameter tuning by grid search over seeds with the harness |
