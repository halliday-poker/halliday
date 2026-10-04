"""Person A: range-conditioned Hold'em equity, with no strategy/SDK dependency.

The integration API is equity(hole, board, opp_ranges, n_iters, time_budget_ms).
Ranges are None (any two cards) or mappings of two-card tuples to weights.
See EQUITY_ENGINE.md for range semantics, deadlines and failure handling.
"""

from bisect import bisect_right
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from math import comb, isfinite, sqrt
from random import Random
from time import perf_counter


HAND_NAMES = (
    "High Card", "One Pair", "Two Pair", "Three of a Kind", "Straight",
    "Flush", "Full House", "Four of a Kind", "Straight Flush", "Royal Flush",
)
_RANKS = "23456789TJQKA"
_SUITS = "cdhs"


class ImpossibleRangeError(ValueError):
    """No disjoint assignment of positive-weight opponent hands is possible."""


class EquityTimeout(TimeoutError):
    """The time budget expired before a complete estimate was available."""


class EquitySamplingError(RuntimeError):
    """The bounded sampler could not produce a compatible deal."""


@dataclass(frozen=True)
class PlayerOdds:
    """Hero first, then opponents in input order; probabilities are fractions."""

    win: float
    tie: float
    loss: float
    equity: float
    hand_probabilities: dict[str, float] | None


@dataclass(frozen=True)
class EquityEstimate:
    players: tuple[PlayerOdds, ...]
    samples: int
    attempts: int
    method: str
    stop_reason: str
    standard_error: float | None

    @property
    def equity(self) -> float:
        return self.players[0].equity


def _parse_card(card):
    if not isinstance(card, str) or len(card) != 2:
        raise ValueError(f"Invalid card: {card!r}")
    try:
        return _SUITS.index(card[1].lower()) * 13 + _RANKS.index(card[0].upper())
    except ValueError:
        raise ValueError(f"Invalid card: {card!r}") from None


def _straight_high(mask):
    runs = mask & (mask >> 1) & (mask >> 2) & (mask >> 3) & (mask >> 4)
    if runs:
        return runs.bit_length() + 3
    return 5 if mask & 0x403C == 0x403C else 0  # A-2-3-4-5


