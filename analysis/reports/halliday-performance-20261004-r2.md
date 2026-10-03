# Halliday performance and decision audit — 04 October 2026 (r2)

Source: `analysis/results/refresh-20261004-r2/source/actions.jsonl`, SHA-256 `5e375a6e55ccec731fbb047758cf47192aeb2c3d89821a14290aa771029a91c1`. The recorded name is `Halliday`. Main results cover 44 ladder matches, 4,400 hands, and 5,687 decisions. Table sizes observed: 4, 5, 6, 7, 8 seats; stacks reset to 200 chips per hand with a two-chip big blind. Recorded match times span 04 Oct 04:00:58–04 Oct 06:39:41, Australia/Melbourne. Hand numbers are zero-based.

## Main findings

This report uses an explicit selection of 44 matches. Earlier Halliday intervals are excluded; the selected IDs are recorded in extraction.json. Replay identity and upload timing do not prove which Git source was deployed.

Halliday's net result was +275 chips (+3.12 big blinds per 100 hands). It folded 3,621 times (82.30% of hands). Both public-information range models flag 1 terminal calls, including 1 on the river. Folding at those flagged decisions changes recorded outcomes by -271 chips. This is a retrospective comparison within the same hands, not a predicted gain on new games.

There were 3 model-supported missed-call flags (0.08% of folds), of which 1 also had positive call expectation against the actual hidden hands. The audit found 0 provably avoidable folds. Most folds leave future betting unresolved, so these figures do not establish the true unnecessary-fold rate. They do not support indiscriminately widening the bot's range.

Runout diagnostic: 19 auditable all-in hands returned +663 chips against +550.9 expected with the recorded hands, a +112.1-chip difference. This isolates cards dealt after betting ended. It does not certify the earlier decisions or provide a complete skill-adjusted win rate.

Recency matters: the latest 20 ladder games returned -460 chips over 2,000 hands and contain 0 terminal call/fold flags under this method. Changes in opponents, cards and possible same-name bot replacements prevent attributing differences to a specific code update.

| Metric | Ladder result |
|---|---|
| Matches / hands / actions | 44 / 4,400 / 5,687 |
| Net chips / bb per 100 hands | +275 / +3.12 |
| Positive / negative games | 22 / 22 |
| Mean chips/game, approximate 95% interval | +6.25 ± 62.93 |
| Latest 20 games: net chips / bb per 100 hands | -460 / -11.50 |

The interval treats matches as independent observations. Shared opponents, related deals and bot changes weaken that assumption. No version hash or decision-time equity/range/clock trace is recorded, so these findings cannot be attributed to the current source branch.

## How often does it fold?

Halliday folded in 3,621/4,400 hands (82.30%): 3,430 preflop (77.95% of all hands), and 191 postflop. Folds were 63.67% of all actions and 74.26% of decisions facing a positive call price. A hand can have several decisions but at most one Halliday fold.

| Street | Folds | Decisions facing a bet | Fold rate facing a bet | Calls | Raises / opening bets |
|---|---|---|---|---|---|
| Preflop | 3,430 | 4,410 | 77.78% | 308 | 673 |
| Flop | 114 | 268 | 42.54% | 149 | 215 |
| Turn | 46 | 125 | 36.80% | 69 | 150 |
| River | 31 | 73 | 42.47% | 40 | 67 |

There were 0 preflop folds of pocket aces. Across ten-hand blocks within games, all-street fold rates ranged from 80.23% to 85.45%. There is no obvious late-game jump to universal folding in these aggregate counts. Timing and verdict records would be needed to diagnose a time-bank fallback.

## How often were folds unnecessary?

A terminal call closes the river betting, or closes betting with at most one live player retaining chips. These opportunities allow a direct call-versus-fold comparison without assuming later betting behavior. Side pots, dead money, stack caps and sunk investments are included.

