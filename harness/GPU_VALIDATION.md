# CUDA harness validation

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
