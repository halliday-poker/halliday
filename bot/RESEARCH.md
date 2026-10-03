# Research upgrades (4 Oct 2026)

Five preflop upgrades. Each was found from a leak analysis of the bot against the fitted
ladder field, grounded in standard exploitative-poker reasoning, and tested in paired
harness runs (same tables, cards and seats; 200 duplicate tables per run; 4-6 seats).
All five are on by default, with the robust settings described below. Parameters live in
the "Research upgrades" block of [params.py](params.py); counters in
[opponents.py](opponents.py); logic in [preflop.py](preflop.py).

**Evaluation pools:**
- **fitted:** `sparring/competitors/from_data/pool.txt`, the 66 ladder bots fitted onto
  `param.py`.
- **drifting:** opponents change style mid-game.
- **default:** house bots, sparring stereotypes and randomised param bots.

All runs used 8 workers, one at a time.

## Starting point: where the bot was losing

A leak analysis of 60,100 hands against the fitted field showed the current bot at
**+24.8 bb/100**. It played only 21% of hands and raised 17% preflop. Its big blind played
just 16-19% of hands (the 6-max big blind lost −17 bb/100), and opening then folding to a
3-bet cost −3,782 bb. The fitted field's settings explain the opportunity:

- **42 of 66 bots 3-bet less than 5% of the time.** In the bots' code, facing a 3-bet they
  continue only with roughly the top `threebet × (0.6 + stickiness)`, which means folding
  about 97% of an opening range for a median bot.
- A quarter of them play more than 48% of hands, and 20 of 66 almost never fold
  postflop (stickiness above 0.7).
- **Facing an open, they defend only about `vpip × (0.3 + 0.5 × stickiness)`**, so most
  hands fold to a raise.

## The five upgrades

### 1. Light 3-bets against openers who fold too often (`light3bet`)
- **Research:** fold-to-3-bet is the classic HUD exploit. A 3-bet risks R to win the pot
  P, so it profits on its own when the opener folds more than R / (R + P). A 2.5× 3-bet
  over a 2.5bb open risks about 12.5 to win about 8, which breaks even at roughly 61%
  before counting equity when called.
- **Logic:** track each opener's fold-to-3-bet rate, recency-weighted (old chances decay
  by 0.75 per new chance) and pulled toward a 60% prior. 3-bet the top 55% of hands only
  while that estimate is at least 65%.
- **Evidence on the fitted pool:**
  - Original setting (35% of hands, 0.60 threshold): +93 ± 51 and +135 ± 54 mbb/hand.
  - Wider settings: +244 to +528.
  - **Safe setting: +135 ± 41 mbb/hand and +0.31 ± 0.14 round points.**
- **Robustness:**
  - The aggressive settings (90% of hands, 0.40 threshold) **lost significantly to
    drifting opponents twice** (−116 ± 66 and −91 ± 70). Bots that turn into maniacs or
    shovers keep getting 3-bet off stale evidence.
  - The safe setting was neutral on drifting in both runs (+4 ± 31, +12 ± 31). That's why
    it's the default.
  - Smaller 3-bets (2.5× in position, 3× out of position) add about +50, because these
    opponents decide whether to fold regardless of size.

### 2. Open wider against tables that fold (`open_wide`, `steal_wide`)
- **Research:** fold-to-steal and fold-to-open exploitation. An open of 2.5bb risks 5 to
  win 3, so it profits on its own whenever everyone behind folds more than 62.5% of the
  time combined.
- **Logic:**
  - `open_wide`: from any position, open the top 50% of hands when the product of each
    remaining player's fold-to-open rate (prior 0.75) is at least 0.55.
  - `steal_wide`: from the cutoff, button or small blind, open the top 60% of hands when
    every remaining blind's fold-to-steal rate (prior 0.55) is at least 0.65.
- **Evidence on the fitted pool:**
  - Steals: +29 ± 17, +39 ± 22, +55 ± 19 (**pooled +41 ± 11**).
  - Open wide: +25 ± 21, +57 ± 22 (**pooled +40 ± 15**).
  - Together, on top of light 3-bets: **+51 ± 27**.