def _evaluate(cards):
    """Best-five tuple for 5-7 distinct card ids; higher wins, ranks 2..14."""
    counts, suits, mask = [0] * 15, [0] * 4, 0
    for card in cards:
        rank = card % 13 + 2
        counts[rank] += 1
        bit = 1 << rank
        mask |= bit
        suits[card // 13] |= bit
    ranks = [r for r in range(14, 1, -1) if counts[r]]
    flush = next((s for s in suits if s.bit_count() >= 5), 0)
    if flush:
        high = _straight_high(flush)
        if high:
            return (8, high)
    quads = [r for r in ranks if counts[r] == 4]
    if quads:
        return (7, quads[0], next(r for r in ranks if r != quads[0]))
    trips = [r for r in ranks if counts[r] == 3]
    pairs = [r for r in ranks if counts[r] >= 2]
    if trips:
        other_pairs = [r for r in pairs if r != trips[0]]
        if other_pairs:
            return (6, trips[0], other_pairs[0])
    if flush:
        return (5, *[r for r in ranks if flush & (1 << r)][:5])
    high = _straight_high(mask)
    if high:
        return (4, high)
    if trips:
        return (3, trips[0], *[r for r in ranks if r != trips[0]][:2])
    if len(pairs) >= 2:
        return (2, *pairs[:2], next(r for r in ranks if r not in pairs[:2]))
    if pairs:
        return (1, pairs[0], *[r for r in ranks if r != pairs[0]][:3])
    return (0, *ranks[:5])


def evaluate_hand(cards):
    """Public fast made-hand evaluator; category 0..8 plus all tiebreakers.

    Accepts 5-7 card strings. A royal flush compares as (8, 14). This helper
    does not estimate equity or treat a preflop pair as a five-card hand.
    """
    if not isinstance(cards, (list, tuple)) or not 5 <= len(cards) <= 7:
        raise ValueError("Expected 5-7 distinct cards")
    parsed = tuple(_parse_card(c) for c in cards)
    if len(set(parsed)) != len(parsed):
        raise ValueError("Expected 5-7 distinct cards")
    return _evaluate(parsed)


@dataclass(frozen=True)
class _Range:
    hands: tuple
    masks: tuple
    weights: tuple
    cumulative: tuple

    def draw(self, rng):
        i = min(bisect_right(self.cumulative, rng.random() * self.cumulative[-1]),
                len(self.hands) - 1)
        return self.hands[i], self.masks[i]


def _compile_range(raw, known, check_time):
    if raw is None:
        return None
    if not isinstance(raw, Mapping) or len(raw) > 1326:
        raise ValueError("Each range must be None or a mapping of at most 1326 combos")
    seen, entries = set(), []
    for i, (cards, weight) in enumerate(raw.items()):
        if i % 32 == 0:
            check_time()
        if not isinstance(cards, tuple) or len(cards) != 2:
            raise ValueError("Range keys must be two-card tuples, e.g. ('As', 'Kd')")
        hand = tuple(sorted(_parse_card(c) for c in cards))
        if hand[0] == hand[1] or hand in seen:
            raise ValueError("Repeated cards or duplicate/reversed range combos")
        seen.add(hand)
        if isinstance(weight, (bool, str, bytes)):
            raise ValueError("Range weights must be finite, nonnegative numbers")
        try:
            weight = float(weight)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Range weights must be finite, nonnegative numbers") from None
        if not isfinite(weight) or weight < 0:
            raise ValueError("Range weights must be finite, nonnegative numbers")
        mask = (1 << hand[0]) | (1 << hand[1])
        if weight > 0 and not mask & known:
            entries.append((hand, mask, weight))
    if not entries:
        raise ImpossibleRangeError("An opponent has no positive-weight unblocked hand")
    # Common scaling is irrelevant to equity, and avoids overflow in the CDF.
    scale = max(w for _, _, w in entries)
    hands, masks, weights, cumulative = [], [], [], []
    total = 0.0
    for i, (hand, mask, weight) in enumerate(entries):
        if i % 32 == 0:
            check_time()
        weight /= scale
        new_total = total + weight
        if weight == 0 or new_total == total:
            raise ValueError("Range weights are too disparate for float precision")
        hands.append(hand)
        masks.append(mask)
        weights.append(weight)
        cumulative.append(new_total)
        total = new_total
    return _Range(tuple(hands), tuple(masks), tuple(weights), tuple(cumulative))


def _check_compatible(restricted, known, check_time):
    """Reject provably impossible joint ranges, with bounded preprocessing.

    A search cap is inconclusive, never proof of impossibility. The sampler
    still has an attempt cap and deadline if feasibility could not be proved.
    """
    visited, nodes = set(), 0

    def visit(depth, used):
        nonlocal nodes
        nodes += 1
        if nodes % 32 == 0:
            check_time()
        if nodes > 10000:
            return None
        if depth == len(restricted):
            return True
        key = (depth, used)
        if key in visited:
            return False
        visited.add(key)
        for i, mask in enumerate(restricted[depth].masks):
            if i % 32 == 0:
                check_time()
            if not mask & used:
                possible = visit(depth + 1, used | mask)
                if possible is not False:
                    return possible
        return False

    if visit(0, known) is False:
        raise ImpossibleRangeError("Opponent ranges cannot hold disjoint cards together")


def equity(hole, board, opp_ranges, n_iters=1000, time_budget_ms=25.0) -> float:
    """Expected hero showdown share against the supplied live opponent ranges.

    All five agreed arguments work positionally or by keyword. No strategy,
    GameState, stacks, SDK or opponent-profile object is required. Raises a
    documented exception rather than inventing equity if no sample is ready.
    """
    return estimate_equity(hole, board, opp_ranges, n_iters, time_budget_ms).equity


def estimate_equity(hole, board, opp_ranges, n_iters=1000, time_budget_ms=25.0,
                    *, seed=None, _evaluate_batch=None, _batch_size=128) -> EquityEstimate:
    """Same engine plus diagnostics and each player's final hand distribution.

    n_iters limits completed Monte Carlo deals. Timed calls check a deadline
    during preparation and before EVERY draw attempt; an interrupted estimate
    includes only completed deals. No samples means EquityTimeout, not 0/0.5.
    time_budget_ms=None allows reproducible offline sampling with seed, and
    exact enumeration for small outcome spaces (at most min(n_iters, 2000)).
    The offline harness may supply a batched made-hand evaluator. Sampling,
    range weights and aggregation stay here; the default has no GPU dependency.
    """
    started = perf_counter()
    if type(n_iters) is not int or n_iters < 1:
        raise ValueError("n_iters must be a positive integer")
    if seed is not None and type(seed) is not int:
        raise ValueError("seed must be an integer or None")
    if _evaluate_batch is not None and (type(_batch_size) is not int or _batch_size < 1):
        raise ValueError("_batch_size must be a positive integer")
    if time_budget_ms is not None and (
        isinstance(time_budget_ms, (bool, str, bytes))
        or not isinstance(time_budget_ms, (int, float))
        or not isfinite(time_budget_ms) or time_budget_ms < 0
    ):
        raise ValueError("time_budget_ms must be nonnegative and finite, or None")
    deadline = None if time_budget_ms is None else started + time_budget_ms / 1000

    def check_time():
        if deadline is not None and perf_counter() >= deadline:
            raise EquityTimeout("Equity budget expired before an estimate was ready")

    check_time()
    if not isinstance(hole, (list, tuple)) or not isinstance(board, (list, tuple)):
        raise ValueError("hole and board must be lists or tuples of card strings")
    if len(hole) != 2 or len(board) not in (0, 3, 4, 5):
        raise ValueError("Expected two hole cards and 0, 3, 4 or 5 board cards")
    hole, board = tuple(_parse_card(c) for c in hole), tuple(_parse_card(c) for c in board)
    if len(set(hole + board)) != len(hole + board):
        raise ValueError("Hole and board cards must be distinct")
    if (not isinstance(opp_ranges, Sequence) or isinstance(opp_ranges, (str, bytes))
            or len(opp_ranges) > 8):
        raise ValueError("opp_ranges must be a sequence of zero to eight live ranges")
    known = sum(1 << c for c in hole + board)
    ranges = tuple(_compile_range(raw, known, check_time) for raw in opp_ranges)
    if not ranges:
        return EquityEstimate((PlayerOdds(1.0, 0.0, 0.0, 1.0, None),),
                              0, 0, "exact", "no_opponents", 0.0)
    restricted = sorted(((i, r) for i, r in enumerate(ranges) if r is not None),
                        key=lambda item: len(item[1].hands))
    uniform = [i for i, r in enumerate(ranges) if r is None]
    _check_compatible([r for _, r in restricted], known, check_time)
    check_time()
    remaining = tuple(c for c in range(52) if not known & (1 << c))
    missing, n = 5 - len(board), len(ranges) + 1
    wins, ties, shares = ([0.0] * n for _ in range(3))
    categories = [[0.0] * 10 for _ in range(n)]
    weight_total, hero_sq, samples, attempts = 0.0, 0.0, 0, 0
    pending = []

    def record_values(values, weight):
        nonlocal weight_total, hero_sq, samples
        best = max(values)
        winners = [i for i, v in enumerate(values) if v == best]
        share = 1 / len(winners)
        for i, value in enumerate(values):
            categories[i][9 if value == (8, 14) else value[0]] += weight
        for i in winners:
            wins[i] += weight * (len(winners) == 1)
            ties[i] += weight * (len(winners) > 1)
            shares[i] += weight * share
        hero_sq += weight * (share * share if 0 in winners else 0)
        weight_total += weight
        samples += 1

    def flush():
        if not pending:
            return
        hands = [hand for deal, _ in pending for hand in deal]
        values = _evaluate_batch(hands)
        if len(values) != len(hands):
            raise RuntimeError("Batch evaluator returned the wrong number of hands")
        for i, (_, weight) in enumerate(pending):
            record_values(values[i * n:(i + 1) * n], weight)
        pending.clear()

    def record(holes, runout, weight=1.0):
        final_board = board + tuple(runout)
        deal = [hole + final_board] + [h + final_board for h in holes]
        if _evaluate_batch is None:
            record_values([_evaluate(hand) for hand in deal], weight)
        else:
            pending.append((deal, weight))
            if len(pending) >= _batch_size:
                flush()

    # No timed enumeration prefixes: an unfinished weighted enumeration would
    # bias the answer. Timed calls sample instead. A fully fixed river is tiny.
    upper_bound = comb(len(remaining) - 2 * len(ranges), missing)
    for r in ranges:
        upper_bound *= len(r.hands) if r else comb(len(remaining), 2)
    fixed_river = not missing and all(r is not None and len(r.hands) == 1 for r in ranges)
    exact = fixed_river or (deadline is None and upper_bound <= min(n_iters, 2000))
    if exact:
        order = [i for i, _ in restricted] + uniform
        holes = [None] * len(ranges)

        def enumerate_deals(depth, used, weight):
            if depth == len(order):
                deck = tuple(c for c in remaining if not used & (1 << c))
                for runout in combinations(deck, missing):
                    record(holes, runout, weight)
                return
            i = order[depth]
            r = ranges[i]
            options = (zip(r.hands, r.masks, r.weights) if r else
                       ((h, (1 << h[0]) | (1 << h[1]), 1.0)
                        for h in combinations(remaining, 2)))
            for hand, mask, w in options:
                if not mask & used:
                    holes[i] = hand
                    enumerate_deals(depth + 1, used | mask, weight * w)

        enumerate_deals(0, known, 1.0)
        flush()
        attempts, stop_reason = samples, "enumerated"
        if not weight_total:
            raise EquitySamplingError("Joint weights are too small for float precision")
    else:
        rng = Random(seed)
        max_attempts = max(1000, n_iters * 100)
        stop_reason = "iteration_limit"
        while samples + len(pending) < n_iters:
            try:
                check_time()
            except EquityTimeout:
                if not samples and not pending:
                    raise
                stop_reason = "time_budget"
                break
            if attempts >= max_attempts:
                if not samples and not pending:
                    raise EquitySamplingError("No compatible deal within the attempt limit")
                stop_reason = "attempt_limit"
                break
            attempts += 1
            used, holes = known, [None] * len(ranges)
            for i, r in restricted:
                hand, mask = r.draw(rng)
                if mask & used:
                    break  # Reject the WHOLE assignment, not just this seat.
                holes[i], used = hand, used | mask
            else:
                # Each valid restricted assignment leaves the same number of
                # cards, so uniform seats can be drawn afterwards without bias.
                deck = remaining if not restricted else tuple(
                    c for c in remaining if not used & (1 << c))
                draw = rng.sample(deck, 2 * len(uniform) + missing)
                for j, i in enumerate(uniform):
                    holes[i] = tuple(draw[2 * j:2 * j + 2])
                record(holes, draw[2 * len(uniform):])
        flush()

    players = tuple(PlayerOdds(
        wins[i] / weight_total, ties[i] / weight_total,
        max(0.0, 1 - (wins[i] + ties[i]) / weight_total), shares[i] / weight_total,
        {name: categories[i][j] / weight_total for j, name in enumerate(HAND_NAMES)},
    ) for i in range(n))
    error = 0.0 if exact else None
    if not exact and samples > 1:
        error = sqrt(max(0.0, hero_sq - samples * players[0].equity ** 2)
                     / (samples - 1) / samples)
    return EquityEstimate(players, samples, attempts, "exact" if exact else "monte_carlo",
                          stop_reason, error)
