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

## GPU workers

Field evaluations and A/B runs default to `--device auto`: when a compatible bot,
NVIDIA driver, CUDA toolkit (`nvcc`) and NumPy are available, the harness starts
one spawned worker per visible GPU. Each worker batches the updated Halliday
engine's seven-card hand rankings on its GPU. Range sampling, weighted aggregation,
the game loop, and opponent decisions run on CPU. Older snapshots and opponents
without the batch hook continue using their own evaluators.

```sh
# Automatically use available GPUs, or fall back to CPU workers.
python harness/eval.py run bot --no-league --pool sparring/competitors/from_data/pool.txt

# Require all four devices; startup failures are errors in explicit CUDA mode.
python harness/eval.py run bot --no-league --pool sparring/competitors/from_data/pool.txt --device cuda --gpu-devices 0,1,2,3

# Limit GPU use, or select the CPU reference path.
python harness/eval.py run bot --no-league --gpu-workers 2 --gpu-batch-size 128
python harness/eval.py run bot --no-league --device cpu --workers 8
```

`--gpu-devices` uses indices reported by the CUDA driver (respecting
`CUDA_VISIBLE_DEVICES`). By default one worker uses each GPU. `--gpu-workers N`
can also share devices round-robin: `--gpu-devices 0,1,2,3 --gpu-workers 16`
uses four processes per GPU. Choose this only when CPU cores and GPU memory
permit; each process has its own CUDA context (about 308 MiB on the tested V100).
A count below the device count selects the first N devices.
`--workers` controls CPU execution and
fallback. `--gpu-batch-size` accepts 1–4096 deals, default 128. At the default,
each worker allocates 36 KiB of device input/output buffers plus CUDA context
overhead; memory is independent of the number of tables. Workers are independent
and do not pool GPU memory or require NVLink transfers.

The CUDA kernel is compiled to a native binary for the device architecture and
cached in `harness/results/cuda-cache/`. Find `nvcc` through PATH, `CUDA_PATH`, or
`/usr/local/cuda`. No additional CUDA Python package is required. Every worker
compiles/loads and checks its kernel before game clocks start. Auto mode falls
back to CPU if detection or startup fails, with a reason in the output and saved
JSON. Errors after play begins remain failures rather than silently changing
the backend midway through a run.

Output and the JSON `compute` field record selected devices, worker startup,
and actual per-device batch and ranked-hand counts. `gpu_seconds` measures host
elapsed time for transfers, kernel launch and synchronization, not pure kernel
time. There is no guaranteed speedup for small batches or workloads dominated
by game logic; see [local validation](GPU_VALIDATION.md).

Promotion gates always use CPU in auto mode, and reject explicit CUDA. GPU timing
does not establish that a submission meets tournament CPU clocks. Timed equity
calls can complete different sample counts on different backends, and finish a
pending batch when their cooperative deadline expires. Use a CPU gate and
`smoke` before promotion or packaging. `--device cpu --workers 1` also preserves
single-process debugging with bot print output.

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

### Fitted competitors

`sparring/competitors/from_data/pool.txt` contains the latest fitted segments for 76
external identities; the historical Halliday fit is also available separately.
See [the competitor documentation](../sparring/competitors/README.md) for
provenance, uncertainties, regeneration and the field evaluation command.
File bots may expose `make_seeded_bot(seed)` to receive the harness's per-seat
seed; otherwise the existing no-argument constructor behavior is unchanged.

Use `--tables-json FILE` for a JSON list of ordered opponent-spec lists. This
overrides random table selection and makes observed lineup comparisons possible.
Fresh duplicate decks are still used. Results also retain per-player action,
VPIP and preflop-raise hand counts to assess behavioral simulation fidelity.

## Four-round simulations and submission limits

```sh
python harness/tournament.py snapshots/analysis_baseline_20261004 analysis/candidates/value_pressure --repeats 20 --device cuda --gpu-workers 16 --output harness/results/four-round.json
python harness/resource_check.py analysis/candidates/value_pressure --repeats 3 --output harness/results/cpu-resources.json
```

`tournament.py` reuses the engine and worker pool from `eval.py`, following the
[documented round scoring](https://docs.poker.monashcoding.com/game-format/scoring/). It scores each
duplicate set, then regroups by cumulative placement points with total game
points breaking regrouping ties. It assumes balanced tables nearest five seats
and an entrant for every observed external display identity, excluding the
validation house bot. This is not an authenticated final roster. Exact grouping
ties use initial seeded ordering. Final prize ties are retained as unresolved;
the organizers' playoff procedure must determine prizes. Per-event results
retain all rounds, entrants, standings and games. Use `--repeat-start` with
disjoint event-index ranges to distribute a fixed-seed study across separate
pools; event seeds and initial lineups are independent of shard boundaries.

`resource_check.py` runs real SDK subprocess games on Linux. The candidate has
one CPU affinity, a 512 MiB address-space ceiling, a read-only chroot, a fresh
64 MiB tmpfs per game and a private network namespace, with the real 30 s plus
0.1 s/hand clock. It requires unprivileged user namespaces and mount support.
It checks a cooperative bot's resource use; it is not a hardened security judge.
The launcher and replicas are offline tools, not submission contents.

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
- Workers discard bot `print()` output. Use `--device cpu --workers 1` to see prints while debugging.
- A failing game raises `RuntimeError: game failed: candidate=... opponents=... table=...
  game=... seed=...` with the full traceback, so it can be replayed with `--seed`.