| Evidence | Count | Meaning |
|---|---|---|
| Provably avoidable fold | 0 | A free check or a guaranteed profitable terminal call was available. |
| Probable missed terminal call under both public-range models | 3 | 0.08% of all folds; 9.09% of the 33 terminal folds. |
| Public-model flag also positive against recorded hidden hands | 1 | 0.03% of all folds; useful review candidates, still model-dependent. |
| Profitable call against actual hands, with no later betting | 6 | 18.18% of terminal folds; hindsight only. |
| Of those, river calls that would win or share | 4 | Finished-board hindsight; opponent cards were not visible at the decision. |

Only 33/3,621 folds (0.91%) meet the terminal condition. Their street counts are preflop: 4, flop: 0, turn: 4, river: 25. This limited coverage is why the report gives flagged cases rather than a single supposedly exact unnecessary-fold percentage.

Among the 3 public-model flags, 2 were not favorable against the actual hidden cards. The combined actual-hand call expectation of all 3 flags is +57.6 chips. This is a warning about model uncertainty, not a reason to judge a decision by the hidden cards alone.

The data also contains 1,275 positive hidden-card checkdown estimates and 104 folds that would share the recorded final board. Only 544 folded hands have a five-card board recorded. These figures assume hidden cards, a selected future board, or unresolved opponents checking down; they are not blunder counts.

### Missed-call cases supported by both models and actual-hand expectation

| Match / hand | Holding / street | Call / pot before call | Public EV: tight / loose | Actual-hand call EV |
|---|---|---|---|---|
| `j979vrq746cjcbwjeqk0antg258fjj34` / h51 | Jd Js / preflop | 182 / 221 | +14.9 / +55.2 | +215.8 |

## Weaknesses and action classifications

### 1. Expensive river calls with weak showdown value

Both models flag 1/40 river calls (2.50%). Folding at those decisions changes the recorded results by -271 chips, excluding earlier sunk investments. The 1 total bad-terminal-call flags span 1 games; 1 occurred in hands that won chips. These labels depend on the tested opponent ranges. Review the listed contexts before inferring a recurring calling weakness or changing the strategy.

| Match / hand | Hole cards | Board | Call / pot | Public EV: tight / loose | Hand chips |
|---|---|---|---|---|---|
| `j97asm3sachknn1x52ka0pgnbh8fj60k` / h61 | 8h 8s | 6s Kd 3c 9c 4c | 131 / 271 | -119.4 / -53.5 | 202 |

### 2. Nonterminal calls and later decisions

There are 0 additional call-review flags, 0 on the turn. Such flags require negative checkdown expectation under both models, but implied odds, future folds and future bets prevent a firm blunder diagnosis. Turn and river costs from the same hand must not be added as independent savings.

### 3. Adaptation and range calibration

The fold rate alone does not establish that a wider range would improve returns. The flagged calls and folds identify contexts for checking range calibration, rather than a validated change in aggressiveness. A publicly demonstrated frequent shover and a selective caller of that shove need separate ranges. Record decision-time ranges and equity to distinguish estimation errors from deliberate strategy choices.

### 4. Bluff outcomes are review labels, not automatic blunders

The audit labels 15 failed high-card/no-draw bets and 14 failed semibluff actions. A profitable bluff strategy loses some called bets. The replay does not reveal how opponents would react to different bet sizes, so this audit cannot establish optimal bluff frequency or missed value bets.

| Action classification | Ladder actions | Evidence level |
|---|---|---|
| certain_avoidable_fold | 0 | Provable dominance in the audited context |
| probable_bad_terminal_call | 1 | Both public models below −2 chips, including sampling margin |
| probable_missed_terminal_call | 3 | Both public models above +2 chips, including sampling margin |
| possible_nonterminal_bad_call | 0 | Review candidate; future betting omitted |
| possible_nonterminal_overfold | 0 | Review candidate; future betting omitted |
| hindsight_losing_call_only | 26 | Hidden-card evidence only |
| hindsight_missed_call_only | 5 | Hidden-card evidence only |
| failed_air_bet / failed_semibluff | 15 / 14 | Outcome labels |
| All remaining actions | 5623 | No error established; alternatives may be unassessed |

