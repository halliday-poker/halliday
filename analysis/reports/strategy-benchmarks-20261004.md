# Halliday strategy benchmarks — 4 October 2026

## Tuning results

The research baseline is the Python bot at the start of the study, hash `8015e4b3`, preserved in `snapshots/analysis_baseline_20261004`. Eleven initial alternatives were tested. These are tuning results, not confirmation of an improvement. Each comparison uses identical opponent lineups and duplicate decks, paired by complete table. None of these experiments has been promoted. Later changes from main are evaluated separately below.

All tested bluff weights use the existing private hash of visible game context. This reproducible weighted decision is applied only after the value-action checks; it does not make every action random. The search covered bluff frequencies 0%, 35%, 65%, 85% and the 100% baseline, plus a 65%/bet-size combination. It is a limited grid, not a proof of globally optimal weights.

| Variant | Learned-field tuning tables | Delta bb/100, 95% interval | Delta round points, 95% interval | Reference-field delta round points |
|---|---:|---:|---:|---:|
| river_guard | 192 | -2.648 ±3.499 | -0.081 ±0.122 | +0.026 ±0.145 |
| turn_discipline | 192 | -0.234 ±3.308 | -0.008 ±0.107 | +0.036 ±0.089 |
| shove_callers | 192 | -5.516 ±3.901 | -0.036 ±0.040 | +0.000 ±0.000 |
| mixed_35 | 192 | +0.839 ±4.456 | +0.049 ±0.117 | +0.042 ±0.153 |
| mixed_65 | 352 | +0.880 ±2.772 | +0.036 ±0.081 | +0.031 ±0.104 |
| value_pressure | 352 | +1.196 ±2.707 | +0.013 ±0.079 | -0.005 ±0.153 |
| small_ball | 192 | +0.817 ±6.128 | +0.000 ±0.129 | +0.094 ±0.150 |
| mixed_00 | 160 | -1.701 ±5.277 | -0.144 ±0.161 | not in initial reference screen |
| mixed_85 | 160 | +0.782 ±3.778 | -0.019 ±0.093 | not in initial reference screen |
| pressure_mixed_65 | 160 | +0.348 ±5.427 | -0.025 ±0.154 | not in initial reference screen |
| shove_ranges_only | 160 | +3.290 ±6.366 | -0.016 ±0.044 | not in initial reference screen |

Intervals in this display are nominal. Machine-readable summaries also retain intervals adjusted for the number of candidates in that comparison. Candidates have differing tuning-table counts because the last four were proposed after the initial screens. Treat these as exploratory results.

`river_guard` lowers the range bluff floor and tightens river calls/reraises. `turn_discipline` adds turn/river/large-bet caution. `shove_callers` raises the evidence threshold for a shove-heavy opponent and corrects cold-caller range handling; it loses chips in the learned field. `shove_ranges_only` isolates that range correction with the original thresholds. `value_pressure` changes continuation, late-value and raise sizes; `small_ball` makes them smaller. Exact parameter overrides and source fingerprints are in each candidate’s `variant.json`.

No candidate demonstrated superiority during tuning. The 65% bluff variant was chosen for independent confirmation because its small tournament-point delta was positive on all three learned-field seeds. The selection and fixed 1,200-table confirmation plan were saved before the new run in `confirmation-plan.json`. Main-bot replacement requires a positive lower 95% bound for the paired round-point difference, no failures, and no material stress-test regression.

## Resource and packaging checks

The baseline passed three actual 100-hand SDK subprocess games, and the finalist passed nine. The CPU-only launcher enforces one CPU affinity, a 512 MiB address-space ceiling, a read-only chroot, a fresh 64 MiB tmpfs per game, no external network interface, and the actual 30-second + 0.1-second/hand clock. This validates cooperative code; it is not a hardened replica of the judge.

- baseline: 3 games, all verdicts OK; maximum RSS 38.45 MiB; maximum cumulative action wait 4.560 seconds out of the 40-second total allowance.
- mixed65: 9 games, all verdicts OK; maximum RSS 38.82 MiB; maximum cumulative action wait 4.884 seconds out of the 40-second total allowance.

Both archives have a root `main.py`, match the verified source byte-for-byte, contain no replay/model data, and pass ZIP integrity and safe-path checks. Baseline: 12 files, 106,111 bytes unpacked; finalist: 13 files, 107,330 bytes. Both are far below 300 files / 20 MiB unpacked. `package-checks.json` records every content hash. Packaging does not assert that the finalist improves performance.

## Independent confirmation and tournament simulation

The 65% bluff variant failed its predeclared independent test. Across 1,200 fresh tables (12,038 games), its paired round-point difference was **−0.04958 ± 0.04265**, with a 95% interval entirely below zero. Chip return changed by −1.474 ± 1.523 bb/100. The baseline scored 3.7604 round points per table versus 3.7108 for the variant. The harness's legacy A/B label uses chips; this study's frozen primary outcome is round points.

| Fixed stress test | Tables / games | Paired round-point change, 95% interval | Paired bb/100 change, 95% interval |
|---|---:|---:|---:|
| Original ParamBot reference field | 200 / 2,006 | −0.0725 ± 0.0841 | −0.289 ± 1.748 |
| Eight-seat learned field | 128 / 2,048 | +0.0547 ± 0.1750 | −0.951 ± 2.673 |
| Default adversarial pool, CPU | 128 / 1,268 | +0.0078 ± 0.0474 | −0.772 ± 2.990 |

No stress test established superiority. All games completed without candidate or opponent failures.

### Four-round tournament and fresh replication

