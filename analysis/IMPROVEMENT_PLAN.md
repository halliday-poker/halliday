# Completed analysis study — 4 October 2026

The research, implementation, simulations and verification below are complete.
See `analysis/README.md` for the user-facing reports and compact evidence index.
Earlier chronological notes are retained below and their live-session status is
superseded by this completion record.

- Input snapshot unchanged: actions SHA-256 `10331deef87e5cacb4e09ac79c5ebe2d4aeb4ff477b153d20cdb7de8fbd01d9a`.
- Halliday audit: 140 ladder games, 75 losses reviewed, every decision classified.
- Opponent refresh: 77 observed identities, public-context models, held-out
  validation and candidate upload intervals; latest profiles rebuilt separately.
- Four V100s used concurrently. Harness supports shared workers and tournament
  regrouping. Raw game/replay data stays local; compact evidence is versioned.
- Fourteen isolated strategy variants tested. No experimentally established
  improvement: mixed65 failed independent confirmation and fresh replication;
  calibrated priors, faster adaptation and isolated shove correction also failed
  their additional screen. No research variant is promoted.
- Main6cfdf0f merged; new sourcebb2090c7 separately checked over400tables/4016games.
  Paired round points +0.00875 +/-0.09299, inconclusive. Upstream features retained.
- Complete study:85,132 full100-hand simulations, no failures, plus15 restricted
  CPU games and smoke checks. Four-round event scoring independently verified.
- Latest main:38.55MiB peak RSS,3.55s maximum action wait,109778-byte unpacked ZIP.
- All132tests passed with CUDA; replay isolation/accounting verifier passed again.
- Final publication uses branch `analysis/opponent-refresh`; commit and PR describe
  the empirical limitations and include the earlier unmerged GPU harness work.

---

# Opponent refresh and Halliday improvement

Active objective: update opponent estimates and newest-segment competitors from
the October 4 input snapshot, validate their predictive behavior against public
replays, benchmark improved Halliday copies including weighted randomness, and
verify the chosen submission under tournament limits. Branches use `analysis/`.

## Evidence required before completion

1. Frozen inputs, hashes, reconstruction audit, and current official rules.
2. Test whether validation-versus-house:call events indicate deployed versions;
   account for failed validation, repeated submissions, timestamp units, delayed
   collection and version evidence. Use event segmentation if supported.
3. Refresh baseline estimates on all four V100s. Compare candidate richer
   estimates to the old approach on whole held-out matches, including action
   likelihood/calibration, sizing, uncertainty and sparse-version behavior.
4. Regenerate `sparring/competitors/from_data` from newest segments. Keep
   interpretable provenance and an executable fallback for sparse versions.
5. Validate harness parity, real-replay opponent/table composition, CPU/GPU
   numerical parity and scheduling. Quantify differences between observed
   Halliday results and simulated results, rather than optimizing only for a
   matching aggregate win rate.
6. Preserve a baseline copy of Halliday. Benchmark separate variants addressing
   river calling, opponent-range calibration and shove adaptation, plus weighted
   stochastic strategies and other evidence-supported alternatives.
7. Separate tuning seeds/data from untouched test seeds/data; compare paired
   duplicate tables, scoring points, uncertainty, individual opponents and
   adverse/cross-model scenarios. Keep running meaningful simulations while
   findings require follow-up; do not claim universal optimality from a finite
   benchmark.
8. Select and package the best supported candidate after real subprocess tests:
   one CPU core, 512 MiB memory, 30 s initial clock + 0.1 s/hand, read-only
   filesystem, fresh 64 MiB `/tmp`, at most 20 MiB unpacked zip. Record archive
   contents, sizes, resource measurements, failures and reproducible commands.

## Current state

- Prior Halliday performance audit is preserved under
  `analysis/results/halliday-performance-20261003` and `analysis/reports`.
