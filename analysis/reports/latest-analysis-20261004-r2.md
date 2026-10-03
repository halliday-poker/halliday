# Newest-segment analysis — 20261004-r2

The primary replay comparison includes only matches where Halliday **and every opponent** belong to their newest observed intervals. Simulations instantiate only newest trusted ladder intervals and use the exact freshly fetched `main` bot as their baseline.

Baseline commit: `6cfdf0f44b332933d88d440791e7151028061849`; snapshot `snapshots/main_6cfdf0f_r2`, harness hash `26121bc2`. Every file was copied directly from that Git tree. The previous merged-main research snapshot included the analysis branch’s GPU engine hook; the early fourteen strategy experiments used an older frozen baseline. They are not the baseline for this rerun.

Successful validation marks an upload, not proof that it was selected as main. These data support newest **observed** intervals, not certified deployment versions. Display identities may also be aliases; no team/source hash is available to resolve every rename.

## Input and selection

- Actions SHA-256: `5e375a6e55ccec731fbb047758cf47192aeb2c3d89821a14290aa771029a91c1`.
- 2,120,024 rows, 2,164 replay matches and 2,168 metadata matches. 4 metadata matches have no replay rows and are excluded.
- 89 rebuilt identities: 86 learned policies and 3 sparse/validation fallbacks.
- Strict simulation field: 65 external identities. Excludes Halliday, the house bot, validation-only evidence and identities without trusted play timestamps.
- Halliday newest interval: 73 ladder matches; 44 have every seat in its newest interval and form the primary replay cohort.

[Exact selection and exclusions](evidence/20261004-r2/latest-selection.json) retain each interval, match ID and successful-upload boundary. The shared neural model learns from historical intervals with separate epoch features; older intervals are not instantiated as opponents in this field. The initial upload was incomplete and was not analysed. The final frozen copy passed NUL, JSON, metadata and collected-state checks.

## Latest-cohort Halliday performance

| Metric | Result |
|---|---:|
| Matches / hands / decisions | 44 / 4,400 / 5,687 |
| Net chips / bb per 100 hands | +275 / +3.125 |
| Folds / fraction of hands | 3,621 / 82.30% |
| Preflop folds / fraction of hands | 3,430 / 77.95% |
| Probable bad terminal calls / missed terminal calls | 1 / 3 |
| Auditable terminal folds / all folds | 33 / 3,621 |
| Losing games / those with terminal flags | 22 / 0 |

1 of 1 flagged terminal calls won their hands. Folding at the flagged calls changes recorded results by -271 chips. 2 of 3 model-supported missed calls had negative expectation against the actual hidden hands. These are sensitivity-model review candidates, not certain mistakes. Losing games with a terminal decision flag: 0/22. Checks, raises and nonterminal choices are not exhaustively optimized.

Record decision-time ranges and equity for reviewing these contexts; the current replay lacks those diagnostics. Historical calling-leak counts should not automatically carry forward to this cohort. Only 0.91% of folds meet the terminal audit condition; the true unnecessary-fold rate remains unknown. Changes in table size, opponents and selection prevent treating differences from the earlier report as a causal code improvement.

[Detailed report and hand histories](halliday-performance-20261004-r2.md) · [Flagged actions](halliday-blunders-20261004-r2.csv) · [Every match review](halliday-match-reviews-20261004-r2.csv).

## Predictive accuracy on newest intervals

The common test contains 88,097 decisions from 196 held-out matches, restricted to the newest trusted intervals of included identities and Halliday. Whole matches are held out together. Other seats need not be in their newest interval for this conditional action-prediction test. Selection and stopping use validation data, not these test scores.

| Predictor | Action log loss ↓ | Accuracy ↑ | Brier ↓ | Raise-target MAE, chips ↓ |
|---|---:|---:|---:|---:|
| original_scaffold | 0.6931 | 81.39% | 0.3264 | 6.945 |
| none | 0.2795 | 88.10% | 0.1674 | 7.059 |
| upload | 0.2436 | 89.67% | 0.1458 | 5.846 |
| placebo | 0.2569 | 89.11% | 0.1535 | 6.371 |
| change | 0.2918 | 88.72% | 0.1593 | 6.456 |

The validation-selected model is **upload**. Upload-model gains over the scaffold, no-interval model and randomized-boundary control all have positive per-match bootstrap intervals after adjustment for three comparisons. Predictive support for upload intervals does not establish deployment at every validation event.

## Exact-main simulations

The broad field used 400 duplicate tables and 1,994 complete 100-hand games. Exact main earned **+33.607 ± 4.818 bb/100** and **+3.691 ± 0.121 round points**. The field samples 4–6 seats, so its returns are not directly comparable with the observed cohort’s different table mix.

A separate composition-matched check uses the 44 strict observed lineups and fresh duplicate decks. Both Halliday candidates face the same newest opponent replicas. This describes behavior of refitted models, not held-out closed-loop validation or reconstruction of the original deals.

| Halliday source | bb/100, approximate 95% interval | Folded hands | VPIP | PFR |
|---|---:|---:|---:|---:|
| Recorded newest interval, all seats newest | +3.125 ± 31.463 | 82.30% | 21.89% | 15.20% |
| Exact main | +9.755 ± 13.904 | 85.00% | 19.98% | 13.82% |
| Latest Halliday replica | -4.099 ± 15.816 | 83.80% | 21.06% | 14.64% |

10 four-round tournaments with 66 entrants completed 2,640 games. Mean final rank: **+10.300 ± 4.993**; cumulative round points: **+16.000 ± 1.490**; definite top-three finishes: **2/10**. The roster is an observed-identity surrogate; actual entrants, source versions and prize tie-breaks may differ.

Total this rerun: **5,118 simulation games / 511,800 hands**, with no player failures. Complete rotations, chip conservation and tournament scoring/regrouping passed their audits. Intervals reflect sampled tables/events and exclude opponent-model error; this limited event sample cannot establish a stable tournament win probability.

## GPU use, runtime limits and verification

Four V100s refit the estimators and trained four model ablations concurrently. 4 GPU audit workers performed 79,972,754 rankings across 44 replay matches. Simulation selected 12 cpu workers. Reason: no bot in this field exposes a compatible batched equity engine. The tournament harness checks compatibility before choosing CUDA; merely creating GPU contexts does not accelerate an incompatible engine.

All **144 tests passed with CUDA enabled**. Exact main also passed 9 restricted CPU games: one core, 512 MiB address-space limit, read-only filesystem, fresh 64 MiB temporary storage, and actual 30 s + 0.1 s/hand clocks. Maximum RSS was 43,588 KiB and cumulative action wait 2.323 s. These are cooperative-code resource checks, not a complete replica of the judge sandbox.

[Reproduction commands](reproduce-latest-20261004-r2.md) · [Compact evidence index](evidence/20261004-r2/index.json). Raw inputs and full game logs remain local under the recorded run directory. Production bot strategy was not changed.
