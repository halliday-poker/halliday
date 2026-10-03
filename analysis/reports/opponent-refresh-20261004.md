# Opponent refresh and predictive validation — 4 October 2026

Source SHA-256: `10331deef87e5cacb4e09ac79c5ebe2d4aeb4ff477b153d20cdb7de8fbd01d9a`. 77 observed identities, 1809 complete matches, 1,147,147 actions. Three metadata matches have no collected replay; the identity Gladiator has no action evidence and is not recreated.

## Validation matches and behavior intervals

The frozen metadata contains 227 validation matches, all team-versus-`house:call`. Public replay verdicts show 224 successful validations and three runtime failures. 226 validation matches have collected action data; 133 of those have trusted server play timestamps. The [official FAQ](https://docs.poker.monashcoding.com/faq/) explains that every upload is validated, but a passing upload must be selected as main (the first passing upload becomes main automatically). Thus validation marks an upload, not a guaranteed deployment. Failed checks and uncertain timestamps are excluded from candidate boundaries.

Successful-upload intervals are adopted because they improved predictions on whole held-out matches, including against randomized boundaries with matched per-bot counts. This is evidence that upload timing helps distinguish behavior, not proof that every event changed deployed code. Unknown-time games remain in a base interval. Latest-segment selection prioritizes intervals containing trusted play timestamps. Team validation hands are excluded from fits wherever ladder evidence exists.

## Predictive comparison

60/20/20 deterministic hash of whole match ID; all bots at a table share a split. Every action and every bot from the same game stays together. The original ten-parameter estimator, including its change detection, was refitted using training matches only. Four CUDA workers then trained the richer alternatives concurrently. Stopping and model choice used validation action log loss plus 0.2 times sizing-bin log loss. The final test set contains 313 ladder games and 221,289 decisions and was excluded from selection.

| Model | Test action log loss ↓ | Brier score ↓ | Action accuracy ↑ | Raise-size MAE, chips ↓ | Calibration error ↓ |
|---|---:|---:|---:|---:|---:|
| Original ParamBot estimates | 0.7552 | 0.3633 | 78.89% | 18.00 | 0.1124 |
| Richer context, no time intervals | 0.2969 | 0.1806 | 87.12% | 8.25 | 0.0017 |
| Richer context, successful-upload intervals | 0.2709 | 0.1635 | 88.43% | 7.71 | 0.0013 |
| Richer context, randomized intervals | 0.2870 | 0.1728 | 87.69% | 8.16 | 0.0017 |
| Richer context, detected-change intervals | 0.2838 | 0.1648 | 88.22% | 8.49 | 0.0027 |

Lower log loss/Brier scores indicate better probability forecasts. Calibration error is aggregate confidence-bin error; it can hide subgroup errors. The JSON also retains per-bot, per-street and per-match diagnostics. Size MAE compares a predicted central target with the recorded raise target; it is not a full distributional size score. The models use legal-action masks. Their probability forecasts are not claims to solve poker optimally.

| Reference → candidate | Mean whole-match log-loss improvement | 95% paired bootstrap interval | Interval adjusted for seven comparisons |
|---|---:|---|---|
| baseline → none | 0.4891 | [0.4688, 0.5109] | [0.4623, 0.5197] |
| baseline → upload | 0.5067 | [0.4868, 0.5282] | [0.4797, 0.5363] |
| baseline → placebo | 0.4967 | [0.4756, 0.5198] | [0.4682, 0.5303] |
| baseline → change | 0.5023 | [0.4805, 0.5259] | [0.4725, 0.5341] |
| none → upload | 0.0176 | [0.0135, 0.0217] | [0.0121, 0.0234] |
| placebo → upload | 0.0100 | [0.0055, 0.0153] | [0.0042, 0.0180] |
| none → change | 0.0133 | [-0.0002, 0.0242] | [-0.0060, 0.0269] |

Bootstrap resampling preserves complete matches and all players at each table. Games can still share opponents or versions, so these intervals do not cover all dependence or model uncertainty. The random split measures held-out games from observed versions; it does not establish reliability on unseen future versions. Selected mode: **upload**, epoch 100. Its final replica was refitted on all available eligible data using that stopping epoch. Refit training scores are not substituted for held-out metrics.

## New estimates and executable behavior

The richer model conditions on own cards, board texture, position, live players, legal raises, call price, stack commitment, previous raises, and public opponent-action counters. It predicts action probabilities and a mixture over ten legal raise targets, including all-in. Runtime sampling uses a private per-game RNG. It sees no hidden opponent cards, future actions or outcomes. NumPy inference was checked against the PyTorch training network; the tournament candidate itself does not contain this learned replica model.

Each interval retains the ten scaffold estimates and whole-match bootstrap uncertainty. Additional conditional rates cover preflop shoves, preflop raise calls, folds facing large commitments, multiway postflop folds, river calls, checked-to bets and reraises. Executable scaffold styles shrink toward the full-bot estimate below six matches. Fewer than two ladder games in the latest interval, or only validation evidence, produces an explicit scaffold fallback.

## Latest interval per observed identity

VPIP/PFR/3-bet below are scaffold settings, not raw action percentages. Shove and river-call columns are measured opportunity-conditioned frequencies; a dash means no observations. Full confidence intervals, opportunity counts and sparse-data statuses are in the JSON and generated profiles manifest.

| Identity | Intervals | Latest matches | Policy | VPIP / PFR / 3-bet | Preflop shove rate | River call rate |
|---|---:|---:|---|---|---:|---:|
| Allen Iverson | 1 | 14 | fitted_public_context_policy | 0.11 / 0.11 / 0.03 | 0.1% | 85.7% |
| Allen Iverson 2.0 | 1 | 24 | fitted_public_context_policy | 0.10 / 0.10 / 0.03 | 0.0% | 51.7% |
| Artificial Incompetence | 1 | 23 | fitted_public_context_policy | 1.00 / 1.00 / 0.24 | 0.3% | 6.6% |
| BigBaller | 3 | 20 | fitted_public_context_policy | 0.22 / 0.22 / 0.07 | 0.2% | 34.4% |
| Gladiator_v3 | 3 | 15 | fitted_public_context_policy | 0.52 / 0.49 / 0.02 | 0.5% | 63.6% |
| Halliday | 3 | 43 | fitted_public_context_policy | 0.14 / 0.14 / 0.03 | 0.1% | 51.2% |
| Invoker | 1 | 13 | fitted_public_context_policy | 0.97 / 0.97 / 0.01 | 0.3% | 44.2% |
| Invokerv2 | 1 | 15 | fitted_public_context_policy | 0.93 / 0.93 / 0.02 | 0.3% | 14.8% |
| Jason_idea | 3 | 1 | sparse_scaffold_fallback | 0.85 / 0.85 / 0.85 | 0.0% | 50.0% |
| LF5 | 1 | 16 | fitted_public_context_policy | 0.03 / 0.03 / 0.03 | 0.4% | 66.7% |
| MAC Projects Team | 1 | 89 | fitted_public_context_policy | 0.00 / 0.00 / 0.00 | 0.0% | 52.5% |
| MAC Projects Team Testing Bot | 1 | 51 | fitted_public_context_policy | 0.23 / 0.23 / 0.04 | 0.2% | 10.9% |
| MAC Projects Team Testing Bot 2 | 2 | 63 | fitted_public_context_policy | 0.23 / 0.23 / 0.06 | 2.7% | 14.1% |
| MAC Projects Team Testing Bot 3 | 1 | 2 | fitted_public_context_policy | 0.22 / 0.21 / 0.06 | 0.5% | 33.3% |
| Messi | 3 | 69 | fitted_public_context_policy | 0.10 / 0.01 / 0.00 | 0.0% | 52.9% |
| Nice Hand, Sir | 1 | 81 | fitted_public_context_policy | 0.97 / 0.97 / 0.06 | 0.1% | 16.9% |
| Phil_Ivey_GOAT | 2 | 61 | fitted_public_context_policy | 0.07 / 0.07 / 0.01 | 0.0% | 53.5% |
| RaiseYourEdge | 2 | 36 | fitted_public_context_policy | 0.15 / 0.15 / 0.05 | 0.2% | 16.7% |
| RiverForge | 2 | 18 | fitted_public_context_policy | 0.16 / 0.16 / 0.01 | 0.1% | 72.2% |
| Thanos | 1 | 18 | fitted_public_context_policy | 0.19 / 0.19 / 0.07 | 0.6% | 67.2% |
| Tilted_Towers_2 | 2 | 70 | fitted_public_context_policy | 0.13 / 0.13 / 0.03 | 0.0% | 71.3% |
| Tilted_towers_1 | 1 | 20 | fitted_public_context_policy | 0.10 / 0.10 / 0.01 | 0.2% | 60.0% |
| Who me? | 1 | 7 | fitted_public_context_policy | 0.48 / 0.06 / 0.06 | 0.0% | 33.3% |
| alo | 1 | 114 | fitted_public_context_policy | 1.00 / 1.00 / 1.00 | 99.3% | — |
| axiom | 2 | 36 | fitted_public_context_policy | 0.22 / 0.22 / 0.06 | 0.0% | 39.3% |
| best-bot | 3 | 51 | fitted_public_context_policy | 0.23 / 0.23 / 0.06 | 0.1% | 40.0% |
| big dog | 1 | 66 | fitted_public_context_policy | 0.22 / 0.22 / 0.03 | 0.2% | 50.0% |
| biji satu | 1 | 9 | fitted_public_context_policy | 1.00 / 1.00 / 0.08 | 0.0% | 18.6% |
| catherine | 6 | 58 | fitted_public_context_policy | 0.18 / 0.18 / 0.03 | 0.1% | 28.6% |
| dan_negreanu_on_ket | 2 | 37 | fitted_public_context_policy | 0.22 / 0.22 / 0.06 | 0.3% | 30.8% |
| diddy blud | 1 | 18 | fitted_public_context_policy | 0.03 / 0.03 / 0.03 | 0.7% | 0.0% |
| dudududu | 1 | 18 | fitted_public_context_policy | 0.18 / 0.18 / 0.04 | 1.3% | 71.4% |
| elaine | 1 | 54 | fitted_public_context_policy | 0.16 / 0.16 / 0.03 | 0.0% | 63.6% |
| finian sucks | 1 | 89 | fitted_public_context_policy | 0.03 / 0.02 / 0.02 | 0.1% | 63.6% |
| fold-a2 | 1 | 20 | fitted_public_context_policy | 0.00 / 0.00 / 0.00 | 0.0% | 68.4% |
| fufufafa | 1 | 20 | fitted_public_context_policy | 0.90 / 0.90 / 0.00 | 0.1% | 18.0% |
| fullhouse | 2 | 21 | fitted_public_context_policy | 0.11 / 0.11 / 0.03 | 0.8% | 25.0% |
| goatbot | 1 | 112 | fitted_public_context_policy | 0.38 / 0.38 / 0.06 | 1.4% | 35.7% |
| guaguanco | 1 | 93 | fitted_public_context_policy | 0.00 / 0.00 / 0.00 | 0.0% | 51.0% |
| guaguanco 2 | 1 | 1 | sparse_scaffold_fallback | 0.29 / 0.18 / 0.07 | 0.0% | — |
| guaguanco 3 | 1 | 108 | fitted_public_context_policy | 1.00 / 0.00 / 0.00 | 0.0% | 37.0% |
| guaguanco 4 | 1 | 26 | fitted_public_context_policy | 0.16 / 0.16 / 0.05 | 1.0% | 70.6% |
| guaguanco 5 | 5 | 34 | fitted_public_context_policy | 0.22 / 0.22 / 0.02 | 0.0% | 39.4% |
| house:call | 1 | 226 | sparse_scaffold_fallback | 1.00 / 0.01 / 0.01 | 0.0% | 100.0% |
| idc | 11 | 2 | fitted_public_context_policy | 0.17 / 0.17 / 0.03 | 0.0% | 66.7% |
| jongwon | 7 | 18 | fitted_public_context_policy | 0.15 / 0.15 / 0.02 | 0.1% | 64.7% |
| kingfisher | 1 | 6 | fitted_public_context_policy | 0.98 / 0.98 / 0.97 | 64.5% | — |
| larp larp sahur | 4 | 15 | fitted_public_context_policy | 0.17 / 0.17 / 0.03 | 0.6% | 42.9% |
| let it go | 2 | 32 | fitted_public_context_policy | 0.06 / 0.00 / 0.00 | 0.0% | 50.0% |
| lil-fruit | 1 | 141 | fitted_public_context_policy | 1.00 / 0.10 / 0.04 | 0.0% | 36.4% |
| lil-fruit 2.2 | 1 | 121 | fitted_public_context_policy | 0.95 / 0.89 / 0.01 | 0.0% | 38.3% |
| lil-fruit x | 1 | 32 | fitted_public_context_policy | 1.00 / 1.00 / 0.39 | 0.3% | 6.1% |
| love-of-da-game | 7 | 22 | fitted_public_context_policy | 0.17 / 0.17 / 0.03 | 0.2% | 28.6% |
| luck is all u need | 11 | 43 | fitted_public_context_policy | 0.13 / 0.13 / 0.02 | 0.0% | 38.5% |
| merch where | 5 | 6 | fitted_public_context_policy | 0.93 / 0.93 / 0.06 | 1.8% | 34.6% |
| netanyahu | 3 | 11 | fitted_public_context_policy | 0.23 / 0.23 / 0.02 | 0.2% | 22.2% |
| pocket-nuts | 2 | 91 | fitted_public_context_policy | 0.17 / 0.17 / 0.06 | 0.3% | 37.9% |
| poke-bowl | 1 | 112 | fitted_public_context_policy | 0.17 / 0.17 / 0.05 | 1.6% | 37.1% |
| poke-bowl-one | 1 | 265 | fitted_public_context_policy | 0.36 / 0.36 / 0.06 | 0.7% | 32.3% |
| polygamous lavender marriage | 6 | 21 | fitted_public_context_policy | 0.22 / 0.22 / 0.03 | 0.0% | 16.7% |
| preflop-warrior | 7 | 11 | fitted_public_context_policy | 0.22 / 0.22 / 0.03 | 0.0% | 53.7% |
| pressure | 1 | 40 | fitted_public_context_policy | 0.10 / 0.10 / 0.03 | 0.4% | 29.4% |
| radishv0 | 1 | 117 | fitted_public_context_policy | 0.64 / 0.52 / 0.05 | 0.1% | 34.6% |
| radishv1 | 1 | 103 | fitted_public_context_policy | 0.38 / 0.38 / 0.02 | 0.6% | 28.2% |
| radishv2 | 1 | 75 | fitted_public_context_policy | 0.38 / 0.38 / 0.02 | 0.5% | 38.4% |
| renbot | 2 | 10 | fitted_public_context_policy | 0.23 / 0.23 / 0.03 | 0.6% | 0.0% |
| samith pai is lowkey leng | 2 | 4 | fitted_public_context_policy | 0.22 / 0.22 / 0.04 | 0.5% | 80.0% |
| scaffold | 1 | 36 | fitted_public_context_policy | 0.00 / 0.00 / 0.00 | 0.0% | 70.7% |
| test1 | 1 | 4 | fitted_public_context_policy | 0.00 / 0.00 / 0.00 | 0.0% | 54.5% |
| testQ | 4 | 7 | fitted_public_context_policy | 0.17 / 0.17 / 0.02 | 0.6% | 61.5% |
| the GOON | 9 | 11 | fitted_public_context_policy | 0.17 / 0.17 / 0.05 | 2.6% | 9.1% |
| the big dog | 2 | 44 | fitted_public_context_policy | 0.17 / 0.17 / 0.03 | 0.4% | 54.3% |
| tripi tropi | 2 | 30 | fitted_public_context_policy | 0.17 / 0.17 / 0.03 | 0.5% | 56.9% |
| tungbot | 3 | 73 | fitted_public_context_policy | 0.22 / 0.22 / 0.06 | 0.7% | 18.8% |
| tutududu | 3 | 32 | fitted_public_context_policy | 0.18 / 0.18 / 0.04 | 0.1% | 48.7% |
| yep | 4 | 8 | fitted_public_context_policy | 0.23 / 0.23 / 0.05 | 0.5% | 20.0% |
| zinger box | 1 | 33 | fitted_public_context_policy | 0.38 / 0.38 / 0.03 | 0.1% | 32.8% |

## Scope and next checks

These are reconstructed opponents, not their source code. Display names can be renamed teams or different code versions. Equal weighting of recorded names is not an authenticated final entrant list. The main replay field has eight seats, whereas tournament tables are commonly smaller; both contexts must be tested. Predictive improvements do not prove that closed-loop simulations reproduce real game winnings. The completed [simulation fidelity report](simulation-fidelity-20261004.md) separates behavioral similarity from the remaining uncertainty in simulated winnings. Strategy tests use fresh paired duplicate tables, with tuning and final confirmation recorded separately.