- Current-snapshot Halliday audit is complete under
  `analysis/results/halliday-performance-20261004`, with Markdown/HTML reports in
  `analysis/reports`. All 143 matches, 14,006 hands and 17,865 decisions reconcile;
  4 parallel V100 workers performed 333,756,251 rankings. Ladder results:
  140 games, -6,772 chips, 88.97% hands folded, 38 probable bad terminal calls
  and 10 probable missed calls under two sensitivity models. No terminal model
  flags occur in the latest 20 games. These are historical identity-level
  findings, not proof of defects in the current source branch. Every action,
  losing game and flagged decision has a review artifact. Range-model error
  and unmodeled future betting limit the unnecessary-fold estimate.
- Refreshed inputs frozen at `analysis/results/refresh-20261004/source`.
- Snapshot metadata has 1,812 matches: 1,585 ladder and 227 validation. Every
  validation matchup includes only one team identity and `house:call`.
- Four V100s are available. Existing CUDA estimator and harness implementations
  will be retained as reference implementations until comparisons are complete.
- Documentation and API evidence are being collected under
  `analysis/results/refresh-20261004/web`.
- Baseline refresh completed on all four V100s (48.8 seconds): 77 observed
  identities, 1,809 replay matches, 1,147,147 actions. Artifacts:
  `baseline-estimates.json`, `baseline-features.npz`, `baseline-run.log`.
- Public-context schema now includes 13 additional fields. Original cache
  format remains readable with explicitly missing context. New cache:
  `context-features.npz`. Replay/runtime feature parity passed on an actual
  rotating 30-hand SDK game; labels and match IDs are excluded from features.
- Four predictive ablations trained concurrently on V100s, selected on a
  deterministic 60/20/20 whole-match split. Final held-out evidence (313 ladder
  games, 221,289 decisions): original scaffold NLL 0.7552 versus richer upload
  model 0.2709, Brier 0.3633 versus 0.1635, raise-target MAE 18.00 versus 7.71
  chips. Upload intervals beat no intervals and a matched randomized-boundary
  control, with whole-match bootstrap intervals adjusted for seven comparisons
  excluding zero. Detailed artifacts: `behavior-comparison.json`,
  `policy-{none,upload,placebo,change}.json`, `training-baseline.json`.
- Official FAQ confirms validation means upload; passing versions must be
  selected as main (first pass automatic). All 227 metadata validations pair
  a team with house:call, 224 OK and three RTE. One has no collected replay;
  133 of the remaining 226 have trusted server timestamps. Epochs are candidate
  behavior intervals, not asserted deployments. Failed/unknown-time events
  are excluded. See `validation-meta.json` and `opponent_model/validation.py`.
- Selected upload model refitted for 100 epochs on all eligible data. New
  estimates/summaries are in `refresh-20261004/opponent-estimates*` and copied
  to the canonical `analysis/results/opponent-estimates*`. Human report:
  `analysis/reports/opponent-refresh-20261004.md`.
- `from_data` regenerated for 77 identities (74 learned context policies, three
  sparse/validation scaffold fallbacks; known house:call uses its actual constant
  call/check behavior). `param_reference` preserves the refreshed original
  scaffold field for comparison. `build.py --policy` verifies model fingerprints
  and selects latest trusted-time intervals. Baseline bot copied unchanged to
  `snapshots/analysis_baseline_20261004`.
- 124 repository tests passed with CUDA enabled; all six competitor tests passed
  again after the final house-call correction. Harness now supports explicit
  opponent table lists and records per-player action/VPIP/PFR counters.
- Field evaluations launched: 400 duplicate tournament tables on GPUs 0/1
  (`field-harness.log`) and current Halliday plus its replica over the 43 latest
  observed eight-seat table compositions on GPUs 2/3 (`context-harness.log`).
  These are simulations on fresh duplicate deals, not exact replayed decks.
  Check live session state before treating these as finished or restarting.
