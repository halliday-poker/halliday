"""Person A's contract, independent SDK oracle and weighted sampling checks."""

from copy import deepcopy
from itertools import combinations, product
from math import comb
from pathlib import Path
from random import Random
import inspect
import random
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "macpoker-src"))
sys.path.insert(0, str(ROOT))

from macpoker import Bot, GameState
from macpoker.cards import parse_cards
from macpoker.evaluator import evaluate as sdk_evaluate
from macpoker.sdk import load_bot_from_file
from bot import engine
from bot.engine import (HAND_NAMES, ImpossibleRangeError, EquitySamplingError,
                        EquityTimeout, equity, estimate_equity, evaluate_hand)
from bot.main import MyBot


HOLE = ["9h", "8h"]
BOARD = ["Ac", "Ad", "Ah", "As", "2d"]


def reference_equity(hole, board, ranges):
    """Small exhaustive oracle: SDK evaluation and independent product weights."""
    hole, board = parse_cards(hole), parse_cards(board)
    known = set(hole + board)
    possibilities = []
    for r in ranges:
        if r is None:
            possibilities.append([(pair, 1) for pair in combinations(
                [c for c in range(52) if c not in known], 2)])
        else:
            possibilities.append([(tuple(parse_cards(hand)), weight)
                                  for hand, weight in r.items() if weight > 0])
    numerator, denominator = 0.0, 0.0
    for opponents in product(*possibilities):
        cards = hole + board + [c for hand, _ in opponents for c in hand]
        if len(cards) != len(set(cards)):
            continue
        weight = 1
        for _, w in opponents:
            weight *= w
        deck = [c for c in range(52) if c not in cards]
        for runout in combinations(deck, 5 - len(board)):
            final_board = board + list(runout)
            values = [sdk_evaluate(hole + final_board)]
            values += [sdk_evaluate(list(hand) + final_board) for hand, _ in opponents]
            best = max(values)
            numerator += weight * (1 / values.count(best) if values[0] == best else 0)
            denominator += weight
    return numerator / denominator


def state(**updates):
    msg = dict(hole=["As", "Ks"], board=[], players=[2, 0, 1], seat=0,
               folded=[False, False, False], stacks=[198, 0, 200], pot=202,
               to_call=0, hand=1, clock_ms=30000, button=0)
    msg.update(updates)
    return GameState(msg)


class EvaluatorTests(unittest.TestCase):
    def test_categories_wheel_double_trips_three_pairs_and_kickers(self):
        hands = [
            "As Ks Qs Js Ts 2d 2c", "As 2s 3s 4s 5s Kd Qh",
            "As Ah Ac Ad Ks Qs Js", "As Ah Ac Ks Kh Kc 2d",
            "As 9s 7s 5s 3s Ks Qs", "As 2c 3h 4d 5s 6h 7s",
            "As Ah Ac Ks Qs Js 9s", "As Ah Ks Kh Qs Qh 2s",
            "As Ah Ks Qh Js 9h 2c", "As Kd Qh Js 9c 8h 2d",
        ]
        for text in hands:
            value = evaluate_hand(text.split())
            self.assertEqual((value[0], *(r - 2 for r in value[1:])),
                             sdk_evaluate(parse_cards(text.split())))

    def test_random_five_six_seven_card_hands_against_sdk(self):
        rng = Random(712)
        for size in (5, 6, 7):
            for _ in range(500):
                cards = rng.sample(range(52), size)
                value = engine._evaluate(cards)
                self.assertEqual((value[0], *(r - 2 for r in value[1:])), sdk_evaluate(cards))

    def test_invalid_made_hands(self):
        for cards in (["As", "Kh"], ["As"] * 5, ["ZZ"] * 5):
            with self.assertRaises(ValueError):
                evaluate_hand(cards)


