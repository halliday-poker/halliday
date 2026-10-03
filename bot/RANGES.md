# Range tracking and showdown learning

Equity used to assume every opponent held random cards, with fixed margins making up for
it. Now each opponent's range is tracked through the hand and narrowed by their actions,
and this game's showdowns tune how each player's betting is read. Code: [ranges.py](ranges.py).
Wiring: [main.py](main.py). Parameters: the `range_*` block in [params.py](params.py).

## How it works

1. **Start of hand:** each opponent can hold any of the 1,326 two-card combos, equally likely.
2. **Each action multiplies every combo's weight by how likely that action is with it**,
   using soft cutoffs on hand strength rather than all-or-nothing ranges:

   | Street | Strength of a combo | Cutoffs come from |
   |---|---|---|
   | Preflop | Rank of its class by equity vs random hands ([hand_ranks.py](hand_ranks.py); heads-up ranking at 2-3 seats, multiway at 4+) | This game's VPIP / PFR / 3-bet counts for that player ([opponents.py](opponents.py)), pulled toward field priors |
   | Postflop | Share of all combos its made hand beats on this board, plus a bonus for flush and open-ended straight draws | Priors, then this player's showdowns |

   - Raises open with the top PFR share, 3-bet with the top 3-bet share, and each further
     re-raise uses a smaller share. Calls and limps play the top VPIP share, minus some of
     the hands that would have raised. Checks keep some strong hands (slow-plays).
   - Postflop, bets need strength above a cutoff, which rises with bet size and for raises.
     Weak hands still bet at the player's bluff floor. Calls need a lower cutoff.
3. **Equity is computed against the tracked ranges.** Ranges still close to uniform are
   passed as random cards. A proven shover's range always stays random cards, because the
   shover rule depends on that.
4. **Decisions switch to range-mode margins.** The old margins exist because random-card
   equity overrates us against selective bettors, and keeping them with ranges would
   penalise opponents' strength twice.
5. **Showdowns update each player's cutoffs and bluff floor** for the rest of the game:
   - Each shown postflop bet records whether it was above or below that player's betting
     cutoff. That moves their bluff floor, and the strength of their above-cutoff bets moves
     the cutoff itself.
   - Shown calls move their calling cutoff.
   - **Samples are weighted by bias.** Bluffs that worked are never shown, so only a bet
     whose call led to the showdown counts fully. Earlier bets and calls count less.

Hooks only record events. All computing happens inside `act()`, which is where the
tournament's clock runs. The harness only times `act()`, so this keeps its timing honest.
Nothing persists between games, and players are identified only by this game's id.

## Parameters

All live in `DEFAULT_PARAMS`. **Bold** marks the ones most worth tuning first.

