# Evaluation harness

Scores bot versions against a pool of opponents at random 4-6 seat tables, using the
tournament's engine and duplicate format. Run everything from the repo root with the venv
Python (`.venv/Scripts/python` on Windows, `.venv/bin/python` elsewhere).

## Everyday loop

```sh
python harness/eval.py snapshot v3                 # freeze the current bot/ as snapshots/v3/
# ...edit bot/...
python harness/eval.py run snapshots/v3 bot        # is the edit better than v3?
python harness/eval.py smoke bot                   # before every upload: real subprocesses
python harness/eval.py package                     # dist/submission-<time>-<hash>.zip
```

## `run`

```sh
python harness/eval.py run BASELINE [CANDIDATE ...] [--tables 200] [--seed eval] [--label "note"]
```

- Draws `--tables` random tables. Each one has a seat count from `--sizes` (default `4,5,5,6`;
  repeat a number to weight it) and opponents drawn by weight from `--pool`
  (default [pools/default.txt](pools/default.txt)). `--add` puts extra opponents in the pool for one run.
- Each table plays a full duplicate set: one game per seat, same decks, seats shifted each game.
- **Every candidate plays the identical tables, cards and opponents from the same slot.**
  The paired comparison against the first candidate (the baseline) is therefore low noise.
  Trust the `BETTER` / `WORSE` call, which needs the 95% interval to exclude zero, over the
  raw numbers.
- Speed: about 200 tables x 2 candidates in 20 s on 15 workers with simple bots. Slower bots
  scale with their think time.

Output columns:

| Column | Meaning |
|---|---|
| mbb/hand | Chip winnings per hand in milli big blinds, +- 95% CI over tables. Main metric, lowest noise. |
| game pts | Average tournament game points (n for 1st down to 1 for last) per game. |
| round pts | Average round placement points per table: what the tournament actually sums. |
| 1st % | Share of tables where we won the round. |
| max ms / bank | Slowest single decision, and the most of the clock (30 s + 0.1 s per hand) used in any game. In-process timing on a busy machine is pessimistic; still keep bank well under 100%. |
| verdicts | Games ending in TLE/RTE/PV. The first crash traceback is printed below the tables. |

Below that are breakdowns by table size and by **opponent present**: our mbb/hand averaged
over tables containing that opponent. This shows which opponent types we fail to exploit.

Every run is saved to `harness/results/<time>.json` (every game's chips, verdicts and timing)
and appended as one row per candidate to `harness/results/log.csv`, with the git commit and a
content hash of the bot directory, so uncommitted versions are still identifiable.

## `smoke`

Plays the bot as a real subprocess over the wire protocol, exactly as the tournament runs it,
in two lineups: one without shove bots so hands reach the river, one with the all-in and
check-fold extremes. Prints `SMOKE PASS` only if every game ends `OK`.

## Pitfalls

- **Change the seed before believing a result.** Iterate with a pinned `--seed`, then confirm
  with a fresh one. Tuning many parameters against one seed overfits to those cards.
- **Import sibling modules at the top of main.py**, not inside functions. The harness gives
  each bot version its own copy of its sibling modules (so `snapshots/v2/engine.py` and
  `bot/engine.py` can share a table). That only works for top-level imports.
- Bots are loaded once per worker and get a fresh instance per game. Module-level mutable
  state therefore leaks between games here but not in the tournament. Keep state on `self`.
- Workers discard bot `print()` output. Use `--workers 1` to see prints while debugging.
- Opponent pool: add `snapshots/vN` and new sparring bots to the pool as they appear. The
  default sparring bots are simple stereotypes (nit, station, maniac, tag); beating them is
  necessary, not sufficient.