### 3. Wider big blind defence (`bb_defend_wide`)
- **Research:** pot odds and minimum defence frequency. Against a 2.5bb open, the big
  blind calls 3 to win 8 (3.5 : 1, needing about 27% equity). Theory-based ranges defend
  around 40% or more; the old chart covered 28% of hands.
- **Logic:** against opens of at most 3bb, defend a 49% range (pairs, any suited ace or
  king, most suited connectors and gappers, broadways and strong offsuit aces and kings).
- **Evidence on the fitted pool:** +41 ± 31, +62 ± 36, +14 ± 33 (**pooled +38 ± 19**).
  On top of light 3-bets: +18 ± 18.

### 4. Flat-call wider against loose openers (`call_vs_loose`)
- **Research:** a loose opener's range is weak, so calling it in position with hands that
  would fold against a tight range is profitable.
- **Logic:** when the opener's preflop raise rate (prior 0.18, 12 hands' weight) is at
  least 30%, call with the top 35% of hands instead of the standard calling chart.
- **Evidence on the fitted pool:** +73 ± 46, +28 ± 34 (**pooled +44 ± 27**).

### 5. Fight back against frequent 3-bettors (`vs_light3`)
- **Research:** a player who 3-bets far too often has a weak 3-betting range, so folding
  most of an opening range to it is exploitable.
- **Logic:** when the 3-bettor's observed 3-bet rate (prior 0.08, 10 chances' weight) is
  at least 20%, 4-bet TT+, AQs+ and AKo, and call a wider range (55+, A8s+, KTs+, QTs+,
  JTs, T9s, AJo+, KQo).
- **Evidence on the fitted pool:** +32 ± 31, +28 ± 30 (**pooled +30 ± 21**). Together
  with #4, on top of light 3-bets: **+70 ± 38**.

## All five together

| Configuration | Fitted pool | Drifting pool | Default pool |
|---|---|---|---|
| Everything, aggressive light 3-bets | **+644 ± 91**, round +0.85 | −71 ± 70 | **+244 ± 143** |
| **Everything, safe light 3-bets (default)** | **+288 ± 58, round +0.53 ± 0.17** | +35 ± 55 | n/a |

On the same tables, the features add +122 ± 49 on top of aggressive light 3-bets. The
default configuration roughly doubles the bot's win rate against the fitted ladder field
(about +300 mbb/hand at baseline), with no measurable loss against opponents that change.

## Tested and rejected

| Idea | Result (paired, mbb/hand) | Why it doesn't help |
|---|---|---|
| Isolation raises over limpers | −1 ± 30, round −0.13 | Limpers' calling ranges are strong enough |
| Squeeze (light 3-bet with callers) | about +15 over light 3-bets, not significant | Few spots |
| Value against stations (thinner, bigger) | −3 ± 5 | Rarely triggers: needs 8+ bets observed |
| Bluff-catching against frequent bettors | +7 ± 11 | Frequent bettors also bet value |
| Bigger opens (3bb) | −4 ± 18 | The field's preflop calls ignore size |
| Bigger 3-bets (3.5× / 4.5×) | +3 ± 7 | Same reason; smaller is better (see #1) |
| More equity samples (2,000 / 80 ms) | 0 ± 19 | Equity noise isn't a bottleneck |
| Recency weighting alone, aggressive light 3-bets | −36 on drifting (vs −34 without) | The threshold matters, not the decay |

## Caveats

- **The fitted bots are surrogates** built on `param.py`. Their fold-to-3-bet behaviour is
  structural to that code, and real ladder bots may fold less. Every upgrade is gated on
  per-opponent evidence, so against a player who doesn't fold the bot falls back to its
  old ranges within a few observations. The drifting-pool results check exactly that.
- Results are against simulated fields and don't predict tournament standings.
- Leak analysis script and per-run logs are local (scratchpad and `harness/results/`).
