# Fixed baseline validation

Tested 3 October 2026 on Windows, Python 3.12.13, using the vendored SDK.
Branch: `codex/baseline-strategy`, based on local `feat/odds-calc` at
`d8c1a2c7659c48278abb90ff746a09cc760f09f6` (including its harness merge).
Candidate content hash: **`3b8824f8`**. Engine source is unchanged.

## Correctness and protocol

- **43 tests passed:** original engine checks plus 19 strategy tests.
- Strategy coverage includes all 169 preflop classes, rotated positions and
  heads-up blinds; openings, reraises, blind defence, large bets; postflop
  calls/folds/value bets; short all-ins and closed raising; current-street
  pot eligibility; draws and royal-board splits; minimum sample counts,
  low clock and unavailable estimates; seeded observations independent of
  identities and previous hands; no input or global RNG mutation.
- An audited SDK hand runner checked raw bot actions **before** the engine
  could coerce them, over 80 hands at 2, 4, 6 and 9 seats. All raises were
  allowed and within bounds; checks/calls/folds matched the outstanding bet.
- **Subprocess smoke passed:** two five-player duplicate sets, 10 games of
  100 hands, all `OK`. The first lineup used call/random/station/tag; the
  second allin/checkfold/maniac/nit. Seed: `baseline-v1-smoke`.
- Submission packaging succeeded with `main.py` at the root alongside
  `engine.py`, `params.py`, `preflop.py` and `strategy.py`; no bytecode.

## Paired performance

Each seed drew 40 independent random tables with 4-6 seats from the default
pool, including jittered archetypes and league opponents. Each table used
one duplicate game per seat, 100 hands per game, and two workers. Candidate
and reference used the same tables, seats and decks. Parameters were not
tuned between the two runs.

The only league reference was `snapshots/v0`, hash `5e70a912`, the original
scaffold. Its decisions are the same pot-odds-only rule previously retained
by `feat/odds-calc`; it does not spend time on unused equity diagnostics.

All units below are **big blinds per hand**, converted from the harness's
milli-big-blind output. Intervals are the harness's approximate 95% intervals
over independent tables; the improvement interval uses paired differences.

| Metric | `baseline-v1-a` | `baseline-v1-b` |
|---|---:|---:|
| Games, both versions | 406 | 408 |
| Hands, both versions | 40,600 | 40,800 |
| Scaffold bb/hand | -2.329 +/- 0.725 | -2.061 +/- 0.794 |
| Baseline bb/hand | +2.357 +/- 0.609 | +2.057 +/- 0.527 |
| Paired improvement bb/hand | **+4.686 +/- 1.077** | **+4.118 +/- 1.048** |
| Paired round-point improvement | +2.35 +/- 0.36 | +2.01 +/- 0.38 |
| Candidate TLE/RTE/PV games | 0 | 0 |
| Slowest candidate decision | 31.96 ms | 36.04 ms |
| Maximum candidate clock consumption | 5.12% | 4.54% |
| Harness verdict | **GATE PASS** | **GATE PASS** |

Total: 814 in-process games / 81,400 hands across both versions, including
407 candidate games / 40,700 candidate hands, plus the subprocess smoke above.
Local raw results (gitignored):

- `harness/results/20261003-005257.json`
- `harness/results/20261003-005619.json`

The raw runs record `d8c1a2c+dirty` because validation preceded the baseline
commit; both record the candidate content hash above. Reproduction commands
are in [BASELINE.md](../bot/BASELINE.md).

## Interpretation and next comparisons

This establishes a working fixed baseline that improves substantially on
the scaffold in the local pool. It is a smaller check than the harness's
default 400-table gate and does not establish tournament or equilibrium
strength. Opponent-present breakdowns describe mixed tables, not isolated
head-to-head wins over each named opponent. No league promotion or merge
was performed by these checks.

For subsequent improvements, compare against this fixed code on reserved
seeds and new opponent mixtures. Useful next experiments are fixed
action-conditioned ranges, precision near decision thresholds, and side-pot
chip EV before adding cross-hand adaptation. The current model uses uniform
unknown opponent cards; its pressure margins are only heuristics.
