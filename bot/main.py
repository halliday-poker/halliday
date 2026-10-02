"""Your tournament bot. Keep this file named main.py.

Test it locally:

    macpoker play main.py house:call house:random --deals 50

Add --subprocess for full production parity. You can split your code into
extra modules in this folder and import them from here; zip the whole folder
(main.py at the root) when you submit.

Full SDK reference: https://docs.poker.monashcoding.com
"""

from itertools import combinations
from math import isfinite, sqrt
from random import Random
from time import perf_counter

from macpoker import Bot


# Exclusive best-five categories, ascending in strength. Royal Flush is split
# out for reporting, but uses the ordinary straight-flush value for comparison.
HAND_NAMES = (
    "High Card", "One Pair", "Two Pair", "Three of a Kind", "Straight",
    "Flush", "Full House", "Four of a Kind", "Straight Flush", "Royal Flush",
)
_RANKS = "23456789TJQKA"
_SUITS = "cdhs"


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
    """Best-five comparison tuple for 5-7 distinct card ids; higher wins.

    Direct rank/suit counting avoids the SDK evaluator's 21 five-card
    evaluations per seven-card hand. All kickers still participate in ties.
    """
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


def _category(value):
    return 9 if value == (8, 14) else value[0]


def _probabilities(counts):
    total = sum(counts)
    return {name: counts[i] / total for i, name in reversed(list(enumerate(HAND_NAMES)))}


def _pot_layers(contributions, live):
    """SDK pot eligibility after refunding a unique unmatched top bet."""
    contributions = list(contributions)
    refunds = [0] * len(contributions)
    top = max(contributions)
    leaders = [s for s, amount in enumerate(contributions) if amount == top]
    if len(leaders) == 1:
        seat = leaders[0]
        refunds[seat] = top - max(c for s, c in enumerate(contributions) if s != seat)
        contributions[seat] -= refunds[seat]
    layers, previous = [], 0
    for level in sorted({c for c in contributions if c > 0}):
        amount = sum(min(c, level) - min(c, previous) for c in contributions)
        eligible = [s for s in live if contributions[s] >= level] or live
        layers.append((amount, eligible))
        previous = level
    return layers, refunds