- Observed-table comparison completed in `harness/results/20261004-014228.json`:
  43 eight-seat duplicate tables, 344 games per candidate, no failures.
  Current baseline +30.38 ±12.00 bb/100; Halliday replica +13.00 ±10.95 bb/100.
  Observed latest interval: -18.09 ±34.26 bb/100, fold89.70%, VPIP15.63%,
  PFR9.81%. Replica: fold89.13%, VPIP16.26%, PFR10.50%. Actual interval's
  30 all-ins were -1,027.8 chips below actual-hand expectation. Behavior is
  close; real win-rate fidelity remains uncertain, not established.
- Profiling shows CPU range/sampling work dominates the tiny CUDA ranking
  duration. Harness now supports explicit multiple workers per GPU while
  retaining default one per device. Round-robin assignment waits for every
  worker's startup. An 8-worker/4-GPU smoke passed all 40 games with no failures:
  `harness/results/20261004-014651.json` (each GPU used two distinct worker PIDs).
  This host exposes 16 CPU cores; do not oversubscribe during paired benchmarks.
- Seven isolated, unselected candidate copies now exist under
  `analysis/candidates`: river_guard, turn_discipline, shove_callers, mixed_35,
  mixed_65, value_pressure, small_ball. `analysis/build_variants.py` records the
  exact baseline hashes and parameter overrides. The shover variant preserves
  a cold caller's action-conditioned range and permits a call behind a known
  shover only with ranged equity above price; two focused tests passed.
  No variant has yet been performance-selected or substituted for bot/.

Remaining: quantify closed-loop fidelity, benchmark the original reference field,
improve harness coverage/scoring as needed, implement several separate Halliday
strategy variants including weighted randomness, perform held-out paired
benchmarks, and validate/package the selected bot under CPU submission limits.
No strategy improvements, exact deployment boundaries or tournament win
guarantees have yet been established for this new objective.


## Continued checks and strategy screens

- Merged newest `origin/main` commit f89e77f (documentation about rejected
  fold-more rules; no bot code changes). The connector returned 404 for PR7;
  `gh` has working repository credentials. PR7 remains open from
  analysis/gpu-harness into main. Current branch remains analysis/opponent-refresh.
- Full learned field completed: `harness/results/20261004-015231.json`, 400
  tables/1,970 games, +85.70 ±14.06 bb/100, round points 3.704 ±0.122, no failures.
  Original-reference field: `20261004-015019.json`, same table/deck seed,
  +28.73 ±4.97 bb/100, points 3.718 ±0.134, no failures. Model sensitivity is large.
- `analysis/fidelity.py` writes `analysis/reports/simulation-fidelity-20261004.md`
  and closed-loop-fidelity.json. Latest observed Halliday behavior matches fairly
  closely, but several opponent VPIP/PFR marginals differ. A chronological audit
  finds 134/301 opponent seats in those 43 games belong to earlier intervals.
  `analysis/create_fidelity_tables.py` prepared historical-interval-tables.json
  and generated ignored wrappers for a separate fidelity follow-up. Current-field
  benchmarks continue to use each identity's newest interval.
- Tuning A (`20261004-030355.json`): 96 tables, 3,904 games, eight candidates.
  Tuning B (`20261004-031150.json`): 96 tables, 3,776 games, eight candidates.
  Reference tuning (`20261004-031202.json`): 96 tables, 3,920 games, eight candidates.
  All completed without failures. A+B point gains are inconclusive: value_pressure
  +0.065±0.100, mixed_65 +0.052±0.107; stricter shover thresholds lose
  -5.52±3.90 bb/100. No strategy is selected or promoted yet.
  `analysis/summarize_benchmarks.py` audits duplicate rotations, zero-sum chips,
  hash consistency, paired intervals and family-adjusted intervals. Summaries
  are `tuning-ab-summary.json` and `tuning-reference-summary.json`.
- Four additional experiments: mixed_00, mixed_85, pressure_mixed_65,
  shove_ranges_only. The last isolates the range/cold-call fix without changing
  baseline shover thresholds. Builder accepts --only and never overwrites copies.
  Tuning C is running (session 82657): 160 tables, 5,565 games, baseline plus six
  alternatives on sixteen workers across all four GPUs; log strategy-tune-c.log.
