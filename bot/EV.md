# EV action selection (postflop)

> **Status: built, tested, and switched off by default** (`ev_enabled: False`). It wins
> chips from passive callers but loses to aggressive and drifting opponents, and it never
> improved round points. With it off, the bot plays like `main` (see Validation). Turn it
> on with `ev_enabled: True`.

When enabled, the bot stops comparing equity with fixed thresholds and special-case rules
postflop. It scores every candidate action in chips and takes the best. Code: [ev.py](ev.py).
Wiring: `MyBot.ev_action` in [main.py](main.py). Parameters: the `ev_*` block in
[params.py](params.py). Preflop is unchanged (charts plus the shover rule).

## How a decision is made

1. **Candidates:** check or fold; call; bets of ⅓, ⅔ and 1× pot when checked to;
   raises of 0.75× and 1.25× the after-call pot when facing a bet. All in is a candidate
   only when our stack is at most 3× the pot.
2. **Opponent ranges:** each opponent's tracked range ([RANGES.md](RANGES.md)), capped
   at its heaviest 300 combos. Proven shovers and opponents who haven't acted hold any two
   cards.
3. **Our share against each combo,** over sampled runouts (exact on the river, every
   river card on the turn, 40 sampled turn-and-river pairs on the flop), within a 60 ms
   budget.
4. **How each opponent responds to a bet:** every combo keeps playing with a chance that
   rises with its strength on this board, from `ev_continue_floor` to
   `ev_continue_ceiling` around a cutoff:
   - The cutoff rises with bet size and for raises, up to a cap of 0.95, so the top of a
     range always continues.
   - It falls when we bet out of position, because the field calls those more.
   - It shifts by how loose this player's showdowns have shown it to be.
   - Junk calls shrink once a bet exceeds the pot.

   The resulting fold chance is then pulled toward how often this player has actually
   folded to our bets this game (`ev_fold_evidence`).
5. **EV of each candidate**, treating the hand as going to showdown after this action:
   - `EV(check) = R × equity × pot`
   - `EV(call) = R × equity × (pot + to_call) − to_call`
   - `EV(bet)` sums over every combination of who continues: everyone folding wins the
     pot; otherwise our share against their continuing ranges times the final pot, minus
     our bet.
   - With several opponents, equities multiply, which assumes independence.
   - R is 1 in position and `ev_realize_oop` when we act first.
6. **Choice:** a bet must beat the best passive action by `ev_bet_margin` × pot. Among
   bets within `ev_size_tolerance` × pot of the best, the smallest wins. A call must beat
   folding by `ev_call_margin` × pot.

**The old rules still decide** when EV is off, with more than `ev_max_opponents`
opponents, below the low-clock threshold, on a royal-flush board, or if anything fails.
`MyBot.last_ev` holds the EV table of the last decision, for debugging.

**What the model leaves out:**
- opponents re-raising after we bet (their raising hands count as calls)
- betting on later streets
- side pots

The margins and the size tolerance absorb some of that optimism.

## Parameters

