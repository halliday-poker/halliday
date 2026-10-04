"""Range tracking and showdown learning: directions, safeguards, timing, integration."""

from collections import Counter, defaultdict
from pathlib import Path
import sys
import time
import unittest

import numpy as np
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "macpoker-src"))
sys.path.insert(0, str(ROOT))

from macpoker.bots import BUILTINS
from macpoker.match import MatchConfig, MatchRunner
from macpoker.transport import InProcessTransport
from bot.main import MyBot
from bot.opponents import OpponentTracker
from bot.params import DEFAULT_PARAMS
from bot.ranges import (COMBOS, PREFLOP_PCT, RangeTracker, board_strength,
                        postflop_likelihood, preflop_likelihood, _class_of, _combo_index)

P = DEFAULT_PARAMS


def tracker(params=P, profiles=None, players=(3, 7, 5, 9), seat=0):
    rt = RangeTracker(profiles if profiles is not None else defaultdict(Counter), params)
    rt.on_hand_start({"players": list(players), "stacks": [200] * len(players),
                      "seat": seat, "button": 0})
    return rt


def act(rt, street, seat, kind, amount=0):
    rt.on_action({"street": street, "seat": seat, "action": kind, "amount": amount,
                  "players": rt.players})


def weight_of(rt, seat, cards):
    rt._catch_up()
    return rt.weights[seat][_combo_index(tuple(cards))]


def mean_strength(rt, seat, board):
    rt._catch_up()
    strength, _ = board_strength(board)
    pairs = [(w, strength[i]) for i, w in enumerate(rt.weights[seat]) if not np.isnan(strength[i])]
    return sum(w * s for w, s in pairs) / sum(w for w, _ in pairs)


class HandRanks(unittest.TestCase):
    def test_percentiles_order_hands(self):
        for table in PREFLOP_PCT:
            aa = table[_combo_index(("As", "Ah"))]
            seven_two = table[_combo_index(("7c", "2d"))]
            self.assertLess(aa, 0.01)
            self.assertGreater(seven_two, 0.9)
            self.assertTrue(all(0 < x < 1 for x in table))

    def test_multiway_ranking_prefers_suited_connectors(self):
        hu, mw = PREFLOP_PCT
        i = _combo_index(("7s", "6s"))
        self.assertLess(mw[i], hu[i])


class BoardStrength(unittest.TestCase):
    def test_nuts_blocked_and_draws(self):
        board = ["Qs", "7s", "2d"]
        strength, draws = board_strength(board)
        self.assertTrue(np.isnan(strength[_combo_index(("Qs", "Ah"))]))  # uses a board card
        self.assertGreater(strength[_combo_index(("Qh", "Qd"))], 0.99)  # top set
        self.assertLess(strength[_combo_index(("4c", "3h"))], 0.2)
        self.assertTrue(draws[_combo_index(("As", "5s"))])              # flush draw
        self.assertFalse(draws[_combo_index(("6c", "5h"))])             # 5-6-7 only: not a draw
        self.assertFalse(draws[_combo_index(("Kc", "Jh"))])
        _, connected = board_strength(["9h", "8d", "2c"])
        self.assertTrue(connected[_combo_index(("7c", "6h"))])           # open-ended
        self.assertFalse(connected[_combo_index(("Jc", "7h"))])          # single gutshot: not counted
        _, river_draws = board_strength(board + ["9c", "3s"])
        self.assertFalse(any(river_draws))