- New `harness/tournament.py` reuses eval.py's worker/engine and implements
  four rounds with cumulative-point regrouping. Exact table allocation and
  authenticated roster unavailable: balanced tables nearest five, original
  seeded order for exact grouping ties, house excluded. Prize ties are explicitly
  unresolved rather than awarded without playoffs. Three scoring/grouping tests
  and a small actual four-round CPU smoke passed. Full field run still pending.
- New Linux `harness/resource_check.py` + limited_bot.py use real SDK subprocesses
  in a private user/mount/network namespace. Candidate has one CPU affinity,
  512MiB address-space ceiling, read-only chroot and fresh 64MiB tmpfs, actual
  30s+.1s/hand clocks. Initial launcher failures were corrected (mount namespace
  protections, remount semantics, actual SDK run_bot entry point). Baseline final
  check PASSED all three 100-hand games including eight seats and extreme styles:
  maximum cumulative action wait 4.56s, maximum RSS 39,372KiB, no verdict failures.
  Artifact baseline-resource-check.json. Selected candidate checks still pending.
- Documentation updated for shared GPU workers and richer models. Added
  opponent_model/fetch_validation.py to reproduce metadata caching (227 cached
  entries verified with zero new network requests); report generation no longer
  hardcodes current counts/date. Human dated report retains snapshot-specific API
  details; canonical result summaries regenerated from report data.

Next: finish tuning C; choose finalist(s) using tuning only and freeze selection
before fresh paired confirmation. Run eight-seat/reference/default-pool stress,
full four-round field simulations, historical-interval fidelity follow-up,
CPU-only candidate validation, package manifest/size checks, final tests/report,
then commit and create an analysis-branch PR. Do not claim a supported improvement
unless independent evidence warrants it; retaining baseline is valid if none does.

- Full CUDA-enabled suite passed **130 tests in 37.629s**. Later feature batching
  change passed all seven behavior tests and bitwise comparison on all 1,147,147
  rows in float32 and float64 (feature-batching-check.json). Profiling found
  repeated nan_to_num calls consumed substantial replica CPU time; cleaning the
  matrix once preserves predictions and avoids 43 per-column cleanups. No
  candidate logic or model weights changed. Ongoing confirmation workers retain
  their loaded modules; subsequent pools load the equivalent faster features.
- Tuning C completed: `harness/results/20261004-032501.json`, 160 tables,
  5,565 games, no failures. All deltas remain inconclusive. `mixed_65` was frozen
  as the sole finalist before independent confirmation (confirmation-plan.json):
  its point difference was positive in all three learned-field tuning seeds;
  combined 352-table point delta +0.0355±0.0813. No claim of superiority.
- Live independent confirmation session **69619**: baseline vs mixed_65,
  1,200 fresh tables /12,038 games, GPUs0/1/2 with12 workers, log
  strategy-confirm.log. Must finish the predeclared run; do not stop or change
  parameters based on intermediate results. Primary: paired round-point lower
  95% confidence bound must exceed zero to claim superiority. Do not promote
  an inconclusive candidate or one with material stress regressions.
- Historical-interval fidelity completed in `harness/results/20261004-033206.json`:
  43 tables, 688 games, no failures. Halliday replica -3.49±11.28 bb/100,
  current baseline +24.66±9.66. Opponent marginal discrepancies improved:
  testQ real47.17%VPIP vs newest23.31% vs historical44.82%; preflop-warrior
  real25.75% vs newest42.82% vs historical25.81%. Results use different fresh
  deck seeds from the prior fidelity run, so not a causal paired comparison.
  Full report regenerated with these findings in simulation-fidelity-20261004.md.
- Live four-round tournament session **35500**: twenty repeats for baseline
  and mixed_65, 76 entrants each, 4 rounds,12,160 games total on GPU3/four workers.
  Log four-round-confirm.log, output four-round-confirm.json. Reuses eval.py,
  retains unresolved final prize ties, uses equal observed-identity roster.
