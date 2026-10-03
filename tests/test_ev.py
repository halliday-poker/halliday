"""EV action selection: sensible choices, guards, fallbacks, timing, real games."""

from collections import Counter, defaultdict
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "macpoker-src"))
sys.path.insert(0, str(ROOT))

from macpoker import GameState
from macpoker.bots import BUILTINS
from macpoker.match import MatchConfig, MatchRunner
from macpoker.transport import InProcessTransport
from bot import ev
from bot.main import MyBot
from bot.params import DEFAULT_PARAMS
from bot.ranges import RangeTracker

P = dict(DEFAULT_PARAMS, ev_enabled=True)
STREETS = {"flop": 3, "turn": 4, "river": 5}


def heads_up(hole, board, opp_bet=0, profile=None, params=P, stacks=(200, 200)):
    """We are the button (seat 1, in position): we raised preflop and were called,
    earlier streets checked through, then the opponent checks or bets `opp_bet`."""
    players = [7, 3]
    profiles = defaultdict(Counter)
    if profile:
        profiles[7].update(profile)
    rt = RangeTracker(profiles, params)
    rt.on_hand_start({"players": players, "stacks": list(stacks), "seat": 1, "button": 1})

    def act(street, seat, kind, amount=0):
        rt.on_action({"street": street, "seat": seat, "action": kind, "amount": amount,
                      "players": players})
    act("preflop", 1, "raise", 6)
    act("preflop", 0, "call", 4)
    street = {3: "flop", 4: "turn", 5: "river"}[len(board)]
    for name, n in STREETS.items():
        rt.on_street({"street": name, "board": board[:n]})
        if name == street:
            break
        act(name, 0, "check")
        act(name, 1, "check")
    act(street, 0, "raise" if opp_bet else "check", opp_bet)
    left = [stacks[0] - 6 - opp_bet, stacks[1] - 6]
    state = GameState(dict(
        hole=hole, board=board, players=players, seat=1, button=1, folded=[False, False],
        stacks=left, pot=12 + opp_bet, to_call=opp_bet, hand=1, clock_ms=30000, street=street,
        street_bets=[opp_bet, 0], history=[], can_raise=True,
        min_raise_to=max(2, 2 * opp_bet), max_raise_to=left[1]))
    return state, rt, profiles


def decide(hole, board, **kw):
    params = kw.get("params", P)
    state, rt, profiles = heads_up(hole, board, **kw)
    return ev.choose(state, rt, profiles, params, 1), state


class Choices(unittest.TestCase):
    def test_value_bets_the_nuts(self):
        (action, info), _ = decide(["Ah", "Ad"], ["As", "7c", "2d", "9h", "3s"])
        self.assertEqual(action.kind, "raise")
        self.assertGreater(info["table"][action.amount], info["table"]["check"])

    def test_no_bluffs_against_a_player_who_never_folds(self):
        (action, _), _ = decide(["5c", "4h"], ["Ks", "Qc", "9d", "8h", "2s"],
                                profile=dict(faced_us=12, fold_us=0))
        self.assertEqual(action.kind, "check")

    def test_never_calls_with_no_equity(self):
        (action, info), _ = decide(["3c", "4h"], ["Ks", "Qc", "9d", "8h", "Js"], opp_bet=12)
        self.assertNotEqual(action.kind, "call")
        self.assertLess(info["table"]["call"], 0)

    def test_calls_or_raises_a_strong_hand(self):
        (action, _), _ = decide(["Kd", "Kc"], ["Ks", "7c", "2d", "9h", "3s"], opp_bet=12)
        self.assertIn(action.kind, ("call", "raise"))


class Guards(unittest.TestCase):
    def test_all_in_only_when_stacks_are_short(self):
        (_, deep), state = decide(["Ah", "Ad"], ["As", "7c", "2d", "9h", "3s"])
        self.assertNotIn(state.max_raise_to, deep["table"])
        (_, short), state = decide(["Ah", "Ad"], ["As", "7c", "2d", "9h", "3s"], stacks=(40, 40))
        self.assertIn(state.max_raise_to, short["table"])

    def test_smallest_size_within_tolerance(self):
        wide = dict(P, ev_size_tolerance=10.0)  # every size counts as equal
        (action, info), _ = decide(["Ah", "Ad"], ["As", "7c", "2d", "9h", "3s"], params=wide)
        sizes = [k for k in info["table"] if isinstance(k, int)]
        self.assertEqual(action.amount, min(sizes))

    def test_out_of_scope_returns_nothing(self):
        state, rt, profiles = heads_up(["Ah", "Ad"], ["As", "7c", "2d"])
        self.assertEqual(ev.choose(state, rt, profiles, dict(P, ev_max_opponents=0), 1), (None, None))

    def test_flop_timing(self):
        state, rt, profiles = heads_up(["9h", "8h"], ["Ks", "7h", "2h"])
        started = time.perf_counter()
        action, info = ev.choose(state, rt, profiles, P, 1)
        self.assertIsNotNone(action)
        self.assertLess((time.perf_counter() - started) * 1000, P["ev_time_budget_ms"] + 60)


class Integration(unittest.TestCase):
    def play(self, bot, deals=40):
        transports = [InProcessTransport(bot, "bot")] + [
            InProcessTransport(BUILTINS[name](), name) for name in ("call", "random", "call")]
        return MatchRunner(MatchConfig(seats=4, deals=deals, seed="ev-test"), transports).run()

    @patch("bot.main.DEFAULT_PARAMS", P)
    def test_plays_legal_games_using_ev(self):
        bot = MyBot()
        used, original = [], bot.act

        def spy(state):
            action = original(state)
            used.append(bot.last_ev is not None)
            return action
        bot.act = spy
        self.assertEqual(self.play(bot).verdicts[0], "OK")
        self.assertTrue(any(used))

    @patch("bot.main.DEFAULT_PARAMS", P)
    def test_failure_falls_back_to_rules(self):
        bot = MyBot()
        with patch("bot.main.choose", side_effect=RuntimeError("boom")):
            self.assertEqual(self.play(bot, deals=15).verdicts[0], "OK")


if __name__ == "__main__":
    unittest.main()