## What happened in negative-chip matches?

The 22 negative ladder games total -3,456 chips. 0 contain a probable terminal call/fold flag; 22 have no such flag. A negative result alone is insufficient to conclude that the bot played badly. The following exclusive hand categories reconcile to the negative-game total; the amounts include full hand results, not the marginal cost of a flagged action.

| Hand category inside negative games | Hands | Actual chips |
|---|---|---|
| Other showdown losses; decision quality unresolved | 30 | -2,528 |
| Other all-in losses; decision quality unresolved | 6 | -1,200 |
| Postflop investment, then fold | 93 | -1,152 |
| Blind-only folds | 589 | -867 |
| Failed high-card bluff hands | 9 | -444 |
| Failed semibluff hands | 11 | -392 |
| Preflop investment, then fold | 32 | -174 |
| Winning / break-even hands | 1,430 | +3,301 |

### Worst five games: decision flags versus all-in runouts

`j97fpmcf5371heqmbr0khkrz0d8fjj5k`: -505 chips, 0 bad-call flags and 0 missed-call flags. Its 1 auditable all-in hands returned +0 chips versus +10.1 expected against the recorded hands (-10.1 runout difference). No terminal decision blunder is established by the tested range models. The runout estimate addresses the cards after betting ended, not the quality of every earlier action.

`j975e155mcdgk969pf1n0q27g58fjhtw`: -403 chips, 0 bad-call flags and 0 missed-call flags. Its 1 auditable all-in hands returned -200 chips versus -111.6 expected against the recorded hands (-88.4 runout difference). No terminal decision blunder is established by the tested range models. The runout estimate addresses the cards after betting ended, not the quality of every earlier action.

`j970yjhs6ehenmf5nbf2f88m5h8fkg18`: -400 chips, 0 bad-call flags and 0 missed-call flags. Its 1 auditable all-in hands returned -200 chips versus -61.1 expected against the recorded hands (-138.9 runout difference). No terminal decision blunder is established by the tested range models. The runout estimate addresses the cards after betting ended, not the quality of every earlier action.

`j9716rfv1xv9vzpq71vnbeaxb98fj0t7`: -290 chips, 0 bad-call flags and 0 missed-call flags. Its 0 auditable all-in hands returned +0 chips versus +0.0 expected against the recorded hands (+0.0 runout difference). No terminal decision blunder is established by the tested range models. The runout estimate addresses the cards after betting ended, not the quality of every earlier action.

`j97d5qnmmgqkrg6qvyj5w4whnn8fksc2`: -249 chips, 0 bad-call flags and 0 missed-call flags. Its 1 auditable all-in hands returned -200 chips versus -149.2 expected against the recorded hands (-50.8 runout difference). No terminal decision blunder is established by the tested range models. The runout estimate addresses the cards after betting ended, not the quality of every earlier action.

### Every losing game

Call/fold flags are model-dependent. The largest loss category is descriptive and may include sound decisions. “Fold-at-call saving” changes only flagged terminal calls, includes flagged calls that won, and does not include missed-call estimates. It must not be added to the all-in runout difference because the same hands can appear in both.

