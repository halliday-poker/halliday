"""Fixed-policy regressions, engine integration, and raw-action legality."""

from collections import Counter
from copy import deepcopy
from pathlib import Path
from random import Random
from types import SimpleNamespace
import random
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "macpoker-src"))
sys.path.insert(0, str(ROOT))

from macpoker import GameState
from macpoker.hand import Sink, play_hand
from bot.main import MyBot
from bot.opponents import OpponentTracker
from bot.params import DEFAULT_PARAMS
from bot.preflop import OPEN_RANGES, expand_range, hand_class, in_position, position, pot_odds
from bot.strategy import bet, board_texture, decide, has_draw, legal_raise


def state(**updates):
    msg = dict(hole=["As", "Ah"], board=[], players=list(range(6)), seat=3,
               button=0, folded=[False] * 6, stacks=[200, 199, 198, 200, 200, 200],
               pot=3, to_call=2, hand=1, clock_ms=30000, street="preflop",
               street_bets=[0, 1, 2, 0, 0, 0], history=[], can_raise=True,
               min_raise_to=4, max_raise_to=200)
    msg.update(updates)
    return GameState(msg)


def postflop(**updates):
    msg = dict(board=["Ac", "7h", "2d"], hole=["As", "Kh"], seat=0,
               stacks=[190, 170], players=[0, 1], folded=[False, False],
               street_bets=[0, 0], pot=40, to_call=0, min_raise_to=2,
               max_raise_to=190, street="flop", history=[])
    msg.update(updates)
    return state(**msg)


