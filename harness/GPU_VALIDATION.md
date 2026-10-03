# CUDA harness validation

The second October 4 upload was checked with **144 passing CUDA-enabled tests**.
Its exact main snapshot `26121bc2` has no batching hook, so its field and
tournament simulations correctly select CPU. The tournament driver now uses
the same compatibility preflight as `eval.py`; GPU contexts alone do not count
as acceleration. Four V100s fit the models and execute the separate replay
audit. See [current evidence](../analysis/reports/evidence/20261004-r2/index.json).

Validated on 3 October 2026 with Python 3.12.14, NumPy 2.3.5, CUDA toolkit
12.8 and four Tesla V100-SXM2-16GB devices. Each device initially had about
1,089 MiB free alongside existing workloads. The harness uses a native `sm_70`
kernel through the CUDA driver API; it does not load PyTorch in game workers.

## Correctness and fallback

All 110 repository tests passed with CUDA enabled (17.2 seconds, no skips):

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B -m unittest discover -s tests -v
```

The CUDA tests compare 10,010 random and edge-case seven-card hands against the
independent SDK evaluator, including wheels, straight flushes, double trips and
three pairs. Complete equity reports match the CPU engine exactly with fixed
seeds on every street, with one, four and eight opponents, and for weighted
rejection sampling and exact enumeration.

Tests also cover pending batches at deadlines, invalid input, actual CUDA work
through the harness loader, device selection, CPU-only execution, unavailable
CUDA, worker startup failure and interrupt cleanup. Auto mode falls back before
games start; explicit CUDA mode fails clearly. Promotion gates select CPU.

A separate 12-table comparison ran the same seed on four GPU workers and four
CPU workers. All 62 games had identical chip totals and verdicts. GPU work
totalled 3,028,224 seven-card rankings across 10,728 batches. The harness reported
9 seconds on GPU versus 8 seconds on CPU, excluding GPU startup. This small
workload establishes actual GPU execution and parity, not a speedup claim.

## Full fitted-field run

| Metric | Result |
|---|---:|
| Duplicate tables / games / hands | 400 / 2,005 / 200,500 |
| External identities encountered | 66, each on 14–36 tables |
| Winnings, milli big blinds per hand | +262.8 ± 50.4 (95% CI across tables) |
| First place in duplicate set | 36.5% |
| Candidate and opponent failures | 0 across 10,241 player-game verdicts |
| Harness wall time, excluding startup | 239 seconds |
| Wall time including startup and monitoring | 243 seconds |
| Sampled peak worker VRAM, including context | 308 MiB per GPU |

All four GPU workers were present concurrently. Memory monitoring sampled
`nvidia-smi` compute-process usage 444 times at roughly half-second intervals,
counting only these workers. Sampled worker memory remained within the available
1 GiB per-device budget. Recorded CUDA work was:

| Device | Games | Kernel batches | Seven-card hands ranked |
|---|---:|---:|---:|
| cuda:0 | 504 | 76,344 | 21,264,384 |
| cuda:1 | 491 | 76,758 | 21,487,872 |
| cuda:2 | 516 | 78,756 | 22,109,952 |
| cuda:3 | 494 | 78,192 | 21,945,600 |

The saved games have complete seat rotations and zero-sum chips. All 2,005
games' chip totals and verdicts match the earlier full CPU evaluation. The
winnings mean and interval were independently recomputed. GPU timings do not establish
a speedup: the earlier full CPU run used eight workers, and this run used four
GPU workers with active memory monitoring on a shared machine.

Reproduce from the repository root:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B -u harness/eval.py run bot --no-league --pool sparring/competitors/from_data/pool.txt --tables 400 --deals 100 --device auto --workers 4 --seed competitors-latest-20261003 --label latest-competitor-segments-cuda
```

`auto` selected four CUDA workers. The generated field uses the latest segment
for each of 66 external identities; see [competitor provenance](../sparring/competitors/README.md).
These are fitted surrogates. Their evaluation does not predict results against
the original bots or implement the tournament's cumulative-score regrouping.

GPU timing is unsuitable evidence for CPU submission clocks. Timed simulations
may complete different sample counts, and a pending batch finishes after a
cooperative deadline. The default batch size is 128 deals; device input/output
buffers use 36 KiB per worker, in addition to the CUDA context. Sampling and game
logic remain CPU work. Independent workers do not combine VRAM or use NVLink.

Local artifacts, intentionally ignored by Git:

- [Full field results](results/20261003-223151.json)
- [Game and scoring validation](results/competitors-latest-cuda-validation.json)
- [GPU memory measurements](results/competitors-latest-cuda-memory.json)
- [Run log](results/competitors-latest-cuda.log)
- [Full CUDA-enabled test log](results/gpu-harness-full-cuda-tests.log)
- Small comparison: [GPU](results/20261003-221801.json) and [CPU](results/20261003-222229.json)


## October 4 shared-worker extension

The refreshed model adds CPU inference work, so profiling and scheduling were
revisited. CUDA ranking accounted for about 18.6 seconds across the learned
400-table field run, compared with 863 seconds elapsed on two workers. CPU
range sampling, game logic and replica inference dominate. Shared GPU workers
therefore expose more CPU parallelism without changing equity kernels.

`--gpu-workers` now permits multiple processes per device. Its default remains
one per device. An eight-worker/four-V100 smoke completed all 40 games without
failures, with two distinct worker PIDs and nonzero ranking work on each GPU
(`harness/results/20261004-014651.json`). A later strategy screen ran sixteen
workers across all four V100s. Each process has its own CUDA context; four
workers per device exceed the original 1 GiB free-memory budget and were used
only after the hardware had been freed for this task. Explicit shared-worker
counts require enough free VRAM and CPU cores; NVLink does not pool their memory.

After the model, scheduling, behavior counters, resource launcher and four-round
scoring changes, **132 repository tests passed with CUDA enabled** in 49.3 seconds after the
latest main integration. The final log is
`analysis/results/refresh-20261004/final-tests.log`. Additional
actual restricted subprocess checks are recorded separately; GPU benchmark
clocks remain unsuitable proof of CPU submission compliance. These workloads
and worker counts differ from October 3, so no exact speedup factor is claimed.


A later profile found repeated feature-column cleaning in replica inference.
Cleaning the full small row matrix once gives bit-for-bit equal features on all
1,147,147 replay decisions in both float32 and float64. All seven behavior tests
passed again. A nonexclusive microbenchmark over 1,148 single-row calls took
0.678 s before and 0.174 s after; this is a feature-construction measurement,
not a game throughput claim. Existing running workers retain loaded modules;
subsequent pools use the equivalent optimized code. No model weights or
candidate decisions were intentionally changed.

`analysis/results/refresh-20261004/gpu-concurrency.txt` records sixteen concurrent
CUDA worker contexts, four per V100, each using 308 MiB. Total device use was
1,236 MiB per device with 14,909 MiB free. Low instantaneous GPU utilization is
consistent with CPU-bound simulation and does not mean CUDA work is absent;
per-game batch/ranking counters record the actual work.

## October 4 follow-up checks

Single-action replica inference now constructs features with NumPy scalars,
avoiding dozens of one-element arrays. A compatibility predicate retains the
vector path when the installed NumPy scalar-promotion rules differ. Against the
unchanged batch path, all **1,147,147 replay decisions matched bit-for-bit in
both float32 and float64**, including the final compatibility predicate. The
verification records the source fingerprint in `scalar-features-check.json`.
A 1,148-row microbenchmark took about 0.177 seconds before and 0.054 seconds
after this additional change; this measures feature construction only. No
end-to-end speedup factor is established.

The bot loader also isolates top-level sibling module names already loaded by
the SDK outside the harness. Without this, a candidate could reuse a different
bot's `params` or `strategy` module. A regression test loads two conflicting
bots and checks both candidate isolation and restoration of the original SDK
alias. The benchmarks used fresh worker processes and did not encounter that
preloaded-SDK condition.

After these changes, **140 repository tests passed with CUDA enabled**, without
skips, in 56.6 seconds. The follow-up log and feature verification are included
in [the compact evidence bundle](../analysis/reports/evidence/20261004/index.json).
The additional strategy studies completed 17,895 full games with no player
failures. No candidate passed its performance selection rule; harness fixes
and equivalent feature acceleration do not imply a stronger poker strategy.

## Opponent catalogue loader follow-up

The data-catalogue migration passed all 149 tests with CUDA enabled and no
skips. A CLI integration run completed 76 games with catalogue opponents and
a catalogue candidate across four concurrent V100 workers; every device
performed CUDA rankings. A separate 24-game CPU tournament exercised catalogue
roster filtering and exact-main fallback. Both runs had zero player failures.
All 89 current replicas also matched their previous generated-file versions'
chips, action counters and verdicts exactly on 15 seeded tables. The 65-identity
strict roster and all 77 reference-field parameter records are unchanged.