class EquityTests(unittest.TestCase):
    def test_agreed_five_argument_float_api(self):
        self.assertEqual(list(inspect.signature(equity).parameters),
                         ["hole", "board", "opp_ranges", "n_iters", "time_budget_ms"])
        result = equity(HOLE, BOARD, [{("7h", "6h"): 1}], 1000, 25)
        self.assertIsInstance(result, float)
        self.assertEqual(result, 1)
        self.assertEqual(equity(hole=HOLE, board=BOARD, opp_ranges=[], n_iters=1,
                                time_budget_ms=None), 1)

    def test_every_street_and_table_size_normalizes(self):
        for opponents in (1, 4, 8):
            for board in ([], ["Qs", "7s", "2d"], ["Qs", "7s", "2d", "3h"],
                          ["Qs", "7s", "2d", "3h", "9c"]):
                report = estimate_equity(["As", "Ks"], board, [None] * opponents,
                                         48, None, seed=4)
                self.assertEqual(len(report.players), opponents + 1)
                self.assertEqual(report.samples, 48)
                self.assertAlmostEqual(sum(p.equity for p in report.players), 1)
                for p in report.players:
                    self.assertAlmostEqual(p.win + p.tie + p.loss, 1)
                    self.assertEqual(set(p.hand_probabilities), set(HAND_NAMES))
                    self.assertAlmostEqual(sum(p.hand_probabilities.values()), 1)
                    self.assertTrue(all(0 <= q <= 1 for q in p.hand_probabilities.values()))

    def test_no_opponents_is_certain_without_simulation(self):
        with patch("bot.engine._evaluate", side_effect=AssertionError("Must not simulate")):
            result = estimate_equity(["As", "Ks"], [], [], 1, None)
        self.assertEqual(result.equity, 1)
        self.assertEqual(result.samples, 0)
        self.assertIsNone(result.players[0].hand_probabilities)

    def test_exact_uniform_heads_up_river_against_sdk(self):
        report = estimate_equity(HOLE, BOARD, [None], 1000, None)
        self.assertEqual(report.method, "exact")
        self.assertEqual(report.samples, 990)
        self.assertEqual(report.standard_error, 0)
        self.assertAlmostEqual(report.equity, reference_equity(HOLE, BOARD, [None]))

    def test_distinct_ranges_change_equity_without_stale_cache(self):
        weak, strong = {("7h", "6h"): 1}, {("Kh", "Qh"): 1}
        self.assertEqual(equity(HOLE, BOARD, [weak], 1, None), 1)
        self.assertEqual(equity(HOLE, BOARD, [strong], 1, None), 0)
        mixed = {("7h", "6h"): 3, ("Kh", "Qh"): 1}
        self.assertEqual(equity(HOLE, BOARD, [mixed], 1000, None), 0.75)
        scaled = {hand: w * 1e300 for hand, w in mixed.items()}
        self.assertEqual(equity(HOLE, BOARD, [scaled], 1000, None), 0.75)

    def test_blocked_and_zero_weight_combos_are_excluded(self):
        r = {("9h", "Kh"): 100, ("Ac", "Kd"): 100,
             ("7h", "6h"): 1, ("Kh", "Qh"): 0}
        report = estimate_equity(HOLE, BOARD, [r], 1000, None)
        self.assertEqual(report.equity, 1)
        self.assertEqual(report.samples, 1)

    def test_weighted_joint_enumeration_matches_product_measure(self):
        ranges = [{("Kh", "Qh"): 1, ("7h", "6h"): 3},
                  {("Kh", "5c"): 2, ("4c", "3c"): 1}]
        result = estimate_equity(HOLE, BOARD, ranges, 1000, None)
        self.assertEqual(result.samples, 3)
        self.assertAlmostEqual(result.equity, 0.3)
        self.assertAlmostEqual(result.equity, reference_equity(HOLE, BOARD, ranges))

    def test_monte_carlo_rejects_whole_assignment_without_seat_bias(self):
        # Three equiprobable compatible deals; only one wins. Sequentially
        # renormalizing the second range would incorrectly yield 1/4, not 1/3.
        ranges = [{("Kh", "Qh"): 1, ("7h", "6h"): 1},
                  {("Kh", "5c"): 1, ("4c", "3c"): 1}]
        for ordered in (ranges, list(reversed(ranges))):
            result = estimate_equity(HOLE, BOARD, ordered, 12000, 60000, seed=41)
            self.assertEqual(result.method, "monte_carlo")
            self.assertEqual(result.samples, 12000)
            self.assertGreater(result.attempts, result.samples)
            self.assertAlmostEqual(result.equity, 1 / 3, delta=6 * result.standard_error)
        ranges[0][("7h", "6h")] = 3
        ranges[1][("Kh", "5c")] = 2
        result = estimate_equity(HOLE, BOARD, ranges, 12000, 60000, seed=41)
        self.assertAlmostEqual(result.equity, 0.3, delta=6 * result.standard_error)

    def test_mixed_uniform_and_restricted_ranges(self):
        ranges = [{("7h", "6h"): 1}, None]
        result = estimate_equity(HOLE, BOARD, ranges, 1000, None)
        self.assertEqual(result.method, "exact")
        self.assertEqual(result.samples, comb(43, 2))
        expected = reference_equity(HOLE, BOARD, ranges)
        self.assertAlmostEqual(result.equity, expected)
        sampled = estimate_equity(HOLE, BOARD, ranges, 6000, 60000, seed=3)
        self.assertAlmostEqual(sampled.equity, expected, delta=6 * sampled.standard_error)

    def test_ranges_condition_future_board_and_hand_probabilities(self):
        hole, board = ["As", "Ks"], ["Qs", "7s", "2d"]
        ranges = [{("Js", "Ts"): 1}]
        result = estimate_equity(hole, board, ranges, 1000, None)
        self.assertEqual(result.samples, comb(45, 2))
        self.assertEqual(result.method, "exact")
        # Two spades are in the opponent's known hand, leaving seven, not nine.
        self.assertAlmostEqual(result.players[0].hand_probabilities["Flush"],
                               1 - comb(38, 2) / comb(45, 2))
        self.assertAlmostEqual(result.equity, reference_equity(hole, board, ranges))

    def test_joint_draws_share_board_and_never_reuse_cards(self):
        observed = []
        original = engine._evaluate
        def recording(cards):
            observed.append(tuple(cards))
            return original(cards)
        ranges = [{("Kh", "Qh"): 1, ("7h", "6h"): 1},
                  {("Kh", "5c"): 1, ("4c", "3c"): 1}] + [None] * 6
        with patch("bot.engine._evaluate", side_effect=recording):
            result = estimate_equity(["As", "Ks"], [], ranges, 32, None, seed=13)
        self.assertEqual(len(observed), 9 * result.samples)
        for start in range(0, len(observed), 9):
            deal = observed[start:start + 9]
            self.assertTrue(all(hand[2:] == deal[0][2:] for hand in deal))
            cards = [c for hand in deal for c in hand[:2]] + list(deal[0][2:])
            self.assertEqual(len(set(cards)), 23)

    def test_royal_board_ties_are_fractional_equity(self):
        for opponents in (1, 4, 8):
            result = estimate_equity(["2c", "3d"], ["As", "Ks", "Qs", "Js", "Ts"],
                                     [None] * opponents, 48, None, seed=8)
            self.assertAlmostEqual(result.equity, 1 / (opponents + 1))
            for player in result.players:
                self.assertEqual(player.win, 0)
                self.assertEqual(player.tie, 1)
                self.assertEqual(player.hand_probabilities["Royal Flush"], 1)

    def test_fixed_multiway_river_can_be_exact_with_time_budget(self):
        result = estimate_equity(HOLE, BOARD, [{("7h", "6h"): 1}, {("5c", "4c"): 1}],
                                 1, 1000)
        self.assertEqual(result.method, "exact")
        self.assertEqual(result.equity, 1)

    def test_incompatible_ranges_fail_explicitly(self):
        scenarios = [[{}], [{("9h", "Kh"): 1}], [{("Kh", "Qh"): 0}],
                     [{("Kh", "Qh"): 1}, {("Kh", "Jh"): 1}]]
        five_cards = ["Kh", "Qh", "Jh", "Th", "7h"]
        scenarios.append([dict.fromkeys(combinations(five_cards, 2), 1)] * 3)
        for ranges in scenarios:
            with self.assertRaises(ImpossibleRangeError):
                estimate_equity(HOLE, BOARD, ranges, 10, None)

    def test_zero_budget_and_expired_preprocessing_do_not_invent_equity(self):
        with patch("bot.engine._evaluate", side_effect=AssertionError("No budget")):
            with self.assertRaises(EquityTimeout):
                equity(HOLE, BOARD, [None], 100, 0)
        with patch("bot.engine.perf_counter", side_effect=[0, 0, 1]):
            with self.assertRaises(EquityTimeout):
                equity(HOLE, BOARD, [{("7h", "6h"): 1}], 100, 1)

    def test_deadline_returns_only_completed_samples(self):
        with patch("bot.engine.perf_counter", side_effect=[0, 0, 0, 0, 1]):
            result = estimate_equity(HOLE, BOARD, [None], 100, 1, seed=6)
        self.assertEqual(result.samples, 1)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.stop_reason, "time_budget")
        self.assertEqual(result.method, "monte_carlo")
        self.assertIsNone(result.standard_error)

    def test_rejection_loop_has_attempt_cap_without_a_deadline(self):
        ranges = [{("Kh", "Qh"): 1, ("7h", "6h"): 1},
                  {("Kh", "5c"): 1, ("4c", "3c"): 1}]
        with patch.object(engine._Range, "draw", lambda self, rng: (self.hands[0], self.masks[0])):
            with self.assertRaises(EquitySamplingError):
                estimate_equity(HOLE, BOARD, ranges, 1, None)

    def test_repeatability_and_no_input_or_global_rng_mutation(self):
        ranges = [None, {("Kh", "Qh"): 1, ("7h", "6h"): 3}]
        inputs = (HOLE[:], BOARD[:], ranges)
        before, rng_before = deepcopy(inputs), random.getstate()
        first = estimate_equity(*inputs, 64, None, seed=7)
        self.assertEqual(first, estimate_equity(*inputs, 64, None, seed=7))
        self.assertEqual(inputs, before)
        self.assertEqual(random.getstate(), rng_before)

    def test_invalid_inputs(self):
        for kwargs in (dict(n_iters=0), dict(n_iters=True), dict(seed="deck"),
                       dict(time_budget_ms=-1), dict(time_budget_ms=float("nan")),
                       dict(time_budget_ms="25")):
            with self.assertRaises(ValueError):
                estimate_equity(HOLE, BOARD, [None], **kwargs)
        for hole, board, ranges in ((["As", "As"], [], [None]),
                                    (HOLE, ["9h", "2c", "3c"], [None]),
                                    (["ZZ", "Kh"], [], [None]), (HOLE, ["2c"], [None]),
                                    (HOLE, [], [None] * 9), (HOLE, [], {0: None})):
            with self.assertRaises(ValueError):
                estimate_equity(hole, board, ranges, 1, None)
        for r in ("AA", {"AKs": 1}, {("Kh", "Kh"): 1},
                  {("Kh", "Qh"): 1, ("Qh", "Kh"): 2},
                  {("Kh", "Qh"): -1}, {("Kh", "Qh"): float("inf")},
                  {("Kh", "Qh"): True}, {("Kh", "Qh"): "1"}):
            with self.assertRaises(ValueError):
                estimate_equity(HOLE, BOARD, [r], 1, None)


class IntegrationTests(unittest.TestCase):
    def test_glue_excludes_folds_includes_all_ins_and_resets_each_call(self):
        bot = MyBot()
        s = state(folded=[False, False, True])
        with patch("bot.main.equity", return_value=0.7) as calculate:
            self.assertEqual(bot.act(s).kind, "check")
            self.assertEqual(calculate.call_args.args, (s.hole, s.board, [None], 256, 25))
        self.assertEqual(bot.last_equity, 0.7)
        s._m["clock_ms"] = 20
        with patch("bot.main.equity", side_effect=AssertionError("Low clock")):
            bot.act(s)
        self.assertIsNone(bot.last_equity)
        s._m["clock_ms"] = 1000
        with patch("bot.main.equity", side_effect=EquityTimeout):
            self.assertEqual(bot.act(s).kind, "check")
        self.assertIsNone(bot.last_equity)
        bot.on_hand_start({})
        self.assertIsNone(bot.last_equity)

    def test_sdk_can_load_submission_with_sibling_engine(self):
        self.assertIsInstance(load_bot_from_file(str(ROOT / "bot" / "main.py")), Bot)


if __name__ == "__main__":
    unittest.main()