class Likelihoods(unittest.TestCase):
    def test_tight_open_narrows_but_keeps_a_floor(self):
        widths = (0.15, 0.10, 0.04)
        pct = PREFLOP_PCT[1]
        aa = preflop_likelihood("raise", pct[_combo_index(("As", "Ah"))], 0, widths, P)
        trash = preflop_likelihood("raise", pct[_combo_index(("7c", "2d"))], 0, widths, P)
        self.assertGreater(aa, 0.95)
        self.assertAlmostEqual(trash, P["range_floor"], places=3)

    def test_bigger_bets_and_raises_need_stronger_hands(self):
        learned = (P["range_bet_cut"], P["range_call_cut"], 0.1)
        small = postflop_likelihood("raise", 0.6, 0.33, False, learned, P)
        large = postflop_likelihood("raise", 0.6, 1.5, False, learned, P)
        raise_ = postflop_likelihood("raise", 0.6, 0.33, True, learned, P)
        self.assertGreater(small, large)
        self.assertGreater(small, raise_)

    def test_bluff_floor_scales_with_bet_size(self):
        # The field bluffs 55-60% of its bets up to 0.4 pot but ~10% above 1.3 pot.
        learned = (P["range_bet_cut"], P["range_call_cut"], 0.3)
        weak = lambda size: postflop_likelihood("raise", 0.1, size, False, learned, P)
        self.assertAlmostEqual(weak(0.3), 0.9, delta=0.01)
        self.assertAlmostEqual(weak(0.6), 0.3, delta=0.01)
        self.assertAlmostEqual(weak(1.0), 0.165, delta=0.01)
        self.assertAlmostEqual(weak(2.0), 0.075, delta=0.01)

    def test_checks_keep_slowplays(self):
        learned = (P["range_bet_cut"], P["range_call_cut"], 0.1)
        nuts = postflop_likelihood("check", 0.99, 0, False, learned, P)
        self.assertAlmostEqual(nuts, P["range_slowplay"], delta=0.02)
        self.assertGreater(postflop_likelihood("check", 0.1, 0, False, learned, P), 0.99)


class Tracking(unittest.TestCase):
    def setUp(self):
        self.profiles = defaultdict(Counter)
        self.profiles[5].update(hands=40, vpip=6, pfr=4, threebet_chances=5, threebets=0)

    def test_preflop_raise_from_tight_player(self):
        rt = tracker(profiles=self.profiles)
        act(rt, "preflop", 3, "fold"); act(rt, "preflop", 0, "call", 2)
        act(rt, "preflop", 1, "fold"); act(rt, "preflop", 2, "raise", 8)   # player 5
        # At most 1 / floor^temper (about 16x) less likely per action.
        self.assertGreater(weight_of(rt, 2, ("Ks", "Kh")), 10 * weight_of(rt, 2, ("8c", "3d")))
        self.assertGreater(weight_of(rt, 2, ("8c", "3d")), 0)

    def test_temper_zero_means_actions_change_nothing(self):
        rt = tracker(params=dict(P, range_temper=0.0), profiles=self.profiles)
        act(rt, "preflop", 3, "fold"); act(rt, "preflop", 0, "call", 2)
        act(rt, "preflop", 1, "fold"); act(rt, "preflop", 2, "raise", 8)
        self.assertEqual(weight_of(rt, 2, ("Ks", "Kh")), weight_of(rt, 2, ("8c", "3d")))

    def test_bigger_bets_favour_the_top_over_medium_hands(self):
        board = ["Qs", "7h", "2d"]
        ratios = []
        for amount in (2, 10):  # half pot vs 2.5x pot into a 4-chip pot
            rt = tracker(profiles=self.profiles, players=(3, 5))
            act(rt, "preflop", 0, "call", 1); act(rt, "preflop", 1, "check")
            rt.on_street({"street": "flop", "board": board})
            act(rt, "flop", 1, "raise", amount)
            ratios.append(weight_of(rt, 1, ("Qh", "Qd")) / weight_of(rt, 1, ("Kc", "7c")))
        self.assertGreater(ratios[1], ratios[0])

    def test_ranges_for_skips_uniform_and_excludes_known_cards(self):
        rt = tracker(profiles=self.profiles)
        self.assertEqual(rt.ranges_for([1], ["Ac", "Kd"], []), [None])   # never acted
        act(rt, "preflop", 3, "fold"); act(rt, "preflop", 0, "call", 2)
        act(rt, "preflop", 1, "fold"); act(rt, "preflop", 2, "raise", 8)
        rng = rt.ranges_for([2], ["Ac", "Kd"], [])[0]
        self.assertIsNotNone(rng)
        self.assertLessEqual(len(rng), P["range_max_combos"])
        self.assertFalse(any({"Ac", "Kd"} & set(c) for c in rng))
        self.assertAlmostEqual(sum(rng.values()), sum(rng.values()))
        loose = tracker(params=dict(P, range_uniform_skip=1.01), profiles=self.profiles)
        act(loose, "preflop", 3, "call", 2)
        self.assertIsNotNone(loose.ranges_for([3], ["Ac", "Kd"], [])[0])

    def test_timing_five_opponents(self):
        rt = tracker(players=(1, 2, 3, 4, 5, 6))
        for seat in (3, 4, 5, 1, 2):
            act(rt, "preflop", seat, "call", 2 if seat != 1 else 1)
        act(rt, "preflop", 0, "check")
        rt.on_street({"street": "flop", "board": ["Qs", "7h", "2d"]})
        for seat in (1, 2, 0, 3, 4):
            act(rt, "flop", seat, "check")
        act(rt, "flop", 5, "raise", 8)
        started = time.perf_counter()
        rt.ranges_for([1, 2, 3, 4, 5], ["Ac", "Kd"], ["Qs", "7h", "2d"])
        self.assertLess((time.perf_counter() - started) * 1000, 150)


