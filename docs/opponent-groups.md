# Opponent-group experiment

Branch: `feat/opponent-groups`, starting at main `6cfdf0f44b332933d88d440791e7151028061849`.
The experiment ran 10,000 matched games per policy (40,000 executions and
4,000,000 hands). No player failed. Grouping did not establish an improvement
over either base: -0.82 bb/100 on calibration (95% interval -2.03 to +0.45),
and -0.64 on main (-1.77 to +0.52). Keep the group variants experimental.

The [report](../analysis/reports/opponent-groups-20261004.md) contains return and
placement comparisons, fold/call reviews, a SWOT analysis and figures. The
171-test four-policy suite, eight focused report/reproduction checks, both
restricted-process bot checks and all four V100 audit workers passed.

The main-based candidate retains main's call behavior. An alternative on
`feat/opponent-groups-call-calibration` starts from `feat/call-calibration` and
retains its terminal-call corrections and 0.06 river margin. Both use identical
group counter adjustments relative to their own baseline. Comparing all four
policies distinguishes the grouping effect from the calibration effect.

## Required outcome and evidence

- Freeze the current input snapshot and refit each newest submission's parameters,
  uncertainty and covariance. Every timestamped validation against `house:call`
  starts a version; newest data has weight one. Sparse contexts may borrow older
  observations with both version-age and upload-time discounts. Record coverage.
- Derive a small set of groups with observable behavioral signatures and a
  distinct counter-strategy for each. Account for variation within groups and
  uncertain/sparse opponent fits. Export compact constants in the submission.
- Classify anonymous opponents online from public actions and revealed showdowns.
  No names, hidden cards, future observations, filesystem writes or cross-game
  state. Use lightweight per-player statistics within the 100-hand game.
- Blend counter-strategies by calibrated confidence, retain a baseline fallback,
  and measure how early grouping is reliable. High aggression alone does not
  establish bluffing; policy changes alone do not establish opponent adaptation.
- Evaluate bluff defense and bounded strategic variation against adaptive styles,
  including targeted tests. Random variation must preserve legal actions and
  strong value decisions, and must not expose private random seeds to opponents.
- Validate classification on held-out game prefixes, legal-event replay and
  meaningful strategy regressions; measure bot CPU/memory/protocol compliance.
- Compare main, `feat/call-calibration`, and grouping on both bases on at least 10,000
  matched games per version. Use grouping without targeted counters as a pilot
  ablation, and run the final versions on
  matched deals and seat rotations against the refreshed replicas. Select any
  settings on a separate pilot, then freeze a held-out comparison. Report chip
  return, tournament placement, uncertainty, identification speed, remaining
  weaknesses, visualizations and exact reproduction commands.

## Runtime constraints

The submission supports Python standard library plus NumPy, a 30-second bank
plus 100 ms per hand, and no background computation. A fresh process starts each
game, even for repeated opponents in a tournament round. Classification therefore
resets per game. Offline fitting may use PyTorch and the four V100s; the deployed
classifier must not need a GPU, neural runtime, opponent catalogue or network.

## Reproduction

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 OPPONENT_CUDA_MEMORY_MIB=512 \
  .venv-estimators/bin/python -B -u analysis/run_opponent_groups.py --stage refit
```

Full commands are in
[the reproduction guide](../analysis/reports/opponent-groups-20261004-reproduce.md).
The input is frozen separately under `analysis/results/opponent-groups-20261004/input`.
Previous study inputs and reports remain unchanged. The 512 MiB tensor-allocation
limit leaves room for CUDA contexts within the roughly 1 GiB free on each shared
V100. A matched benchmark selected 16 CPU simulation workers while the V100s
were heavily used by another process. All four GPUs perform fitting and the
independent decision audit.