These simulations use 76 entrants: Halliday and 75 observed external display identities, excluding `house:call`. Every round plays complete seat rotations, awards game points from chip standings, awards round points from aggregate game points, then regroups by cumulative round points and game points. Table sizes are balanced near five. The real final roster and exact table/tie allocation were unavailable. Final prize ties remain unresolved; “definite” top three includes only candidates whose entire tie group fits within three places, and “possible” includes ties spanning third place.

| Study | Candidate | Events | Mean final rank, 95% interval | Mean cumulative round points, 95% interval | Definite / possible top three |
|---|---|---:|---:|---:|---:|
| Initial study | Baseline | 20 | 17.925 ± 5.838 | 14.775 ± 0.909 | 3 / 4 |
| Initial study | 65% bluffs | 20 | 13.150 ± 5.628 | 16.225 ± 1.257 | 8 / 8 |
| Fresh replication | Baseline | 40 | 16.225 ± 4.295 | 15.263 ± 0.753 | 4 / 5 |
| Fresh replication | 65% bluffs | 40 | 18.200 ± 4.252 | 14.875 ± 0.705 | 2 / 4 |

The initial 12,160-game study suggested +1.45 ± 1.23 cumulative points for the variant, conflicting with the independent table test. A new 40-seed replication was frozen before new outcomes, keeping both bot hashes unchanged and playing another 24,320 games. Its paired point change was **−0.3875 ± 0.8225**, with a 10,000-resample event-bootstrap interval **[−1.2000, +0.4375]**. Mean rank changed by +1.975 (worse), bootstrap interval [−2.5125, +6.4000]. The initial apparent advantage did not replicate. The 65% variant is rejected for promotion.

All four tournament artifacts passed an independent audit of complete event grids, duplicate rotations, zero-sum chip accounting, game and round scoring, every regrouping step, final ranks and player verdicts. There were no failures. These intervals describe simulation sampling error; they exclude errors in the opponent replicas and uncertainty about the actual entrants.

The completed study through this replication contains 76,321 full 100-hand simulation games (7,632,100 hands), excluding small smoke tests and the 12 restricted CPU games. The additional range-prior screen and newly merged main are recorded separately below.

## Additional range-prior screen

The latest intervals of 74 external ladder identities have equal-bot mean VPIP/PFR/3-bet rates of 0.2976/0.1745/0.0720 and medians of 0.2211/0.1368/0.0424. These motivate two isolated prior replacements. A third variant lowers the range prior from 12 to 4 hands and the showdown prior from 6 to 2 observations. The earlier isolated shove-range correction is retested alongside them. All use the frozen research baseline. The fixed 192-table screen requires a positive family-adjusted lower 95% bound on paired round points before any further independent confirmation; fitting these priors to this field is exploratory.

| Variant | Delta bb/100, 95% interval | Delta round points, 95% interval | Family-adjusted round-point interval |
|---|---:|---:|---:|
| field_mean_priors | +0.780 ± 4.409 | -0.08073 ± 0.10261 | [-0.21148, +0.05002] |
| field_median_priors | -3.565 ± 4.573 | -0.02604 ± 0.12404 | [-0.18411, +0.13202] |
| fast_adaptation | -1.595 ± 5.137 | -0.10156 ± 0.13375 | [-0.27201, +0.06888] |
| shove_ranges_only | -1.269 ± 2.024 | -0.01302 ± 0.02653 | [-0.04683, +0.02078] |

All 4,795 games completed without failures. None qualifies for independent confirmation under the frozen selection rule. The isolated shove correction also failed to repeat its earlier chip gain. Retain the production strategy inherited from main; none of these fourteen research variants has established an improvement.

This additional screen raises the completed total before the main-integration run to 81,116 full games (8,111,600 hands), excluding smoke and resource checks.

## Main-branch integration

Main advanced to `6cfdf0f` during this study. Its wider small-blind steal range, limped-flop bets and short-table out-of-position continuation bets were merged separately. The results above still refer to the frozen pre-merge research baseline and must not be attributed to the newly merged bot. Its independent 400-table comparison completed 4,016 games without failures. The frozen baseline earned +85.110 ± 13.451 bb/100 and 3.75875 ± 0.11972 round points; newly merged main earned +86.909 ± 13.568 bb/100 and 3.76750 ± 0.12011 points. Paired changes were **+1.799 ± 3.728 bb/100** and **+0.00875 ± 0.09299 round points**. Both intervals include zero: this run establishes neither an improvement nor a significant regression. The upstream features remain integrated, with their research uncertainty explicit.

Including this run, the study completed **85,132 full 100-hand simulation games (8,513,200 hands)**, plus 15 restricted CPU games and the separate smoke tests. All major simulation games completed without failures. The [evidence index](evidence/20261004/index.json) links the frozen plans, complete-table summaries, tournament verification, source hashes and resource checks.


The merged source (`bb2090c7`) passed three 100-hand restricted CPU protocol games with every verdict OK. Maximum resident memory was 39,472 KiB (38.55 MiB), and maximum cumulative action wait was 3.550 seconds of the 40-second allowance. Its archive contains 12 files, 109,778 bytes unpacked and 42,043 bytes compressed, with a root `main.py`, safe paths, matching source bytes and valid ZIP integrity. `main-package-check.json` retains content hashes. These resource checks validate this source; historical baseline and rejected candidate checks remain separate.

After merging main, all 132 repository tests passed with CUDA enabled (49.3 seconds, no skips). The Halliday replay verifier also passed again against the unchanged input snapshot, including exact reproduction of public-range estimates after hidden fields were removed. The production bot equals the newly merged upstream source; no experimental candidate replaces it.
