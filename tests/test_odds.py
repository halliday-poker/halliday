"""Independent evaluator checks and probability/engine regression cases."""

from copy import deepcopy
from itertools import combinations
from pathlib import Path
from random import Random
import random
import sys
import unittest
from unittest.mock import patch

# Local tests use the checked-in SDK without installing runtime dependencies.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "macpoker-src"))
sys.path.insert(0, str(ROOT))

from macpoker import Bot, GameState
from macpoker.cards import parse_cards
from macpoker.evaluator import evaluate as sdk_evaluate
from macpoker.sdk import load_bot_from_file
from bot.main import HAND_NAMES, MyBot, _category, _evaluate


def view(hole=("As", "Ks"), board=(), n=3, **overrides):
    message = dict(
        hole=list(hole), board=list(board), players=list(range(n)),
        folded=[False] * n, seat=0, stacks=[190] * n, pot=10 * n,
        to_call=0, button=0, hand=1, clock_ms=30000, street_bets=[0] * n,
        history=[], min_raise_to=2, max_raise_to=190, can_raise=True,
    )
    message.update(overrides)
    return GameState(message)


def sdk_category(cards):
    value = sdk_evaluate(list(cards))
    return 9 if value == (8, 12) else value[0]


class EvaluatorTests(unittest.TestCase):
    def test_categories_and_tricky_kickers_match_sdk(self):
        hands = [
            "As Ks Qs Js Ts 2d 2c", "As 2s 3s 4s 5s Kd Qh",
            "As Ah Ac Ad Ks Qs Js", "As Ah Ac Ks Kh Kc 2d",
            "As 9s 7s 5s 3s Ks Qs", "As 2c 3h 4d 5s 6h 7s",
            "As Ah Ac Ks Qs Js 9s", "As Ah Ks Kh Qs Qh 2s",
            "As Ah Ks Qh Js 9h 2c", "As Kd Qh Js 9c 8h 2d",
        ]
        for text in hands:
            cards = parse_cards(text.split())
            value = _evaluate(cards)
            self.assertEqual((value[0], *(r - 2 for r in value[1:])), sdk_evaluate(cards))
            self.assertEqual(_category(value), sdk_category(cards))

    def test_random_five_six_seven_card_hands_match_sdk(self):
        rng = Random(712)
        for size in (5, 6, 7):
            for _ in range(500):
                cards = rng.sample(range(52), size)
                value = _evaluate(cards)
                self.assertEqual((value[0], *(r - 2 for r in value[1:])), sdk_evaluate(cards))


