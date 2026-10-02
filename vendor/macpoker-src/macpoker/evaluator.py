"""Poker hand evaluation for 5 to 7 cards, pure python, dependency free.

evaluate() returns a tuple; higher tuples beat lower tuples. The first
element is the hand category (8 = straight flush ... 0 = high card),
followed by the tiebreaker ranks for that category.
"""

from __future__ import annotations

from itertools import combinations

CATEGORY_NAMES = [
    "high card",
    "pair",
    "two pair",
    "three of a kind",
    "straight",
    "flush",
    "full house",
    "four of a kind",
    "straight flush",
]


def _straight_high(ranks: set[int]) -> int | None:
    """Highest straight top-rank in a set of ranks, or None. Handles the wheel."""
    rs = set(ranks)
    if 12 in rs:
        rs.add(-1)  # ace plays low for A-2-3-4-5
    best = None
    for high in range(12, 2, -1):
        if all(high - i in rs for i in range(5)):
            best = high
            break
    return best


def evaluate5(cards: list[int]) -> tuple:
    ranks = sorted((c % 13 for c in cards), reverse=True)
    suits = [c // 13 for c in cards]
    counts: dict[int, int] = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    # ranks grouped by (count, rank) descending: e.g. full house -> [trip rank, pair rank]
    by_count = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    grouped = [r for r, _ in by_count]

    is_flush = len(set(suits)) == 1
    straight = _straight_high(set(ranks))

    if is_flush and straight is not None:
        return (8, straight)
    if by_count[0][1] == 4:
        return (7, grouped[0], grouped[1])
    if by_count[0][1] == 3 and by_count[1][1] == 2:
        return (6, grouped[0], grouped[1])
    if is_flush:
        return (5, *ranks)
    if straight is not None:
        return (4, straight)
    if by_count[0][1] == 3:
        kickers = sorted((r for r in ranks if r != grouped[0]), reverse=True)
        return (3, grouped[0], *kickers)
    if by_count[0][1] == 2 and by_count[1][1] == 2:
        high_pair, low_pair = grouped[0], grouped[1]
        kicker = max(r for r in ranks if r not in (high_pair, low_pair))
        return (2, high_pair, low_pair, kicker)
    if by_count[0][1] == 2:
        kickers = sorted((r for r in ranks if r != grouped[0]), reverse=True)
        return (1, grouped[0], *kickers)
    return (0, *ranks)


def evaluate(cards: list[int]) -> tuple:
    """Best 5-card value from 5, 6 or 7 cards."""
    if len(cards) == 5:
        return evaluate5(cards)
    return max(evaluate5(list(combo)) for combo in combinations(cards, 5))


def hand_name(value: tuple) -> str:
    return CATEGORY_NAMES[value[0]]