class MyBot(Bot):
    def __init__(self):
        self.last_odds = None
        self._odds_key = None
        self._starting_stack = 200  # Documented tournament default.
        self._hand_start = None

    def on_match_start(self, info):
        self._starting_stack = info["stack"]
        self._hand_start = None
        self.last_odds = self._odds_key = None

    def on_hand_start(self, info):
        self._hand_start = (info["hand"], tuple(info["players"]), tuple(info["stacks"]))
        self.last_odds = self._odds_key = None

    def calculate_odds(self, state, *, samples=1000, seed=None,
                       starting_stacks=None, time_budget_ms=None):
        """Calculate final hand odds, showdown equity and strategy inputs.

        Returns fractions in [0, 1], keyed by stable player id, using ONLY
        public GameState fields and our hole cards. See README for the schema.
        Unknown cards are uniform; betting does not yet reweight hand ranges.
        Players still in the hand are assumed to stay through the river.

        Our hand distribution is exact postflop; opponent distributions and
        pairwise comparisons are exact on the river. Full-table showdown is
        exact for a sole live player or a heads-up river involving us.
        Other calculations use shared-board, disjoint-hole Monte Carlo deals.

        time_budget_ms is an optional SOFT budget: exact passes finish, then
        simulation checks the deadline every 16 trials (at least one trial).
        Omit it for reproducible sample counts with seed. No background work,
        filesystem/network access, global RNG changes or hidden engine data.
        """
        started = perf_counter()
        if type(samples) is not int or samples < 1:
            raise ValueError("samples must be a positive integer")
        if seed is not None and type(seed) is not int:
            raise ValueError("seed must be an integer or None")
        if time_budget_ms is not None and (
            not isfinite(time_budget_ms) or time_budget_ms <= 0
        ):
            raise ValueError("time_budget_ms must be positive and finite")
        deadline = None if time_budget_ms is None else started + time_budget_ms / 1000
        hole = tuple(_parse_card(c) for c in state.hole)
        board = tuple(_parse_card(c) for c in state.board)
        if len(hole) != 2 or len(board) not in (0, 3, 4, 5):
            raise ValueError("Expected two hole cards and 0, 3, 4 or 5 board cards")
        known = set(hole + board)
        if len(known) != len(hole) + len(board):
            raise ValueError("Hole and board cards must be distinct")
        players, folded, hero = tuple(state.players), tuple(state.folded), state.seat
        n = len(players)
        if (not 2 <= n <= 9 or len(set(players)) != n or len(folded) != n
                or type(hero) is not int or not 0 <= hero < n or all(folded)):
            raise ValueError("Invalid seats, player ids or folded flags")
        stacks = tuple(state.stacks)
        if starting_stacks is None:
            if self._hand_start and self._hand_start[:2] == (state.hand, players):
                starting_stacks = self._hand_start[2]
            else:
                starting_stacks = (self._starting_stack,) * n
        starting_stacks = tuple(starting_stacks)
        if (len(stacks) != n or len(starting_stacks) != n
                or any(s < 0 or s > initial for s, initial in zip(stacks, starting_stacks))
                or state.to_call < 0 or not 0 <= state.button < n):
            raise ValueError("Invalid stacks, call cost or button")
        contributions = [initial - s for initial, s in zip(starting_stacks, stacks)]
        if sum(contributions) != state.pot:
            raise ValueError("Starting stacks must agree with stacks and pot")
        call_cost = min(state.to_call, stacks[hero]) if not folded[hero] else 0
        contributions[hero] += call_cost
        live = [s for s in range(n) if not folded[s]]  # All-in seats remain live.
        opponents = [s for s in range(n) if s != hero]
        layers, refunds = _pot_layers(contributions, live)
        remaining = tuple(c for c in range(52) if c not in known)
        missing = 5 - len(board)
        hero_counts, opponent_counts = [0] * 10, [0] * 10
        current = _category(_evaluate(hole + board)) if board else None

        # Marginal hand probabilities do not depend on the number of unknown
        # opponents. Their unobserved cards (including folds) integrate out.
        if board:
            for runout in combinations(remaining, missing):
                hero_counts[_category(_evaluate(hole + board + runout))] += 1

        wins, ties, equity, equity_sq = ([0.0] * n for _ in range(4))
        pairwise = {s: [0, 0, 0] for s in live if s != hero and not folded[hero]}
        payout_total, showdown_trials = 0.0, 0
        layer_equity = [0.0] * len(layers)

        def record_showdown(values):
            nonlocal payout_total, showdown_trials
            showdown_trials += 1
            best = max(values[s] for s in live)
            winners = [s for s in live if values[s] == best]
            for s in winners:
                wins[s] += len(winners) == 1
                ties[s] += len(winners) > 1
                share = 1 / len(winners)
                equity[s] += share
                equity_sq[s] += share * share
            for s, counts in pairwise.items():
                result = 0 if values[hero] > values[s] else (1 if values[hero] == values[s] else 2)
                counts[result] += 1
            payout_total += refunds[hero]
            for i, (amount, eligible) in enumerate(layers):
                best = max(values[s] for s in eligible)
                winners = sorted((s for s in eligible if values[s] == best),
                                 key=lambda s: (s - state.button - 1) % n)
                if hero in winners:
                    layer_equity[i] += 1 / len(winners)
                    share, odd = divmod(amount, len(winners))
                    payout_total += share + (winners.index(hero) < odd)

        exact_duel = not missing and len(live) == 2 and not folded[hero]
        exact_showdown = exact_duel or len(live) == 1
        river_pairwise = [0, 0, 0]
        if not missing:
            hero_value = _evaluate(hole + board)
            for other_hole in combinations(remaining, 2):
                value = _evaluate(other_hole + board)
                opponent_counts[_category(value)] += 1
                result = 0 if hero_value > value else (1 if hero_value == value else 2)
                river_pairwise[result] += 1
                if exact_duel:
                    values = [value] * n
                    values[hero] = hero_value
                    record_showdown(values)
        if len(live) == 1:
            # Only the surviving seat participates, so cards cannot affect
            # the winner or payout, even when that seat is an opponent.
            record_showdown([(0,)] * n)

        trials = 0
        if missing or not exact_showdown:
            rng = Random(seed)
            for trial in range(samples):
                if trial and trial % 16 == 0 and deadline is not None and perf_counter() >= deadline:
                    break
                draw = rng.sample(remaining, missing + 2 * len(opponents))
                final_board = board + tuple(draw[:missing])
                values = [None] * n
                values[hero] = _evaluate(hole + final_board)
                if not board:
                    hero_counts[_category(values[hero])] += 1
                for j, seat in enumerate(opponents):
                    offset = missing + 2 * j
                    values[seat] = _evaluate(tuple(draw[offset:offset + 2]) + final_board)
                    if missing:
                        opponent_counts[_category(values[seat])] += 1
                if not exact_showdown:
                    record_showdown(values)
                trials += 1

        hero_probs = _probabilities(hero_counts)
        opponent_probs = _probabilities(opponent_counts)
        report_players = {}
        for seat, player in enumerate(players):
            q = equity[seat] / showdown_trials
            exact_for_seat = exact_showdown or folded[seat]
            error = 0.0 if exact_for_seat else None
            if not exact_for_seat and showdown_trials > 1:
                error = sqrt(max(0, equity_sq[seat] - showdown_trials * q * q)
                             / (showdown_trials - 1) / showdown_trials)
            hand_exact = bool(board) if seat == hero else not missing
            report_players[player] = {
                "seat": seat, "folded": folded[seat],
                "hand_probabilities": dict(hero_probs if seat == hero else opponent_probs),
                "hand_method": "exact" if hand_exact else "monte_carlo",
                "hand_evaluations": sum(hero_counts if seat == hero else opponent_counts),
                "win": wins[seat] / showdown_trials,
                "tie": ties[seat] / showdown_trials,
                "loss": 1 - (wins[seat] + ties[seat]) / showdown_trials,
                "equity": q, "equity_standard_error": error,
            }

        heads_up = {}
        for seat, counts in pairwise.items():
            counts = river_pairwise if not missing else counts
            total = sum(counts)
            heads_up[players[seat]] = {
                "win": counts[0] / total, "tie": counts[1] / total,
                "loss": counts[2] / total, "equity": (counts[0] + counts[1] / 2) / total,
                "method": "exact" if not missing else "monte_carlo", "trials": total,
            }

        next_card = None
        if len(board) in (3, 4):
            counts, improving = [0] * 10, []
            for card in remaining:
                category = _category(_evaluate(hole + board + (card,)))
                counts[category] += 1
                if category > current:
                    improving.append(_RANKS[card % 13] + _SUITS[card // 13])
            next_card = {
                "hand_probabilities": _probabilities(counts),
                "category_improvement_probability": len(improving) / len(remaining),
                "category_improvement_cards": improving,
            }

        return {
            "hero": players[hero], "cards_to_come": missing,
            "players": report_players, "sampled_deals": trials,
            "showdown_method": "exact" if exact_showdown else "monte_carlo",
            "showdown_trials": showdown_trials,
            "hero_heads_up": heads_up,
            "hero_draws": {
                "current_hand": HAND_NAMES[current] if current is not None else None,
                "category_improvement_by_river": (
                    sum(hero_probs[name] for name in HAND_NAMES[current + 1:])
                    if current is not None else None),
                "at_least_by_river": {
                    name: sum(hero_probs[h] for h in HAND_NAMES[i:])
                    for i, name in enumerate(HAND_NAMES)},
                "next_card": next_card,
            },
            "strategy": {
                "call_cost": call_cost,
                "pot_odds": call_cost / (state.pot + call_cost) if state.pot + call_cost else 0.0,
                "checkdown_expected_payout": payout_total / showdown_trials,
                "checkdown_call_ev": payout_total / showdown_trials - call_cost,
                "uncalled_refund": refunds[hero],
                "pots_after_call": [
                    {"amount": amount, "eligible_players": [players[s] for s in eligible],
                     "hero_equity": layer_equity[i] / showdown_trials}
                    for i, (amount, eligible) in enumerate(layers)],
            },
            "assumptions": (
                "Uniform unseen cards; no betting-range inference.",
                "All live players reach showdown; folded hand distributions are hypothetical.",
                "Call EV freezes contributions after our call: no future bets, calls or folds.",
                "Sampled zeroes do not imply impossible outcomes; standard errors are estimates.",
            ),
        }

    def act(self, state):
        # Cache identical decisions, including money/eligibility fields so EV
        # cannot go stale when someone bets without changing the board.
        key = (state.hand, tuple(state.hole), tuple(state.board), state.seat,
               tuple(state.players), tuple(state.folded), tuple(state.stacks),
               state.pot, state.to_call, state.button)
        if key != self._odds_key:
            self.last_odds = None
            self._odds_key = None
            if state.clock_ms >= 250:
                self.last_odds = self.calculate_odds(
                    state, samples=64 if state.clock_ms < 5000 else 256,
                    time_budget_ms=10 if state.clock_ms < 5000 else 25)
                self._odds_key = key

        # What you can see:
        #   state.hole          your two cards, e.g. ["As", "Kd"]
        #   state.board         community cards dealt so far
        #   state.pot           chips in the middle
        #   state.to_call       chips you must add to stay in the hand
        #   state.stacks        every seat's remaining chips
        #   state.min_raise_to  smallest legal raise-to amount
        #   state.max_raise_to  raise-to amount that puts you all in
        #   state.history       every action this hand: [street, seat, kind, amount]
        #   state.clock_ms      time left on your clock
        #
        # What you can do:
        #   state.check() / state.call() / state.fold()
        #   state.raise_to(amount) / state.all_in()

        if state.to_call == 0:
            return state.check()

        pot_odds = state.to_call / (state.pot + state.to_call)
        if pot_odds < 0.3:
            return state.call()
        return state.fold()