class PreflopTests(unittest.TestCase):
    def test_parser_and_all_169_classes(self):
        self.assertEqual(expand_range("QQ+,ATs+,AKo"),
                         {"QQ", "KK", "AA", "ATs", "AJs", "AQs", "AKs", "AKo"})
        classes = set()
        deck = [r + s for r in "23456789TJQKA" for s in "cdhs"]
        counts = {}
        for i, a in enumerate(deck):
            for b in deck[i + 1:]:
                name = hand_class([a, b])
                self.assertEqual(name, hand_class([b, a]))
                classes.add(name)
                counts[name] = counts.get(name, 0) + 1
        self.assertEqual(len(classes), 169)
        self.assertEqual((counts["AA"], counts["AKs"], counts["AKo"]), (6, 4, 12))
        for ranges in OPEN_RANGES.values():
            self.assertTrue(ranges <= classes)
        for bad in ("", "AK", "AAo", "2As", "ZQs", "K9s-K7s", "AQx"):
            with self.assertRaises(ValueError):
                expand_range(bad)

    def test_positions_rotate_and_heads_up_button_is_small_blind(self):
        names = ["button", "small_blind", "big_blind", "early", "middle", "cutoff"]
        for button in range(6):
            for offset, expected in enumerate(names):
                s = state(button=button, seat=(button + offset) % 6)
                self.assertEqual(position(s), expected)
        s = state(stacks=[199, 198], players=[0, 1], seat=0)
        self.assertEqual(position(s), "heads_up")
        self.assertEqual(position(s, 1), "big_blind")
        self.assertTrue(in_position(s, 1))

    def test_opens_position_and_limper_sizing(self):
        self.assertEqual(decide(state(), None).to_wire(), {"action": "raise", "amount": 5})
        self.assertEqual(decide(state(history=[["preflop", 4, "call", 2]]), None).amount, 7)
        self.assertEqual(decide(state(hole=["As", "8d"]), None).kind, "fold")
        self.assertEqual(decide(state(hole=["As", "8d"], seat=0), None).kind, "raise")
        self.assertEqual(decide(state(hole=["7s", "2d"], seat=2, to_call=0), None).kind, "check")

    def test_threebet_and_fourbet_use_raise_to_and_position(self):
        s = state(seat=0, pot=8, to_call=5, min_raise_to=8,
                  street_bets=[0, 1, 2, 5, 0, 0], history=[["preflop", 3, "raise", 5]])
        self.assertEqual(decide(s, None).amount, 15)
        s._m.update(seat=1, to_call=4)
        self.assertEqual(decide(s, None).amount, 20)
        s._m.update(seat=3, to_call=10, min_raise_to=25,
                    street_bets=[15, 1, 2, 5, 0, 0],
                    history=[["preflop", 3, "raise", 5], ["preflop", 0, "raise", 15]])
        self.assertEqual(decide(s, None).amount, 34)
        s._m["hole"] = ["7s", "2d"]
        self.assertEqual(decide(s, 0.99).kind, "fold")

    def test_blind_defence_and_expensive_calls(self):
        s = state(hole=["9s", "8s"], seat=2, to_call=3, pot=8,
                  street_bets=[5, 1, 2, 0, 0, 0], history=[["preflop", 0, "raise", 5]])
        self.assertEqual(decide(s, None).kind, "call")
        s._m.update(to_call=98, street_bets=[100, 1, 2, 0, 0, 0],
                    history=[["preflop", 0, "raise", 100]])
        self.assertEqual(decide(s, 0.80).kind, "fold")

    def test_all_in_call_requires_a_strong_hand_and_equity(self):
        s = state(hole=["Qs", "Qh"], to_call=200, pot=203, can_raise=False,
                  street_bets=[200, 1, 2, 0, 0, 0], history=[["preflop", 0, "raise", 200]])
        self.assertEqual(decide(s, 0.80).kind, "call")
        self.assertEqual(decide(s, 0.40).kind, "fold")
        self.assertEqual(decide(s, None).kind, "fold")
        s._m["hole"] = ["As", "Ah"]
        self.assertEqual(decide(s, None).kind, "call")


    def test_value_fourbets_and_threebet_flats_ignore_position(self):
        # Ladder 3-bets are mostly value (corrected replays), so no wider ranges.
        s = state(seat=3, pot=23, to_call=10, min_raise_to=25,
                  street_bets=[15, 1, 2, 5, 0, 0],
                  history=[["preflop", 3, "raise", 5], ["preflop", 0, "raise", 15]])
        for hole in (["Ks", "Kh"], ["As", "Ks"]):
            s._m["hole"] = hole
            self.assertEqual(decide(s, None).to_wire(), {"action": "raise", "amount": 34})
        for hole in (["Qs", "Qh"], ["As", "Kd"]):
            s._m["hole"] = hole
            self.assertEqual(decide(s, None).kind, "call")
        s._m["hole"] = ["8s", "8d"]
        self.assertEqual(decide(s, None).kind, "fold")  # out of position
        s = state(seat=0, hole=["8s", "8d"], pot=23, to_call=10, min_raise_to=25,
                  street_bets=[5, 1, 15, 0, 0, 0],
                  history=[["preflop", 0, "raise", 5], ["preflop", 2, "raise", 15]])
        self.assertEqual(decide(s, None).kind, "fold")  # in position too

    def test_proven_shover_is_called_with_any_hand_beating_the_price(self):
        folds = [["preflop", seat, "fold", 0] for seat in (4, 5, 0, 1)]
        s = state(seat=2, hole=["As", "5d"], pot=203, to_call=198, can_raise=False,
                  stacks=[200, 199, 198, 0, 200, 200], street_bets=[0, 1, 2, 200, 0, 0],
                  folded=[True, True, False, False, True, True],
                  history=[["preflop", 3, "raise", 200]] + folds)
        shover = {3: Counter(hands=10, shoves=4)}
        self.assertEqual(decide(s, 0.55, shover).kind, "call")
        self.assertEqual(decide(s, 0.50, shover).kind, "fold")  # below price + margin
        self.assertEqual(decide(s, 0.55).kind, "fold")  # unknown shover
        self.assertEqual(decide(s, 0.55, {3: Counter(hands=10, shoves=2)}).kind, "fold")
        s._m["history"] = [["preflop", 3, "raise", 200], ["preflop", 4, "call", 200]]
        self.assertEqual(decide(s, 0.55, shover).kind, "fold")  # someone else called


