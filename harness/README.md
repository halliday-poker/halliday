# Evaluation harness

Scores bot versions against a pool of opponents at random 4-6 seat tables, using the
tournament's engine and duplicate format. Run everything from the repo root with the venv
Python (`.venv/Scripts/python` on Windows, `.venv/bin/python` elsewhere).

## Everyday loop

```sh
# ...edit bot/...
python harness/eval.py run bot                     # gate: must beat each of the last 3 league versions
python harness/eval.py promote v4 --note "wider BTN opens"   # only after GATE PASS
python harness/eval.py smoke bot                   # before every upload: real subprocesses
python harness/eval.py package                     # dist/submission-<time>-<hash>.zip
```

Commit `snapshots/` and `harness/league.json` after a promotion so the whole team gates
against the same league.

## The gate: `run` with one candidate

```sh
python harness/eval.py run bot [--tables 400] [--seed S] [--league 3]
```

- The last 3 promoted versions (`harness/league.json`) become **baselines** and also join the
  **opponent pool**. Every bot plays the identical tables, cards and opponents from the same
  seat, so each comparison is paired and low noise.
- The candidate must be **significantly better than each one**. With 3 baselines each interval
  is widened to 98.3%, keeping the overall chance of a false pass at 5%.
- Verdicts:

  | Verdict | When |
  |---|---|
  | `FAIL` | Any TLE/RTE/PV game, clock use above `--max-bank` (50%), identical to a league version, or significantly worse than any. |
  | `PASS` | Significantly better than every league version. |
  | `INCONCLUSIVE` | Otherwise. The run **extends automatically**: 400 → 800 → 1600 tables (`--max-tables`), each on a fresh seed. |

- Each gate gets a fresh seed by default, so nobody tunes against one gate's cards.
- Exit code 0 only on PASS, so the gate can be scripted.

## The league: `promote`

```sh
python harness/eval.py promote v4 --note "what changed"
```

- Freezes `bot/` into `snapshots/v4/` and appends it to `harness/league.json` with its hash,
  commit, note and the gate run that justified it.
- Refuses unless the latest gate run **for this exact code** (content hash) passed, and was
  run against the **current** league. If a teammate promoted in between, re-run the gate.
- `--force` promotes anyway and records `"forced": true`. Use it only for bootstrapping.
  `v0` (the scaffold template) is the bootstrap entry.

## Plain A/B: `run` with several candidates

```sh
python harness/eval.py run snapshots/v3 bot [more...]     # first = baseline, 95% intervals
python harness/eval.py run A B --no-league                 # without league opponents
```

## The opponent pool

[pools/default.txt](pools/default.txt) lists bot specs with weights. A spec is a bot directory
(`snapshots/v2`), a `.py` file, `house:<name>`, or `param:<archetype>`. `run` adds the league
versions automatically, and `--add` puts extra opponents in for one run.

### Adjustable opponents (`sparring/param.py`)

One bot with a style vector: `vpip, pfr, threebet, limp, aggression, cbet, bluff,
stickiness, size`, plus an `adaptive` flag that adjusts to opponents' aggression and folding.

- `param:random` in the pool fills each seat it draws with a **random archetype** (nit, tag,
  lag, station, maniac, adaptive), with every number **jittered ±20%**. The style comes from
  the table seed, so every candidate meets the identical opponent. It is weighted so about half
  of each table is randomised.
- `param:lag` and similar specs are exact archetype centres, for targeted tests:
  `run bot --no-league --pool <file with param:station>` or `run param:tag param:lag --no-league`.
- Preflop it plays hands by percentile rank (Chen formula, small pairs adjusted). Postflop it
  uses a fast made-hand plus draw heuristic, a few ms per decision.
- Each run's JSON records the drawn styles under `param_styles`.

## Reading the output

| Column | Meaning |
|---|---|
| mbb/hand | Chip winnings per hand in milli big blinds, +- 95% CI over tables. Main metric, lowest noise. |
| game pts | Average tournament game points (n for 1st down to 1 for last) per game. |
| round pts | Average round placement points per table: what the tournament actually sums. |
| 1st % | Share of tables where we won the round. |
| max ms / bank | Slowest single decision, and the most of the clock (30 s + 0.1 s per hand) used in any game. In-process timing on a busy machine is pessimistic. |
| verdicts | Games ending in TLE/RTE/PV. The first crash traceback is printed below the tables. |

Below that are breakdowns by table size and by **opponent present**. Randomised opponents are
grouped by archetype (`param:lag`, ...), which shows which styles a version struggles against.

Every run is saved to `harness/results/<time>.json` (every game's chips, verdicts and timing,
plus the gate verdict) and appended to `harness/results/log.csv`. Both are gitignored and
local to each machine.

## Other commands

- `smoke [bot]`: plays the bot as a real subprocess over the wire protocol, exactly as the
  tournament runs it, in two lineups (no shove bots, so hands reach the river; then the all-in
  and check-fold extremes). Prints `SMOKE PASS` only if every game ends `OK`.
- `snapshot NAME`: freezes `bot/` into `snapshots/NAME/` **without** adding it to the league.
  Useful for ad-hoc A/B tests.
- `package [dir]`: zips a bot directory for upload.

## Pitfalls

- **Import sibling modules at the top of main.py**, not inside functions. The harness gives
  each bot version its own copy of its sibling modules (so `snapshots/v2/engine.py` and
  `bot/engine.py` can share a table). That only works for top-level imports.
- Bots are loaded once per worker and get a fresh instance per game. Module-level mutable
  state therefore leaks between games here but not in the tournament. Keep state on `self`.
- Workers discard bot `print()` output. Use `--workers 1` to see prints while debugging.
- A failing game raises `RuntimeError: game failed: candidate=... opponents=... table=...
  game=... seed=...` with the full traceback, so it can be replayed with `--seed`.