| Parameter | Default | Raise it to... |
|---|---|---|
| `range_enabled` / `range_multiway` / `range_learn_showdowns` | on | Switches: tracking at all; using ranges with 2+ opponents; showdown learning |
| `range_prior_vpip` / `_pfr` / `_threebet` | 0.35 / 0.20 / 0.08 | Assume looser preflop ranges before evidence |
| `range_prior_hands` | 12 | Trust the priors longer (each player's counts take more hands to dominate) |
| **`range_temper`** | 0.8 | **Narrow ranges harder per action** (1 = full Bayesian update, 0 = actions mean nothing) |
| **`range_floor`** | 0.03 | **Keep unlikely hands more alive**: the most any action can cut a combo (about 16x at the defaults) |
| `range_preflop_softness` | 0.25 | Blur preflop cutoffs (ramp width as a share of the range) |
| `range_postflop_softness` | 0.08 | Blur postflop cutoffs (in strength units) |
| `range_4bet_ratio` | 0.5 | Assume wider 4-bet / 5-bet ranges (each re-raise range vs the last) |
| `range_slowplay` | 0.25 | Assume more strong hands check or just call |
| **`range_bet_cut`** | 0.60 | **Read bets as stronger** (prior, before showdowns) |
| `range_call_cut` | 0.35 | Read calls as stronger |
| `range_raise_shift` | 0.15 | Read raises over a bet as stronger than bets |
| `range_size_slope` | 0.15 | Make bet size matter more (overbets beyond 2x pot read as 2x) |
| `range_draw_bonus` | 0.20 | Treat draws as stronger hands when betting or calling |
| **`range_bluff_floor`** | 0.30 | **Assume more bluffs** (prior: weak hands bet this often relative to strong ones; was 0.6 from the bugged "56% air" figure; big ladder turn/river bets are 12-15% air) |
| `range_bluff_turn_factor` / `_river_factor` | 1.0 / 1.0 | Scale the floor further on later streets (lower = read big late bets as stronger; ~0.7 / 0.35 lost to the sparring pools, see [EV.md](EV.md)) |
| `range_frequency_cuts` / `range_frequency_weight` | off / 10 | Set each player's betting and calling cutoffs from how often it bets and continues (off: tested worse together with the river factors) |
| `range_showdown_prior` | 6 | Learn from showdowns more slowly (the priors are worth this many shown samples) |
| `range_showdown_weight_indirect` | 0.5 | Trust shown bets from earlier streets more |
| `range_showdown_weight_passive` | 0.4 | Trust shown calls more |
| `range_max_combos` | 400 | Pass more combos to the engine (more accurate, slower) |
| `range_uniform_skip` | 0.90 | Use random cards for ranges that are this close to uniform (cheaper) |
| **`range_call_margin_flop` / `_turn` / `_river`** | 0.03 / 0.03 / 0.02 | **Call less often against tracked ranges** |
| `range_large_bet_margin` / `range_reraise_margin` | 0.02 / 0.03 | Extra caution against big bets / re-raises in range mode |
| `range_preflop_call_margin` | 0.03 | Range-mode margin for the large-preflop-bet whitelist |

The range code uses no other magic numbers. The only fixed choices are clamps that keep
learned cutoffs inside sensible bounds, and reading overbets beyond 2x pot as 2x.

## Tuning workflow

Copy the bot, change one parameter, and A/B it on fresh seeds:

```sh
cp -r bot ../tune/temper09          # edit range_temper in ../tune/temper09/params.py
python harness/eval.py run bot ../tune/temper09 --no-league --tables 200 --seed t1
```

- Change one thing at a time, and confirm a win on a second seed before keeping it.
- **Be suspicious of gains against `param:*` opponents.** They decide by hand-strength
  thresholds, which is exactly what this model assumes, so the harness flatters it.
  Before trusting a big change, check it against the ladder replays, which include every
  hole card: under the predicted ranges, how likely was each player's true hand compared
  with random cards?

## Validation (3 Oct 2026)

Against an unchanged copy of `main` (`27ff240`), on identical tables and cards, with the
default pool (no league), 200 tables per seed, 4-6 seats:

| Seed | Range tracking vs `main` (mbb/hand) | Round points |
|---|---|---|
| rt-a (before vectorising and the shover fix) | +260 ± 124 | +0.18 ± 0.13 |
| rt-b | **+288 ± 101** | +0.24 ± 0.11 |
| rt-c | **+256 ± 92** | +0.18 ± 0.11 |

- **Drifting field** ([harness/pools/drifting.txt](../harness/pools/drifting.txt): every
  seat is [sparring/drifter.py](../sparring/drifter.py), which starts as a random style
  including a shover, and each hand has a 5% chance of switching style or rescaling 1-3 of
  its settings). 200 tables per seed:

  | Seed | Range tracking vs `main` | vs fixed baseline `d2557d0` | `main` vs fixed baseline |
  |---|---|---|---|
  | drift-1 | **+107 ± 51** | **+165 ± 77** | +57 ± 66 (inconclusive) |
  | drift-2 | **+78 ± 50** | **+177 ± 74** | +99 ± 65 |

  Reads that go stale don't erase the gain, but it shrinks: about +90 here against about
  +270 on the default pool, while every bot wins far less against this field. The
  counters and showdown statistics never forget, so a player who changes style is still
  read by its old habits. Decaying old evidence is the obvious next experiment.
- On rt-b, the same bot with showdown learning off scored +256 ± 104. So learning adds
  roughly +30 on top, which isn't yet distinguishable from noise.
- Gains are spread across every opponent type. The early-game loss against `house:allin`
  seen on rt-a was fixed by keeping proven shovers' ranges random.
- **Timing (single process, 6 seats, 600 decisions):** median 11 ms, 99th percentile 23 ms,
  max 27 ms, about 1.7 s of the 40 s clock per game. Under full 15-worker harness load the
  slowest decision was 120 ms, with 17% of the clock used.
- The subprocess smoke test passed, all games `OK`.
- [tests/test_ranges.py](../tests/test_ranges.py) has 17 tests: the direction of narrowing,
  floors, `temper = 0` changing nothing, bet size, blockers, timing, showdown learning both
  ways, counter correctness, fallback when tracking fails, and full games.

## Known limitations

- **Opponents are read independently.** In multiway pots, a caller's range really depends
  on everyone's actions; the engine only stops two players holding the same card.
- **The strength ladder is the current made hand,** not equity, so draws rely on the bonus
  and the "draw" test (flush draws, open-enders, double gutshots).
- **Showdown samples are still biased** after weighting, and there are few per game. The
  priors do most of the work.
- **The priors are guesses informed by the field-exploit data,** not fitted. Fitting them on
  the ladder replays is the obvious next step.
- **Our own range isn't modelled.** Nothing here reasons about what opponents think we hold.