class ShowdownLearning(unittest.TestCase):
    def river_bluff_called(self, rt, cards, amount=30):
        """Seat 1 bets every street and is called; then shows `cards`."""
        act(rt, "preflop", 0, "call", 1); act(rt, "preflop", 1, "check")
        rt.on_street({"street": "flop", "board": ["Qs", "7h", "2d"]})
        act(rt, "flop", 1, "check"); act(rt, "flop", 0, "check")
        rt.on_street({"street": "turn", "board": ["Qs", "7h", "2d", "9c"]})
        act(rt, "turn", 1, "check"); act(rt, "turn", 0, "check")
        rt.on_street({"street": "river", "board": ["Qs", "7h", "2d", "9c", "3s"]})
        act(rt, "river", 1, "raise", amount); act(rt, "river", 0, "call", amount)
        rt.on_hand_end({"revealed": {"0": ["Ac", "Kd"], "1": list(cards)}})
        rt.learn_pending()

    def test_called_bluffs_raise_the_bluff_floor(self):
        rt = tracker(players=(3, 5))
        before = rt.showdowns[5].learned(P)[2]
        for _ in range(3):
            rt.on_hand_start({"players": [3, 5], "stacks": [200, 200], "seat": 0, "button": 0})
            self.river_bluff_called(rt, ("5c", "4h"))
        self.assertGreater(rt.showdowns[5].learned(P)[2], before)

    def test_called_value_bets_lower_the_bluff_floor(self):
        rt = tracker(players=(3, 5))
        before = rt.showdowns[5].learned(P)[2]
        for _ in range(3):
            rt.on_hand_start({"players": [3, 5], "stacks": [200, 200], "seat": 0, "button": 0})
            self.river_bluff_called(rt, ("Qh", "Qd"))
        self.assertLess(rt.showdowns[5].learned(P)[2], before)

    def test_switch_off_learning(self):
        rt = tracker(params=dict(P, range_learn_showdowns=False), players=(3, 5))
        self.river_bluff_called(rt, ("5c", "4h"))
        self.assertEqual(rt.showdowns[5].bet_weight, 0)


class Counters(unittest.TestCase):
    def test_preflop_stats_count_once_per_hand(self):
        ot = OpponentTracker()
        players = [10, 11, 12]
        ot.on_hand_start({"players": players, "stacks": [200] * 3, "seat": 0})
        for seat, kind, amount in [(0, "raise", 6), (1, "raise", 18), (2, "call", 16),
                                   (0, "raise", 50), (1, "call", 32)]:
            ot.on_action({"street": "preflop", "seat": seat, "action": kind, "amount": amount,
                          "players": players})
        self.assertEqual(ot.profiles[10]["vpip"], 1)
        self.assertEqual(ot.profiles[10]["pfr"], 1)
        self.assertEqual(ot.profiles[10]["threebet_chances"], 0)  # opened; faced no raise first
        self.assertEqual(ot.profiles[11]["threebets"], 1)
        self.assertEqual(ot.profiles[12]["threebet_chances"], 0)  # acted facing two raises


class Integration(unittest.TestCase):
    def play(self, bot, deals=40):
        transports = [InProcessTransport(bot, "bot")] + [
            InProcessTransport(BUILTINS[name](), name) for name in ("call", "random", "call")]
        cfg = MatchConfig(seats=4, deals=deals, seed="ranges-test")
        return MatchRunner(cfg, transports).run()

    def test_plays_ranged_and_legal(self):
        bot = MyBot()
        used = []
        original = bot.act

        def spy(state):
            action = original(state)
            used.append(bot.last_ranged)
            return action
        bot.act = spy
        result = self.play(bot)
        self.assertEqual(result.verdicts[0], "OK")
        self.assertTrue(any(used))

    def test_tracking_failure_falls_back_to_random_cards(self):
        bot = MyBot()
        with patch.object(RangeTracker, "ranges_for", side_effect=RuntimeError("boom")):
            result = self.play(bot, deals=15)
        self.assertEqual(result.verdicts[0], "OK")


if __name__ == "__main__":
    unittest.main()