class OpponentTrackerTests(unittest.TestCase):
    def test_counts_shoves_and_responses_to_postflop_bets(self):
        t = OpponentTracker()
        players = [10, 11, 12]
        t.on_hand_start({"players": players, "stacks": [200, 200, 200]})
        t.on_action({"seat": 1, "street": "preflop", "action": "raise", "amount": 200, "players": players})
        t.on_street({"street": "flop", "players": players})
        for seat, kind, amount in ((0, "check", 0), (2, "raise", 10), (0, "call", 10), (1, "fold", 0)):
            t.on_action({"seat": seat, "street": "flop", "action": kind, "amount": amount, "players": players})
        self.assertEqual(t.profiles[11]["shoves"], 1)
        self.assertEqual((t.profiles[10]["faced"], t.profiles[10]["call"]), (1, 1))
        self.assertEqual((t.profiles[11]["faced"], t.profiles[11]["fold"]), (1, 1))
        self.assertEqual(t.profiles[12]["faced"], 0)  # bet into an unbet pot
        self.assertEqual(t.profiles[10]["hands"], 1)

    def test_counts_responses_to_our_own_bets(self):
        t = OpponentTracker()
        players = [10, 11, 12]
        t.on_hand_start({"players": players, "stacks": [200, 200, 200], "seat": 0})
        t.on_street({"street": "flop", "players": players})
        for seat, kind, amount in ((0, "raise", 10), (1, "call", 10), (2, "raise", 30),
                                   (0, "call", 20), (1, "fold", 0)):
            t.on_action({"seat": seat, "street": "flop", "action": kind, "amount": amount, "players": players})
        self.assertEqual((t.profiles[11]["faced_us"], t.profiles[11]["call_us"]), (1, 1))
        self.assertEqual(t.profiles[11]["fold_us"], 0)  # folded to seat 2's raise, not ours
        self.assertEqual((t.profiles[12]["faced_us"], t.profiles[12]["raise_us"]), (1, 1))
        self.assertEqual(t.profiles[10]["faced_us"], 0)

    def test_malformed_events_never_raise(self):
        bot = MyBot()
        for event in ({}, {"seat": 9, "street": "flop"}, {"players": None}, None):
            bot.on_hand_start(event or {})
            bot.on_action(event or {})
            bot.on_street(event or {})
        self.assertEqual(bot.act(state()).kind, "raise")