| Match | Chips | Call / fold flags | Fold-at-call saving | All-in runout difference | Largest loss category | Hands to review |
|---|---|---|---|---|---|---|
| `j97fpmcf5371heqmbr0khkrz0d8fjj5k` | -505 | 0 / 0 | +0 | -10 | Other showdown losses; decision quality unresolved (-471) | h45 largest loss; unflagged |
| `j975e155mcdgk969pf1n0q27g58fjhtw` | -403 | 0 / 0 | +0 | -88 | Other showdown losses; decision quality unresolved (-200) | h18 largest loss; unflagged |
| `j970yjhs6ehenmf5nbf2f88m5h8fkg18` | -400 | 0 / 0 | +0 | -139 | Other all-in losses; decision quality unresolved (-200) | h46 largest loss; unflagged |
| `j9716rfv1xv9vzpq71vnbeaxb98fj0t7` | -290 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-210) | h55 largest loss; unflagged |
| `j97d5qnmmgqkrg6qvyj5w4whnn8fksc2` | -249 | 0 / 0 | +0 | -51 | Other all-in losses; decision quality unresolved (-200) | h79 largest loss; unflagged |
| `j970wj4mmdcjd2h2w92wxqghys8fkes9` | -235 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-137) | h29 largest loss; unflagged |
| `j97cvyj4r4cq24g1zhxv9v7rvn8fjzjj` | -220 | 0 / 0 | +0 | +0 | Failed semibluff hands (-118) | h65 largest loss; unflagged |
| `j9728kgdgejfzhwr8pxbvz52bs8fks9q` | -181 | 0 / 0 | +0 | +0 | Postflop investment, then fold (-100) | h50 largest loss; unflagged |
| `j97b8arnqw91p1acdkp5eapg898fjh9y` | -168 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-294) | h72 largest loss; unflagged |
| `j974jyjwy0v0t5z1ykcdk3ptsx8fjkrr` | -135 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-200) | h3 largest loss; unflagged |
| `j9747a4qrbcxfvx130np1j8kn58fknfr` | -120 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-227) | h77 largest loss; unflagged |
| `j975pf4d54y5qd4fdwx3776rhh8fjb12` | -116 | 0 / 0 | +0 | +0 | Postflop investment, then fold (-111) | h85 largest loss; unflagged |
| `j97aeaqnp26ah110sh5a4vpvdx8fksv8` | -100 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-186) | h48 largest loss; unflagged |
| `j97f8bdekjfjwkt8zmh4949dwh8fkz8d` | -88 | 0 / 0 | +0 | +0 | Blind-only folds (-45) | h97 largest loss; unflagged |
| `j9785rjwgh6eabvh62s3a05nds8fjy0n` | -52 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-73) | h90 largest loss; unflagged |
| `j97fdsa53cjvz3mnwxqct4efsh8fjedj` | -51 | 0 / 0 | +0 | +0 | Failed high-card bluff hands (-97) | h54 largest loss; unflagged |
| `j97ac0wxak2ejtsn28xbehmm458fj3hh` | -47 | 0 / 0 | +0 | +0 | Blind-only folds (-41) | h36 largest loss; unflagged |
| `j97e9zrasmz11egv0ktf8g3xfx8fjbhn` | -39 | 0 / 0 | +0 | +0 | Other showdown losses; decision quality unresolved (-174) | h24 largest loss; unflagged |
| `j975f9x85654fdcpntys7h2d3d8fjfpc` | -28 | 0 / 0 | +0 | -43 | Other all-in losses; decision quality unresolved (-200) | h82 largest loss; unflagged |
| `j978a3ay48t19qsx9sje4ek9hh8fjrg5` | -14 | 0 / 0 | +0 | -22 | Other all-in losses; decision quality unresolved (-200) | h25 largest loss; unflagged |
| `j9792z8p6hak0bjrndsfbwpt4s8fk47y` | -13 | 0 / 0 | +0 | +0 | Postflop investment, then fold (-111) | h53 largest loss; unflagged |
| `j972y98ssa5y9pn5xpr1dqp3398fkf6k` | -2 | 0 / 0 | +0 | -12 | Other all-in losses; decision quality unresolved (-200) | h54 largest loss; unflagged |

## Chronology and limits on current-version conclusions

| Time quarter, Melbourne | Games | Chips | Folds / hands | Terminal flags |
|---|---|---|---|---|
| 04 Oct 04:00:58 – 04 Oct 05:28:41 | 11 | +442 | 964/1,100 | 1 |
| 04 Oct 05:30:40 – 04 Oct 05:52:36 | 11 | +389 | 934/1,100 | 3 |
| 04 Oct 05:55:39 – 04 Oct 06:17:21 | 11 | -259 | 883/1,100 | 0 |
| 04 Oct 06:19:25 – 04 Oct 06:39:41 | 11 | -297 | 840/1,100 | 0 |