| Parameter | Default | Raise it to... |
|---|---|---|
| `ev_enabled` | on | (off = the rule chain) |
| `ev_max_opponents` | 3 | Use EV in bigger multiway pots (the independence assumption gets worse) |
| `ev_bet_sizes` / `ev_raise_sizes` | (0.33, 0.66, 1.0) / (0.75, 1.25) | Change the candidate sizes |
| `ev_allin_spr` | 3.0 | Consider all in with deeper stacks |
| **`ev_continue_floor`** | 0.20 | **Expect more calls from junk** (fewer bluffs) |
| `ev_continue_ceiling` | 0.92 | Expect strong hands to fold less |
| **`ev_continue_cut`** | 0.62 | **Expect more folds** (prior, before this game's evidence) |
| `ev_continue_cut_max` | 0.95 | Let huge bets fold out stronger hands |
| `ev_continue_softness` | 0.10 | Blur the line between folding and continuing hands |
| **`ev_oop_continue_shift`** | 0.15 | **Expect more calls when we bet out of position** |
| **`ev_fold_evidence`** | 6 | **Trust the model longer** before this game's observed folds take over |
| `ev_realize_oop` | 0.92 | Value out-of-position equity more |
| **`ev_bet_margin`** / `ev_call_margin` | 0.03 / 0.0 | **Bet** / call less often (protection against model optimism) |
| `ev_size_tolerance` | 0.02 | Prefer smaller bets more often |
| `ev_max_combos`, `ev_flop_runouts`, `ev_time_budget_ms`, `ev_min_runouts` | 300, 40, 60, 8 | Spend more time for more precise EVs |

The EV model also reads `range_size_slope`, `range_raise_shift`, `range_draw_bonus` and
`range_call_cut` from the range-tracking block.

Opponents can also re-raise: each raises a share of the hands it continues with, at its
re-raise rate this game (pulled toward `ev_raise_prior`), to `ev_reraise_multiple` times
our bet. If raised, the model calls when our share of the bigger pot pays for it, and
otherwise gives up its bet.

## Validation (3 Oct 2026)

All results are paired against `main` (`d4d593d`) on identical tables and cards, at 4-6
seats. The pools:
- **default:** [pools/default.txt](../harness/pools/default.txt)
- **drifting:** [pools/drifting.txt](../harness/pools/drifting.txt)
- **aggressive:** maniac ×2, tag, nit, station, `param:maniac`, `param:lag`

| Version | Pool | Tables | Chips (mbb/hand) | Round points |
|---|---|---|---|---|
| EV v1 + range recalibration | default | 100 | +528 ± 272 | −0.06 ± 0.18 |
| EV v1, `main`'s ranges | default | 200 | +277 ± 179 | **−0.16 ± 0.14** |
| EV v1 + recalibration | default | 200 | +285 ± 177 | −0.06 ± 0.13 |
| EV v1, `main`'s ranges | drifting | 200 | **−189 ± 64** | **−0.39 ± 0.17** |
| EV v1 + recalibration | drifting | 200 | −58 ± 58 | −0.10 ± 0.16 |
| EV v2 (re-raise model) + recalibration | default | 200 | **+311 ± 188** | −0.03 ± 0.12 |
| EV v2 + recalibration | drifting | 200 | −41 ± 56 | −0.13 ± 0.15 |
| EV v3 (+ frequency cutoffs) + recalibration | aggressive | 120 | **−581 ± 213** | −0.09 ± 0.14 |
| Rules (no EV) + recalibration + frequency cutoffs | aggressive | 120 | **−508 ± 133** | −0.09 ± 0.13 |
| **EV v3, `main`'s ranges (final)** | default | 200 | +204 ± 196 | **−0.17 ± 0.14** |
| **EV v3, `main`'s ranges (final)** | drifting | 200 | **−186 ± 67** | −0.23 ± 0.16 |
| **EV v3, `main`'s ranges (final)** | aggressive | 200 | **−265 ± 140** | −0.10 ± 0.11 |

What the runs show:
- **EV's chip gains are concentrated against passive callers.** On the default pool it gained
  +1,500 at tables with `house:call` and +770 with `sparring/station.py`, through bigger
  value bets. That never turned into better round placement.
- **It loses to aggressive bots.** Against `sparring/maniac.py` it lost −600 to −900. In
  instrumented games against the maniac it folded 63-69% of river bets (rules: 20%) and
  raised 35-37% of flop bets (rules: 8%).
- **The range recalibration** (river bets assumed mostly strong, as the ladder data says)
  made the rule chain itself worse on every sparring pool: −187 ± 113 on the default pool,
  and −508 ± 133 on the aggressive pool together with frequency cutoffs. The sparring bots
  bluff rivers far more than the real ladder does. So those settings default off, and
  which is right depends on the real field.
- **Timing noise:** with EV off, this branch against `main` gives −23 ± 26 on 40 tables, and
  `main` against an exact copy of itself gives +17 ± 23. The equity engine's time budget
  makes results vary slightly under load.

## Why it doesn't win yet, and what to try next

1. **The response model is generic.** One continue curve (floor, ceiling, cutoff) for every
   opponent, adjusted only by aggregate fold and raise counts. Aggressive bots don't fold
   or raise on hand strength the way the curve assumes. Per-opponent response curves,
   fitted on this game's actions or by the planned ladder-trained model, are the main gap.
2. **"Showdown after this action"** ignores later streets. That flatters bets that will get
   raised or bluffed off later, and undervalues pot control.
3. **Ranges feed everything.** Miscalibrated ranges (as with the recalibration above) hurt
   EV more than thresholds, because EV acts on smaller equity edges.
4. **Possible hybrid:** keep the rule chain's decision on *whether* to bet, and use EV only
   to *size* value bets. That's where its gains against callers came from.
5. **Test on a ladder-like pool** (the `est`/`estf` pools in FIELD_EXPLOITS.md) before
   deciding. The sparring pools may not reflect the real field.