class OddsTests(unittest.TestCase):
    def setUp(self):
        self.bot = MyBot()

    def test_every_street_and_table_size_normalizes(self):
        for n in (2, 5, 9):
            for board in ((), ("Qs", "7s", "2d"), ("Qs", "7s", "2d", "3h"),
                          ("Qs", "7s", "2d", "3h", "9c")):
                state = view(board=board, n=n, players=list(reversed(range(n))))
                report = self.bot.calculate_odds(state, samples=48, seed=4)
                self.assertEqual(report["hero"], n - 1)
                self.assertAlmostEqual(sum(p["equity"] for p in report["players"].values()), 1)
                for player, row in report["players"].items():
                    self.assertEqual(row["seat"], n - player - 1)
                    self.assertEqual(set(row["hand_probabilities"]), set(HAND_NAMES))
                    self.assertAlmostEqual(sum(row["hand_probabilities"].values()), 1)
                    self.assertAlmostEqual(row["win"] + row["tie"] + row["loss"], 1)
                    self.assertTrue(all(0 <= p <= 1 for p in row["hand_probabilities"].values()))
                    self.assertEqual(row["hand_method"], "exact" if (board and player == n - 1) or len(board) == 5 else "monte_carlo")
                rows = list(report["players"].values())
                self.assertTrue(all(row["hand_probabilities"] == rows[1]["hand_probabilities"] for row in rows[1:]))

    def test_flop_distribution_matches_independent_sdk_enumeration(self):
        state = view(board=("Qs", "7s", "2d"))
        cards = parse_cards(state.hole + state.board)
        remaining = [c for c in range(52) if c not in cards]
        counts = [0] * 10
        for runout in combinations(remaining, 2):
            counts[sdk_category(cards + list(runout))] += 1
        report = self.bot.calculate_odds(state, samples=32, seed=8)
        hero = report["players"][0]
        self.assertEqual(hero["hand_evaluations"], 1081)
        for name, count in zip(HAND_NAMES, counts):
            self.assertEqual(hero["hand_probabilities"][name], count / 1081)
        self.assertAlmostEqual(report["hero_draws"]["at_least_by_river"]["Flush"], 378 / 1081)

    def test_turn_flush_outs_and_improvement(self):
        report = self.bot.calculate_odds(view(board=("Qs", "7s", "2d", "3h")), samples=32, seed=8)
        hero = report["players"][0]
        self.assertEqual(hero["hand_evaluations"], 46)
        self.assertEqual(hero["hand_probabilities"]["Flush"], 9 / 46)
        draws = report["hero_draws"]
        self.assertEqual(draws["current_hand"], "High Card")
        self.assertEqual(draws["next_card"]["hand_probabilities"], hero["hand_probabilities"])
        self.assertAlmostEqual(draws["category_improvement_by_river"], 1 - hero["hand_probabilities"]["High Card"])
        self.assertTrue({"2s", "3s", "4s", "5s", "6s", "8s", "9s", "Ts", "Js"}.issubset(draws["next_card"]["category_improvement_cards"]))

    def test_exact_river_blockers_kickers_and_heads_up(self):
        state = view(hole=("9h", "8h"), board=("Ac", "Ad", "Ah", "As", "2d"), n=2)
        report = self.bot.calculate_odds(state, samples=1, seed=8)
        cards = parse_cards(state.hole + state.board)
        remaining = [c for c in range(52) if c not in cards]
        hero_value = sdk_evaluate(cards)
        counts = [0, 0, 0]
        for pair in combinations(remaining, 2):
            value = sdk_evaluate(list(pair) + parse_cards(state.board))
            counts[0 if hero_value > value else 1 if hero_value == value else 2] += 1
        self.assertEqual(report["showdown_method"], "exact")
        self.assertEqual(report["showdown_trials"], 990)
        self.assertEqual(report["sampled_deals"], 0)
        hero = report["players"][0]
        self.assertEqual(hero["hand_probabilities"]["Four of a Kind"], 1)
        self.assertEqual(hero["win"], counts[0] / 990)
        self.assertEqual(hero["tie"], counts[1] / 990)
        self.assertEqual(hero["loss"], counts[2] / 990)
        self.assertEqual(hero["equity_standard_error"], 0)
        self.assertEqual(report["hero_heads_up"][1]["win"], hero["win"])

    def test_royal_board_ties_all_in_and_folded_players(self):
        state = view(hole=("2c", "3d"), board=("As", "Ks", "Qs", "Js", "Ts"),
                     n=4, folded=[False, False, True, False], stacks=[0] * 4, pot=800)
        report = self.bot.calculate_odds(state, samples=64, seed=12)
        for player, row in report["players"].items():
            self.assertEqual(row["hand_probabilities"]["Royal Flush"], 1)
            self.assertEqual(row["win"], 0)
            self.assertEqual(row["tie"], 0 if player == 2 else 1)
            self.assertAlmostEqual(row["equity"], 0 if player == 2 else 1 / 3)
        self.assertEqual(set(report["hero_heads_up"]), {1, 3})
        self.assertTrue(all(r["method"] == "exact" for r in report["hero_heads_up"].values()))
        self.assertEqual(report["strategy"]["checkdown_expected_payout"], 266)

    def test_last_player_standing_even_when_hero_folded(self):
        for board in ((), ("Qs", "7s", "2d"), ("Qs", "7s", "2d", "3h", "9c")):
            for winner in (0, 1):
                report = self.bot.calculate_odds(view(board=board, folded=[s != winner for s in range(3)]), samples=32, seed=9)
                self.assertEqual(report["showdown_method"], "exact")
                self.assertEqual(report["players"][winner]["win"], 1)
                self.assertEqual(report["players"][winner]["equity"], 1)
                self.assertEqual(report["strategy"]["checkdown_expected_payout"], 30 if winner == 0 else 0)

    def test_side_pots_refunds_and_capped_call_cost(self):
        state = view(hole=("2c", "3d"), board=("As", "Ks", "Qs", "Js", "Ts"),
                     n=4, stacks=[10, 100, 0, 170], pot=370, to_call=100,
                     folded=[False, False, False, True])
        report = self.bot.calculate_odds(state, samples=32, seed=2, starting_stacks=[50, 200, 200, 200])
        strategy = report["strategy"]
        self.assertEqual(strategy["call_cost"], 10)
        self.assertEqual(strategy["pot_odds"], 10 / 380)
        self.assertEqual([p["amount"] for p in strategy["pots_after_call"]], [120, 60, 100])
        self.assertEqual(strategy["pots_after_call"][-1]["eligible_players"], [1, 2])
        self.assertEqual(strategy["pots_after_call"][-1]["hero_equity"], 0)
        self.assertEqual(strategy["checkdown_expected_payout"], 60)
        self.assertEqual(strategy["checkdown_call_ev"], 50)

    def test_folded_money_and_odd_chip_order(self):
        state = view(hole=("2c", "3d"), board=("As", "Ks", "Qs", "Js", "Ts"),
                     n=4, stacks=[197, 197, 197, 199], pot=10,
                     folded=[False, False, False, True])
        report = self.bot.calculate_odds(state, samples=32, seed=2)
        self.assertEqual(report["strategy"]["checkdown_expected_payout"], 3)
        state._m["button"] = 3
        report = self.bot.calculate_odds(state, samples=32, seed=2)
        self.assertEqual(report["strategy"]["checkdown_expected_payout"], 4)

    def test_uncalled_hero_bet_is_refunded(self):
        report = self.bot.calculate_odds(view(stacks=[150, 180, 190], pot=80,
                                             folded=[False, True, True]), samples=16, seed=3)
        self.assertEqual(report["strategy"]["uncalled_refund"], 30)
        self.assertEqual(report["strategy"]["checkdown_expected_payout"], 80)

    def test_joint_samples_use_one_board_and_no_duplicate_cards(self):
        evaluated = []
        def evaluate(cards):
            evaluated.append(tuple(cards))
            return _evaluate(cards)
        with patch("bot.main._evaluate", side_effect=evaluate):
            report = self.bot.calculate_odds(view(n=9), samples=20, seed=13)
        self.assertEqual(report["sampled_deals"], 20)
        for start in range(0, len(evaluated), 9):
            deal = evaluated[start:start + 9]
            self.assertTrue(all(h[2:] == deal[0][2:] for h in deal))
            cards = [c for h in deal for c in h[:2]] + list(deal[0][2:])
            self.assertEqual(len(set(cards)), 23)

    def test_seed_reproducibility_and_no_mutation(self):
        state = view()
        before, rng_before = deepcopy(state.raw()), random.getstate()
        first = self.bot.calculate_odds(state, samples=64, seed=17)
        second = self.bot.calculate_odds(state, samples=64, seed=17)
        self.assertEqual(first, second)
        self.assertEqual(before, state.raw())
        self.assertEqual(rng_before, random.getstate())
        self.assertIsNone(self.bot.last_odds)
        self.assertIsNone(self.bot.calculate_odds(state, samples=1, seed=9)["players"][0]["equity_standard_error"])

    def test_time_budget_stops_sampling_without_changing_exact_pass(self):
        with patch("bot.main.perf_counter", side_effect=[0, 1]):
            report = self.bot.calculate_odds(view(board=("Qs", "7s", "2d")), samples=1000,
                                             seed=9, time_budget_ms=1)
        self.assertEqual(report["sampled_deals"], 16)
        self.assertEqual(report["players"][0]["hand_evaluations"], 1081)

    def test_hooks_cache_money_changes_and_low_clock(self):
        state = view()
        self.bot.act(state)
        original = self.bot.last_odds
        self.assertIsNotNone(original)
        self.bot.act(state)
        self.assertIs(self.bot.last_odds, original)
        state._m.update(pot=40, to_call=10, stacks=[190, 180, 190])
        self.bot.act(state)
        self.assertIsNot(self.bot.last_odds, original)
        self.assertEqual(self.bot.last_odds["strategy"]["call_cost"], 10)
        self.bot.on_hand_start(dict(hand=2, players=[2, 0, 1], stacks=[50] * 3))
        self.assertIsNone(self.bot.last_odds)
        state = view(hand=2, players=[2, 0, 1], stacks=[40] * 3)
        self.bot.act(state)
        self.assertEqual(self.bot.last_odds["hero"], 2)
        self.bot.on_match_start(dict(stack=100))
        self.assertIsNone(self.bot.last_odds)
        state = view(stacks=[90] * 3, clock_ms=20)
        self.bot.act(state)
        self.assertIsNone(self.bot.last_odds)
        state._m["clock_ms"] = 30000
        self.bot.act(state)
        self.assertIsNotNone(self.bot.last_odds)
        self.assertIsInstance(load_bot_from_file(str(ROOT / "bot" / "main.py")), Bot)

    def test_invalid_inputs_fail_clearly(self):
        for kwargs in ({"samples": 0}, {"samples": True}, {"seed": "deck"},
                       {"time_budget_ms": -1}, {"time_budget_ms": float("nan")},
                       {"starting_stacks": [10, 10, 10]}):
            with self.assertRaises(ValueError):
                self.bot.calculate_odds(view(), **kwargs)
        for changes in (dict(hole=["As", "As"]), dict(board=["As", "2d", "3c"]),
                        dict(hole=["Az", "Ks"]), dict(board=["2d"]),
                        dict(folded=[True] * 3), dict(players=[0, 0, 1]),
                        dict(seat=9), dict(pot=100)):
            with self.assertRaises(ValueError):
                self.bot.calculate_odds(view(**changes), samples=1)


if __name__ == "__main__":
    unittest.main()