- Restricted mixed_65 CPU check passed nine100-hand games, zero failures,
  maximum action wait4.884s. Baseline3games also passed. Artifacts
  mixed65-resource-check.json and baseline-resource-check.json include memory,
  read-only mount and fresh tmpfs evidence. Both submitted-code hashes remain
  unchanged: current bot/baseline8015e4b3, mixed65f1abf214.
- Packaged both verified sources; archive integrity, rootmain.py, content hashes,
  safe paths, <=300files and <=20MiB unpacked all pass (package-checks.json).
  Baseline dist/submission-20261004-033009-8015e4b3.zip:12files106111bytes.
  Finalist dist/submission-20261004-033009-f1abf214.zip:13files107330bytes.
  Candidate package is experimental, not evidence of improvement.
- Preliminary strategy report: analysis/reports/strategy-benchmarks-20261004.md.
  Its final section explicitly awaits confirmation/tournament/stress results.
  Do not leave this pending placeholder in the final committed report.

Still required after live runs: default/reference/eight-seat stress for frozen
finalist, primary decision, final result summaries and audit of tournament
rotations/scoring/zero-sum, finish report and plan, commit/PR. Stronger default
pool is particularly important given main's newly documented fold-more failures.

- Independent table confirmation COMPLETED: `harness/results/20261004-035621.json`,
  1,200 paired tables /12,038 games, no failures. The predeclared primary FAILED:
  mixed65 round-point delta -0.04958 ±0.04265, chip delta -1.4737 ±1.5227 bb/100,
  game-point delta -0.01610 ±0.01684. Keep the failed primary visible. Baseline
  +73.979±6.613bb/100; mixed65 +72.506±6.628. Summary confirmation-summary.json.
- Original full tournament study COMPLETED: four-round-confirm.json,20 seeds per
  candidate,40 tournaments,12,160 games. Independent verify_tournament.py checks
  full candidate/event grid, rotations, zero-sum, all points and regrouping;
  PASSED (four-round-verification.json). Baseline meanrank17.925±5.838, placement
  14.775±.909, definite top3 3/20 (possible4/20). Mixed65 meanrank13.15±5.628,
  placement16.225±1.257, definite/possible top3 8/20. Paired placement delta
  +1.45±1.231, rankdelta -4.775±5.848. This conflicts with the random-table test;
  do not promote or selectively report only the favorable format.
- NEW predeclared follow-up: tournament-replication-plan.json freezes40 fresh
  event seeds (four-round-replication-20261004), same unmodified two bots and
  model, primary paired cumulative four-round placement points. This is an
  independent replication of a newly discovered format-specific hypothesis,
  not retroactive replacement of the failed original primary test.
- Tournament CLI now accepts --repeat-start to shard the fixed40 event indices.
  A real nonzero-offset CPU smoke passed and its independent verifier passed.
  First10 event seeds are LIVE on GPUs0/1,six workers, session12726:
  tournament-replication-00-09.log -> tournament-replication-00-09.json.
  Remaining30 seeds (repeat-start10,repeats30) MUST still be launched when
  resources free; same seed string. Aim16 totalCPU workers maximum.
- Stress tests (predeclared in stress-plan.json, only worker/device scheduling
  adjusted after both original runs ended): reference200tables COMPLETE,
  harness/results/20261004-040411.json,2,006 games,no failures, summary
  reference-confirm-summary.json. Eight-seat128tables/2,048 games LIVE session
  31042 on GPUs2/3,six workers (eight-seat-confirm.log). CPU default128tables/
  1,268 games LIVE session88237,four workers (default-confirm.log).
- Added analysis/README.md, versioned compact Halliday blunders/match-review CSVs,
  verify_tournament.py; published report source remains reproducible. Whole
  action-classification CSV(5MiB) and raw data remain local ignored artifacts.
- Live session41153 (first verification command) finished and polled. A later
  rerun verification command may have a new handle; inspect most recent tool
  output. Original full test130 and post-feature-batching behavior7 all passed.