The latest 20 games contain 0 bad-terminal-call flags and 0 missed-terminal-call flags, with 1,549 folds (77.45% of hands). No flag is not a certificate of correct play: this method does not solve all preflop, raise-sizing, bluff and future-street decisions. Timestamp units are normalized for ordering. The report does not infer deployment boundaries from a name or a validation game.

## All probable blunders: action-level review list

The full CSV includes every action. This shorter list contains only provable or probable terminal decision flags. “Actual EV” uses hidden cards and must not be substituted for the public-information decision models. Positive hand chips do not remove a decision flag.

| Match / hand / action # | Class | Cards / board | Call / pot | Public call EV: tight / loose | Actual call EV | Hand chips |
|---|---|---|---|---|---|---|
| `j97fhpndam4yyhtea3xr7rmfvn8fk9qs` / 45 / 11 | missed_terminal_call | Qs As / (preflop) | 165 / 444 | +39.8 / +67.9 | -81.3 | -35 |
| `j979vrq746cjcbwjeqk0antg258fjj34` / 47 / 9 | missed_terminal_call | Jh Js / (preflop) | 170 / 237 | +32.5 / +72.3 | -76.8 | -30 |
| `j979vrq746cjcbwjeqk0antg258fjj34` / 51 / 8 | missed_terminal_call | Jd Js / (preflop) | 182 / 221 | +14.9 / +55.2 | +215.8 | -18 |
| `j97asm3sachknn1x52ka0pgnbh8fj60k` / 61 / 14 | bad_terminal_call | 8h 8s / 6s Kd 3c 9c 4c | 131 / 271 | -119.4 / -53.5 | +271.0 | 202 |

## Method, verification and limitations

The source contains 2,120,024 rows from 2,164 matches. Metadata lists 44 Halliday matches; 44 have replay actions (0 missing). The 0 validation games contribute 0 hands and +0 chips and are excluded from ladder rates. All replays combined: 4,400 hands, 5,687 actions, +275 chips.

Every recorded pot, legal action amount, seat/name mapping, hole-card consistency check, final seat/bot delta, odd-chip allocation and pot winner was checked. All 44 match totals reconcile; hands are contiguous, and 0 target hands failed reconstruction. The independent SDK evaluated 1,076 contested pot layers.

Call EV is expected hero-eligible gross payout minus the additional call. Already invested chips are sunk. For terminal decisions, no additional future betting is required. Nonterminal estimates assume all currently live players match the current bet, within stack caps, then check down. They omit future raises, folds, implied odds and value bets.

The actual-hand calculation conditions on all recorded hole cards, including folded cards, and only the board visible at the decision. Flop/turn runouts are enumerated exactly; preflop uses 4,096 seeded runouts. Future board cards do not choose the sampled runouts. Fractional tied payouts are used for EV, while actual settlement separately checks integer odd chips.

Public models see only Halliday’s hole cards, the visible board and preceding public actions. They do not see hidden opponent cards or future outcomes. Tight preflop VPIP/PFR/3-bet widths are 22%/12%/5%; loose widths are 45%/30%/14%. Postflop bet/call cutoffs and bluff floors are 0.75/0.50/0.10 versus 0.55/0.30/0.30. An opponent publicly observed to shove in at least 80% of eight or more prior hands receives an any-two preflop prior when shoving. Other players retain their own likelihood updates. Hole cards are sampled jointly with collision rejection.

Both models scored 388 facing-bet contexts: every terminal opportunity and heads-up postflop opportunities. Terminal estimates use 8,192 samples per model; others use 4,096. A probable flag requires both models to disagree with the action by more than two chips after a 1.96-standard-error sampling margin. That margin covers Monte Carlo noise, not range-model error or the many decisions screened. Both models share the repository’s action-likelihood functions, so they are sensitivity checks, not independent empirical validation or a poker solver. Preflop raise size is not fully modeled as a range signal.

