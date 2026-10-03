# Simulation fidelity — 4 October 2026

The replicas predict recorded actions substantially better. Matching historical opponent intervals brings simulated Halliday results closer to the observed interval, but frozen-baseline results remain more optimistic. Do not treat simulated win rates as forecasts of the live leaderboard.

## Matching the observed table composition

The 43 latest Halliday ladder games were replayed as table compositions on fresh duplicate deals: 344 games per candidate. These preserve eight-seat lineups, not original decks or actions.

| Halliday source | bb/100, approximate 95% interval | Folded hands | VPIP | PFR |
|---|---:|---:|---:|---:|
| Observed latest interval | -18.09 ± 34.26 | 89.70% | 15.63% | 9.81% |
| Halliday replica / newest opponents | +13.00 ± 10.95 | 89.13% | 16.26% | 10.50% |
| Frozen baseline / newest opponents | +30.38 ± 12.00 | 90.41% | 14.92% | 9.26% |
| Halliday replica / observed opponent intervals | -3.49 ± 11.28 | 88.55% | 16.53% | 11.00% |
| Frozen baseline / observed opponent intervals | +24.66 ± 9.66 | 89.83% | 15.03% | 9.86% |

134 of the 301 opponent seats belong to earlier intervals than the newest available one. A separate fresh-deck run used each opponent’s estimated interval for the actual historical match. Its Halliday-replica point estimate is closer to observed returns. The two simulations use different seeds, so this is not an isolated causal estimate of changing intervals. Matching observed contexts is a descriptive check on a refitted model, separate from the whole-match held-out predictive test.

The latest interval’s 30 auditable all-ins were 1,027.8 chips below expectation against the recorded hands. Subtracting only that runout effect leaves -528.2 chips (-6.14 bb/100), rather than the observed -1,556. This is not a complete skill-adjusted return. The gap between the frozen baseline and the learned replica can reflect approximation error or an unknown code version; it does not establish which source ran historically.

## Opponent action-rate discrepancies

Below are the largest absolute VPIP differences among identities present in at least three observed matches. More detail is retained in `closed-loop-fidelity.json`. These marginal rates include lineup effects and differing opponent versions.

| Identity | Real matches | Real VPIP | Newest-interval VPIP | Matched-interval VPIP | Real PFR | Matched-interval PFR |
|---|---:|---:|---:|---:|---:|---:|
| testQ | 12 | 47.17% | 23.31% | 44.82% | 2.50% | 2.91% |
| preflop-warrior | 20 | 25.75% | 42.82% | 25.81% | 12.20% | 12.99% |
| the GOON | 27 | 41.93% | 25.87% | 44.77% | 19.74% | 19.72% |
| idc | 11 | 14.91% | 23.89% | 15.99% | 11.09% | 10.57% |
| Gladiator_v3 | 4 | 35.75% | 31.03% | 31.66% | 14.00% | 12.06% |
| catherine | 8 | 24.00% | 28.23% | 24.39% | 14.88% | 16.06% |
| MAC Projects Team Testing Bot 2 | 4 | 21.75% | 25.50% | 24.97% | 17.50% | 18.22% |
| merch where | 10 | 89.30% | 86.16% | 88.94% | 44.20% | 43.85% |
| tungbot | 4 | 25.50% | 28.50% | 26.47% | 16.00% | 16.25% |
| Messi | 5 | 14.20% | 16.70% | 16.85% | 0.00% | 0.35% |
| love-of-da-game | 14 | 18.93% | 21.15% | 20.28% | 14.00% | 15.07% |
| guaguanco 5 | 22 | 17.86% | 19.66% | 19.34% | 14.45% | 15.32% |

## Sensitivity to the opponent model

On the same 400 randomly drawn 4–6-seat duplicate tables (1,970 games each), the frozen Halliday baseline (`8015e4b3`) earned +85.70 ±14.06 bb/100 against the learned replicas and +28.73 ±4.97 against the original scaffold fits. Round placement points were much closer: 3.704 ±0.122 and 3.718 ±0.134. A small number of large pots can materially change chip returns without improving placement.

The broader small-table pool includes every observed external name, including old aliases and the validation house bot. It differs from Halliday’s recent eight-seat opponents. Neither model is calibrated by forcing Halliday’s aggregate win rate to match observed losses. Strategy selection must use independent paired deals, tournament points, both model families and eight-seat stress tests.

Source artifacts: `harness/results/20261004-014228.json`, `20261004-015231.json`, `20261004-015019.json`, `20261004-033206.json`. No candidate or opponent failures occurred in these runs. Confidence intervals measure simulation sampling uncertainty and exclude opponent-model error.