Remaining: complete stress runs, finish all40 fresh tournament repetitions,
interpret conflicting evidence without changing frozen candidates, finalize
reports/evidence/selection, ensure all tests/source/package checks still apply,
then commit and createPR on analysis/opponent-refresh. Current bot/ remains
unmodified (other than merged main documentation); no candidate promoted yet.

- All three fixed stress tests COMPLETE without failures. Original model:
  200tables/2,006games, delta roundpoints -0.0725±0.0841, chips -0.289±1.748bb/100.
  Eight seats:128tables/2,048games, result20261004-040835.json, delta roundpoints
  +0.0547±0.1750, chips -0.951±2.673bb/100. CPUdefault:128tables/1,268games,
  result20261004-041016.json, delta roundpoints +0.0078±0.0474, chips
  -0.772±2.990bb/100. None confirms superiority; neither stress run resolves
  the conflict between average random tables and the first full-tournament study.
- Fresh tournament replication uses THREE disjoint shards under the same seed
  four-round-replication-20261004, frozen before new outcomes:
  * 00–09 COMPLETE,20tournaments/6,080games, verifierpassed. No performance
    interpretation until all40 seeds finish. File tournament-replication-00-09.json.
  * 10–19 LIVE session90550 on GPUs2/3,sixworkers; same filename prefix/log.
  * 20–39 LIVE session95160 on GPUs0/1,tenworkers; same filename prefix/log.
  Both running pools total16CPU workers. All40 seeds must finish and be combined
  with duplicate-event/grid checks. Do not restart any live session based on ETA.
- All other sessions mentioned earlier are terminal and polled. New combined
  table result summaries are reference-confirm-summary.json,
  eight-seat-confirm-summary.json and default-confirm-summary.json.
- analysis/verify_tournament.py now verifies the complete candidate/event grid,
  source-spec consistency and every scoring/regrouping step independently.
  Original40-tournament verification passed again with those stronger checks.
- Full prior study's placement advantage arose after regrouping: paired per-round
  differences +.075,+.45,+.70,+.225 points (each individual interval includes0).
  This is a reason to replicate the format-specific hypothesis, not evidence
  to reverse the failed primary-table test or pick another metric retroactively.

Next actions: poll90550/95160; audit and combine all40 fresh seeds (24320games),
report paired cumulative placement/rank and definite/possible top-three rates
with event-level uncertainty. Interpret all evidence, retain baseline if no
replicated improvement, finalize strategy report/evidence and completion audit,
check final tests/package hashes, commit and create an analysis-branchPR.


## Final evidence and main integration (supersedes earlier live-session notes)

- All initial confirmation, stress and four-round replication jobs are complete.
  The 65% bluff variant failed its independent 1,200-table primary test
  (round-point delta -0.04958 +/-0.04265) and did not repeat its initial
  tournament gain: 40 fresh events gave -0.3875 +/-0.8225 cumulative points,
  bootstrap interval [-1.2,0.4375]. Reject this variant; do not promote it.
- All four tournament artifacts passed independent scoring/accounting checks.
  The completed study through this replication totals 76,321 full games.
- A fixed 192-table exploratory screen now tests field mean/median priors,
  faster adaptation and the existing isolated shove-range fix. Plan is saved
  before outcomes in field-priors-plan.json. Session61509, 16 workers on all
  four GPUs. Only a positive family-adjusted point interval justifies a new
  independent test. No candidate has been promoted.
- Main advanced to6cfdf0f and was merged as bffe87b. It adds OOP short-table
  c-bets, limped-flop bets and small-blind steals. Preserve the old research
  baseline8015e4b3; newly merged main is separately frozen as
  snapshots/analysis_main_20261004, hashbb2090c7. Its fresh 400-table paired
  evaluation is predeclared in main-integration-plan.json, awaiting workers.
- Latest user replay audit is complete and matches the unchanged snapshot SHA.
  Human report and compact CSVs are in analysis/reports. Remaining work:
  finish these two screens, refresh main CPU/package checks and integration
  tests, export compact evidence, finalize reports, commit/push and createPR.