All actions receive a classification, but checks and raises are not exhaustively optimized. A not-flagged action may have unassessed alternatives. The total error rate cannot be inferred from the fraction of labels marked probable. Neither lost chips nor a hidden-card winner alone proves a blunder.

| GPU worker | Games scored | Seven-card rankings | Device buffers |
|---|---|---|---|
| cuda:0 | 10 | 18,617,090 | 1,179,648 bytes |
| cuda:1 | 12 | 21,535,896 | 1,179,648 bytes |
| cuda:2 | 11 | 19,767,506 | 1,179,648 bytes |
| cuda:3 | 11 | 20,052,262 | 1,179,648 bytes |

4 V100 workers ran in parallel and executed 79,972,754 actual CUDA seven-card rankings. The computation stage took 10.0 seconds, including worker startup and result serialization. Each worker also needs a CUDA context beyond the listed buffers. Packed GPU rankings are checked against CPU evaluation at startup. Extraction, reconstruction, verification and rendering are separate stages.

Final verification: 7 audit tests passed. All 5,687 action IDs and 4,400 hand IDs are unique, all 44 match totals and exclusive loss buckets reconcile, and prior histories contain no future actions. Both public-range models were reproduced exactly in 7 representative contexts after removing every field outside the explicit public-information allowlist. The source SHA-256 was unchanged after computation. Source-code fingerprints, tested context IDs and test output are retained alongside this report.

## Prioritized improvements to test

| Priority | Change to investigate | Validation |
|---|---|---|
| 1 | Record version hashes, verdicts and decision-time ranges/equity. | Identify the deployed source and compare its estimates with held-out outcomes. |
| 2 | Replay the terminal call/fold flags under opponent-specific ranges. | Test sensitivity to range assumptions; a flagged hand alone does not validate a fix. |
| 3 | Review the largest losing hands and earlier betting choices. | Measure complete hand outcomes; avoid double-counting alternative fold points. |
| 4 | Distinguish frequent shovers from selective callers of their shoves. | Use earlier public actions only; test any changes on untouched matches. |
| 5 | Assess additional opens, bluff sizing and future-street choices separately. | Use fresh duplicate-deck simulations; this terminal audit does not optimize them. |

## Files and reproduction

[Every action and classification](../results/halliday-performance-20261004-r2/action-classifications.csv) · [Probable blunders](../results/halliday-performance-20261004-r2/blunders.csv) · [Every match review](../results/halliday-performance-20261004-r2/match-reviews.csv) · [Every hand outcome](../results/halliday-performance-20261004-r2/hand-outcomes.csv) · [Summary JSON](../results/halliday-performance-20261004-r2/summary.json).

[Detailed actions with full prior histories](../results/halliday-performance-20261004-r2/classified-actions.json), [reconstruction audit](../results/halliday-performance-20261004-r2/reconstruction-audit.json), [input fingerprints](../results/halliday-performance-20261004-r2/extraction.json), [GPU work](../results/halliday-performance-20261004-r2/gpu-work.json), and [final verification](../results/halliday-performance-20261004-r2/verification.json) retain the evidence. Large result files are local and Git-ignored. Preserve the result directory when collecting a newer snapshot.

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B analysis/halliday_performance.py extract --snapshot analysis/results/refresh-20261004-r2/source --directory analysis/results/halliday-performance-20261004-r2 --match-ids analysis/results/halliday-performance-20261004-r2/selected-match-ids.json
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B analysis/halliday_performance.py prepare --directory analysis/results/halliday-performance-20261004-r2
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B analysis/halliday_performance.py compute --devices 0,1,2,3 --directory analysis/results/halliday-performance-20261004-r2
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B analysis/halliday_report.py --directory analysis/results/halliday-performance-20261004-r2
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B analysis/verify_halliday_report.py --directory analysis/results/halliday-performance-20261004-r2
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B analysis/render_halliday_report.py --directory analysis/results/halliday-performance-20261004-r2
```