class PostflopTests(unittest.TestCase):
    def test_value_check_call_raise_and_fold(self):
        s = postflop()
        self.assertEqual(decide(s, 0.80).to_wire(), {"action": "raise", "amount": 16})
        self.assertEqual(decide(s, 0.35).kind, "check")
        s._m.update(to_call=10, street_bets=[0, 10], min_raise_to=20)
        self.assertEqual(decide(s, 0.10).kind, "fold")
        self.assertEqual(decide(s, 0.50).kind, "call")
        self.assertEqual(decide(s, 0.92).to_wire(), {"action": "raise", "amount": 48})

    def test_sizing_respects_prior_contributions_and_short_all_ins(self):
        s = postflop(to_call=20, street_bets=[10, 30], pot=100, min_raise_to=50)
        self.assertEqual(bet(s, 0.5).amount, 90)
        s._m.update(min_raise_to=45, max_raise_to=45)
        self.assertEqual(legal_raise(s, 200).amount, 45)
        s._m["can_raise"] = False
        self.assertEqual(legal_raise(s, 200).kind, "call")
        s._m["to_call"] = 0
        self.assertEqual(legal_raise(s, 200).kind, "check")

    def test_pot_odds_exclude_chips_hero_cannot_win(self):
        s = postflop(pot=110, to_call=20, street_bets=[0, 100])
        self.assertAlmostEqual(pot_odds(s), 20 / 50)

    def test_draws_and_wet_boards(self):
        self.assertFalse(board_texture(["As", "7h", "2d"]))
        self.assertTrue(board_texture(["As", "7s", "2d"]))
        self.assertTrue(board_texture(["9s", "8h", "7d"]))
        self.assertTrue(has_draw(["As", "Ks"], ["Qs", "7s", "2d"]))
        self.assertTrue(has_draw(["9s", "8h"], ["7d", "6c", "2d"]))
        self.assertFalse(has_draw(["As", "Kh"], ["Qd", "Jc", "2d"]))
        self.assertFalse(has_draw(["As", "Ks"], ["Qs", "7s", "2d", "3c", "4h"]))

    def test_heads_up_flop_cbet_is_pot_sized_with_any_hand(self):
        s = postflop(history=[["preflop", 0, "raise", 5]])
        for equity in (0.10, 0.45, 0.80):  # one size for air and value
            self.assertEqual(decide(s, equity).to_wire(), {"action": "raise", "amount": 40})
        s._m.update(board=["Qc", "Qh", "2d"])
        self.assertEqual(decide(s, 0.10).amount, 40)
        s._m["history"] = [["preflop", 1, "raise", 5]]  # no initiative
        self.assertEqual(decide(s, 0.45).kind, "check")
        s._m.update(history=[["preflop", 0, "raise", 5]], board=["Ac", "7h", "2d", "9s"])
        self.assertEqual(decide(s, 0.45).kind, "check")  # flop only
        s._m.update(board=["Ac", "7h", "2d"], players=[0, 1, 2], stacks=[190, 190, 190],
                    folded=[False] * 3, street_bets=[0] * 3)
        self.assertEqual(decide(s, 0.45).kind, "check")  # multiway: value only

    def test_station_gets_no_bluff_cbet(self):
        s = postflop(history=[["preflop", 0, "raise", 5]])
        profiles = {1: Counter(hands=20, faced=10, call=10)}
        self.assertEqual(decide(s, 0.10, profiles).kind, "check")
        self.assertEqual(decide(s, 0.80, profiles).amount, 40)  # value still bets
        profiles[1].update(fold=4)  # folds 4 of 10: not a station
        self.assertEqual(decide(s, 0.10, profiles).kind, "raise")

    def test_bluffs_stop_once_an_opponent_calls_our_bets(self):
        s = postflop(hole=["Ks", "Qh"], history=[["preflop", 0, "raise", 5]])  # air
        profiles = {1: Counter(hands=10, faced_us=1, call_us=1)}
        self.assertEqual(decide(s, 0.10, profiles).amount, 40)  # one call is not enough
        profiles[1].update(faced_us=1, call_us=1)  # called our last two bets
        self.assertEqual(decide(s, 0.10, profiles).kind, "check")
        self.assertEqual(decide(s, 0.80, profiles).amount, 40)  # value still bets pot
        s._m["hole"] = ["Ks", "7c"]  # a pair still bets pot
        self.assertEqual(decide(s, 0.55, profiles).amount, 40)
        s._m["hole"] = ["Ks", "Qh"]
        profiles[1].update(faced_us=4, fold_us=4)  # folds again: bluff again
        self.assertEqual(decide(s, 0.10, profiles).amount, 40)

    def test_turn_barrel_after_a_called_cbet(self):
        line = [["preflop", 0, "raise", 5], ["flop", 0, "raise", 20], ["flop", 1, "call", 20]]
        s = postflop(board=["Ac", "7h", "2d", "9s"], hole=["Ks", "Qh"], pot=50, history=line)
        self.assertEqual(decide(s, 0.10).to_wire(), {"action": "raise", "amount": 50})  # air
        self.assertEqual(decide(s, 0.80).amount, 50)  # value uses the same size
        s._m["hole"] = ["Ks", "7c"]  # weak pair checks
        self.assertEqual(decide(s, 0.45).kind, "check")
        self.assertEqual(decide(s, 0.45, params=dict(DEFAULT_PARAMS, barrel_weak_pairs=True)).amount, 50)
        s._m["hole"] = ["Ks", "Qh"]
        self.assertEqual(decide(s, 0.10, {1: Counter(hands=20, faced=10, call=10)}).kind, "check")  # station
        self.assertEqual(decide(s, 0.10, {1: Counter(hands=10, faced_us=2, call_us=2)}).kind, "check")  # dial
        self.assertEqual(decide(s, 0.10, params=dict(DEFAULT_PARAMS, turn_barrel=False)).kind, "check")
        self.assertEqual(decide(s, 0.10, params=dict(DEFAULT_PARAMS, barrel_bluffs=False)).kind, "check")
        s._m["history"] = line[:1]  # flop checked through: no barrel
        self.assertEqual(decide(s, 0.10).kind, "check")
        s._m["history"] = line[:1] + [["flop", 1, "raise", 10], ["flop", 0, "call", 10]]  # their bet
        self.assertEqual(decide(s, 0.10).kind, "check")

    def test_bluff_frequency_mixes_air_repeatably(self):
        params = dict(DEFAULT_PARAMS, bluff_frequency=0.5)
        boards = [[a, b, c] for a, b, c in (("Qd", "8c", "3h"), ("Jd", "9c", "4h"), ("Td", "6c", "2h"),
                                             ("9d", "5c", "3s"), ("8d", "4c", "2s"), ("Qc", "6d", "4s"),
                                             ("Jc", "5d", "2c"), ("Tc", "8h", "3c"))]
        kinds = []
        for board in boards:
            s = postflop(board=board, history=[["preflop", 0, "raise", 5]])
            kinds.append(decide(s, 0.10, params=params).kind)
            self.assertEqual(decide(s, 0.10, params=params).kind, kinds[-1])
        self.assertEqual(set(kinds), {"raise", "check"})

    def test_their_cbet_gets_the_normal_margins(self):
        # Their pot-sized heads-up flop c-bet prices us at 1/3; calling it with
        # a weak pair or air loses ~0.86 pot per call on the ladder.
        s = postflop(to_call=40, pot=80, street_bets=[0, 40], min_raise_to=80,
                     history=[["preflop", 1, "raise", 5], ["flop", 1, "raise", 40]])
        self.assertEqual(decide(s, 0.36).kind, "fold")
        self.assertEqual(decide(s, 0.50).kind, "call")

    def test_out_of_position_air_checks(self):
        # Heads-up, the button acts last: with button=1 we act first (OOP).
        s = postflop(hole=["Ks", "Qh"], history=[["preflop", 0, "raise", 5]], button=1)
        self.assertEqual(decide(s, 0.10).kind, "check")  # air
        s._m["hole"] = ["As", "8h"]  # a pair still bets pot
        self.assertEqual(decide(s, 0.45).amount, 40)
        s._m.update(hole=["Ks", "Qh"], button=0)  # in position, air bets pot
        self.assertEqual(decide(s, 0.10).amount, 40)
        line = [["preflop", 0, "raise", 5], ["flop", 0, "raise", 20], ["flop", 1, "call", 20]]
        s = postflop(board=["Ac", "7h", "2d", "9s"], hole=["Ks", "Qh"], pot=50, history=line, button=1)
        self.assertEqual(decide(s, 0.10).kind, "check")  # no OOP air barrel
        s._m["hole"] = ["8s", "6s"]  # an open-ender still barrels
        self.assertEqual(decide(s, 0.30).amount, 50)

    def test_low_spr_value_shoves_and_all_in_opponents_cannot_be_bluffed(self):
        s = postflop(pot=300)
        self.assertEqual(decide(s, 0.95).amount, 190)
        s._m.update(stacks=[190, 0], can_raise=False)
        self.assertEqual(decide(s, 0.95).kind, "check")

    def test_locked_board_splits_do_not_fold_or_raise(self):
        s = postflop(board=["As", "Ks", "Qs", "Js", "Ts"], hole=["2d", "3c"])
        self.assertEqual(decide(s, 0.5).kind, "check")
        s._m.update(to_call=100, pot=110, street_bets=[0, 100])
        self.assertEqual(decide(s, None).kind, "call")

    def test_missing_equity_is_check_fold(self):
        s = postflop()
        self.assertEqual(decide(s, None).kind, "check")
        s._m.update(to_call=10, street_bets=[0, 10])
        self.assertEqual(decide(s, None).kind, "fold")
        self.assertEqual(decide(s, float("nan")).kind, "fold")


