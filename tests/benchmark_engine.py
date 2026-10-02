"""Repeatable local latency/sample-count check; not a unit-test speed gate."""

from itertools import combinations
from pathlib import Path
from statistics import median
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot.engine import EquityTimeout, estimate_equity


def main():
    cards = [r + s for s in "cdhs" for r in "23456789TJQKA"]
    wide = dict.fromkeys(combinations(cards, 2), 1)
    tight = {("Qh", "Jh"): 1, ("9c", "9d"): 2,
             ("Ac", "Ad"): 1, ("6c", "5c"): 0.5}
    cases = [("2 uniform", [None]), ("5 uniform", [None] * 4),
             ("9 uniform", [None] * 8), ("5 mixed", [tight, None, tight, None]),
             ("9 full mappings", [wide] * 8)]
    for name, ranges in cases:
        for board in ([], ["Qs", "7s", "2d"], ["Qs", "7s", "2d", "3h", "9s"]):
            times, counts, unavailable = [], [], 0
            for seed in range(7):
                started = perf_counter()
                try:
                    result = estimate_equity(["As", "Ks"], board, ranges,
                                             256, 25, seed=seed)
                    counts.append(result.samples)
                except EquityTimeout:
                    unavailable += 1
                times.append(1000 * (perf_counter() - started))
            print(f"{name:16} board={len(board)} median={median(times):6.2f}ms "
                  f"max={max(times):6.2f}ms samples={min(counts, default=0)}.."
                  f"{max(counts, default=0)} unavailable={unavailable}")


if __name__ == "__main__":
    main()
