# Opponent refresh and Halliday research — 4 October 2026

## New-data rerun completed

The [latest-segment report](reports/latest-analysis-20261004-r2.md) supersedes
the replay and field counts below for the current upload. It uses exact main
`6cfdf0f` (harness hash `26121bc2`), 65 reliably dated latest opponent intervals,
and 44 observed games where every seat belongs to its newest interval. The
rerun completed 5,118 simulation games, nine restricted CPU games and 144 tests.
Four V100s performed model fitting and replay scoring; the unmodified main
engine used 12 CPU simulation workers. No strategy was changed or promoted.
[Commands and frozen-input requirements](reports/reproduce-latest-20261004-r2.md)
reproduce this rerun. The earlier experimental study remains below as history;
its merged-main snapshot included the analysis branch's GPU engine hook.

## Earlier completed research

The requested analysis, replica refresh, strategy experiments, tournament
simulations and resource checks are complete. The objective of establishing a
stronger strategy remains unmet: none of eighteen isolated experimental variants
qualified for promotion. Retain the current bot inherited from main. This is a
research outcome, not proof of optimality or of superiority against real bots.
No simulation jobs are still running.

## Completed evidence

1. Frozen input: actions SHA-256
   `10331deef87e5cacb4e09ac79c5ebe2d4aeb4ff477b153d20cdb7de8fbd01d9a`.
   All 143 Halliday matches, 14,006 hands and 17,865 decisions reconcile.
   The primary replay report covers 140 ladder games and reviews all 75 losses.
2. Four V100s refreshed estimates for 77 observed identities. Whole-match
   held-out tests compare the original scaffold and four public-context models.
   Upload intervals improve prediction, but validation proves an upload rather
   than deployment. Unknown times and failed validations do not create epochs.
3. Latest-interval replicas are separate in `sparring/competitors/from_data`.
   Historical-version lineups were also tested to measure simulation mismatch.
   Hidden opponent cards and historical profiles are excluded from the bot.
4. Eighteen isolated variants cover river/turn caution, shove ranges, value and
   bluff sizes, weighted bluff frequencies, priors, adaptation and small opens.
   Tuning, independent confirmation, stress and four-round event results are
   preserved, including failed replication. No variant has established a gain.
5. Main `6cfdf0f` was merged and preserved as snapshot `bb2090c7`. Its separate
   400-table comparison was inconclusive. Production `bot/` retains this source.
6. Total completed simulation study: 103,027 full 100-hand games, zero player
   failures, plus 18 restricted CPU games and separate smoke checks.
7. Current main passed one-core, 512 MiB, read-only filesystem, fresh 64 MiB
   `/tmp`, and actual 30 s + 0.1 s/hand protocol checks. Peak RSS was 38.55 MiB;
   cumulative action wait at most 3.550 s. Its verified ZIP is 109,778 bytes
   unpacked, with no analysis data or GPU dependency.
8. GPU scheduling supports concurrent workers per device when VRAM permits.
   The final 140-test CUDA suite passed without skips. Scalar inference features
   equal the unchanged batch calculation on all 1,147,147 observations in both
   float32 and float64. SDK/harness sibling module isolation has a regression.

## Final follow-up outcomes

- Adaptive steals, 65% participation and cutoff widening: 256 tables / 5,172
  games. None passed its family-adjusted round-point selection rule.
- Additional-open diagnosis: 128 fresh tables / 645 games, 594 extra opens,
  +1.434 chips per open versus folding in those same hands, table-bootstrap
  interval [0.053, 2.859]. This excludes later adaptation and tournament points.
- Minimum-size added steals (`03e75b3e`): frozen 1,200 tables / 12,078 games.
  Paired round points +0.02417 ± 0.04310, interval crosses zero. The conditional
  1,000-table replication was not triggered. Three restricted CPU games passed;
  the candidate remains unselected and is not the recommended submission.

Frozen plans, source hashes, uncertainty, complete-table summaries and checks
are in `analysis/reports/evidence/20261004`. Large replay/game traces remain in
ignored local results. `analysis/export_evidence.py` reproduces the compact
bundle. `analysis/README.md` links the human reports and reproduction commands.
Publication uses `analysis/opponent-refresh` and existing PR #9.

## Limits on conclusions

The reconstructed field does not fully reproduce real Halliday returns. Better
held-out action prediction and historical version matching improve fidelity,
but opponent-model error remains outside simulation confidence intervals. The
replay's largest calling flags describe older play; none occurs in its latest
20 ladder games. Blindly applying those historical fixes to current source did
not establish a gain. A claim that Halliday now beats every bot is unsupported.