class BotIntegrationTests(unittest.TestCase):
    def test_normal_preflop_does_not_spend_simulation_time(self):
        with patch("bot.main.estimate_equity", side_effect=AssertionError("Unneeded simulation")):
            self.assertEqual(MyBot().act(state()).kind, "raise")

    def test_sparse_estimates_and_low_clock_fail_safely(self):
        bot = MyBot()
        result = SimpleNamespace(equity=1, method="monte_carlo", samples=1)
        s = postflop(to_call=10, street_bets=[0, 10])
        with patch("bot.main.estimate_equity", return_value=result):
            self.assertEqual(bot.act(s).kind, "fold")
        self.assertIsNone(bot.last_equity)
        s._m["clock_ms"] = 200
        with patch("bot.main.estimate_equity", side_effect=AssertionError("No time")):
            self.assertEqual(bot.act(s).kind, "fold")
        self.assertIsNone(bot.last_estimate)
        s._m["clock_ms"] = 2000
        with patch("bot.main.estimate_equity", return_value=result) as estimate:
            bot.act(s)
            self.assertEqual(estimate.call_args.args[-2:], (192, 10))

    def test_public_seed_one_observation_no_mutation_or_global_randomness(self):
        bot, s = MyBot(), postflop()
        before, rng = deepcopy(s.raw()), random.getstate()
        result = SimpleNamespace(equity=0.7, method="monte_carlo", samples=768)
        with patch("bot.main.estimate_equity", return_value=result) as estimate:
            action = bot.act(s)
            seed = estimate.call_args.kwargs["seed"]
            bot.on_action({"player": 100, "action": "raise", "amount": 200})
            bot.on_hand_start({})
            self.assertIsNone(bot.last_estimate)
            s._m.update(players=[200, 100], hand=99)
            self.assertEqual(bot.act(s), action)
            self.assertEqual(estimate.call_args.kwargs["seed"], seed)
        s._m.update(players=before["players"], hand=before["hand"])
        self.assertEqual(s.raw(), before)
        self.assertEqual(random.getstate(), rng)
        with self.assertRaises(TypeError):
            DEFAULT_PARAMS["open_bb"] = 3

    def test_real_equity_changes_the_action(self):
        # Exact hand strength extremes avoid a test depending on MC noise.
        bot = MyBot()
        s = postflop(board=["Qs", "Js", "Ts", "2c", "3d"], hole=["As", "Ks"])
        self.assertEqual(bot.act(s).kind, "raise")
        self.assertEqual(bot.last_equity, 1)
        s._m.update(hole=["4h", "5h"], board=["Ac", "Kd", "9s", "7h", "2c"],
                    to_call=100, pot=140, street_bets=[0, 100], min_raise_to=190)
        self.assertEqual(bot.act(s).kind, "fold")

    def test_raw_actions_are_legal_before_engine_coercion(self):
        test, rng, actions = self, Random(8732), []

        class AuditedSink(Sink):
            def __init__(self, n):
                self.bot, self.n = MyBot(), n

            def request_action(self, seat, view):
                s = GameState(dict(view, players=list(range(self.n)), clock_ms=30000))
                if seat:
                    if s.to_call and rng.random() < 0.25:
                        return s.fold()
                    if s.can_raise and rng.random() < 0.2:
                        return s.raise_to(rng.choice([s.min_raise_to, s.max_raise_to]))
                    return s.call() if s.to_call else s.check()
                action = self.bot.act(s)
                actions.append(action.kind)
                if action.kind == "raise":
                    test.assertTrue(s.can_raise)
                    test.assertLessEqual(s.min_raise_to, action.amount)
                    test.assertLessEqual(action.amount, s.max_raise_to)
                    test.assertGreater(action.amount, max(s.street_bets))
                elif action.kind == "check":
                    test.assertEqual(s.to_call, 0)
                else:
                    test.assertIn(action.kind, ("fold", "call"))
                    test.assertGreater(s.to_call, 0)
                return action

        for n in (2, 4, 6, 9):
            sink = AuditedSink(n)
            for hand in range(20):
                deck = list(range(52))
                rng.shuffle(deck)
                result = play_hand([200] * n, hand % n, deck, sink, 1, 2, hand)
                self.assertEqual(sum(result.deltas), 0)
        self.assertTrue({"raise", "check", "call", "fold"} <= set(actions))


if __name__ == "__main__":
    unittest.main()
