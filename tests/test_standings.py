"""Finishing-position play: chip totals, the points model and its decisions."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "macpoker-src"))
sys.path.insert(0, str(ROOT))

from macpoker import GameState
from macpoker.match import MatchConfig, MatchRunner
from macpoker.transport import InProcessTransport
from macpoker.bots import BUILTINS
from bot.main import MyBot
from bot.params import DEFAULT_PARAMS
from bot.preflop import pot_odds
from bot.standings import Standings
from bot.strategy import by_points, decide

PARAMS = dict(DEFAULT_PARAMS, endgame_enabled=True)


def standings(totals, hand, me=0, num_hands=100, params=PARAMS):
    s = Standings(params)
    s.on_match_start({"player": me, "num_hands": num_hands})
    s.totals = dict(totals)
    s.on_hand_start({"players": list(range(len(totals))), "seat": me,
                     "stacks": [200] * len(totals), "hand": hand})
    return s


def river(hand, **updates):
    """Heads-up river: seat 1 bet 40 into 40, seat 0 (us) to act."""
    msg = dict(hole=["As", "9h"], board=["Ac", "7h", "2d", "Ks", "4c"], players=[0, 1, 2, 3],
               seat=0, button=1, folded=[False, False, True, True], stacks=[160, 120, 200, 200],
               pot=120, to_call=40, hand=hand, clock_ms=30000, street="river",
               street_bets=[0, 40, 0, 0], history=[["preflop", 1, "raise", 6], ["river", 1, "raise", 40]],
               can_raise=True, min_raise_to=80, max_raise_to=160)
    msg.update(updates)
    return GameState(msg)


class TotalsTests(unittest.TestCase):
    def test_hand_end_deltas_follow_player_ids_across_seats(self):
        s = Standings(PARAMS)
        s.on_match_start({"player": 2, "num_hands": 100})
        s.on_hand_start({"players": [0, 1, 2], "seat": 2, "stacks": [200] * 3})
        s.on_hand_end({"deltas": [10, -4, -6]})
        s.on_hand_start({"players": [2, 0, 1], "seat": 0, "stacks": [200] * 3})
        s.on_hand_end({"deltas": [7, -7, 0]})
        self.assertEqual(s.totals, {0: 3, 1: -4, 2: 1})

    def test_totals_match_the_engine_over_a_game(self):
        bot = MyBot()
        bots = [bot, BUILTINS["call"](), BUILTINS["random"](), BUILTINS["call"]()]
        transports = [InProcessTransport(b) for b in bots]
        result = MatchRunner(MatchConfig(seats=4, deals=30, seed="standings"), transports).run()
        self.assertEqual([bot.standings.totals[pid] for pid in range(4)], result.chips)
        self.assertEqual(bot.standings.num_hands, 30)

    def test_malformed_messages_are_ignored(self):
        s = Standings(PARAMS)
        s.on_hand_start({})
        s.on_hand_end({"deltas": None})
        s.on_match_start(None)
        self.assertEqual(s.totals, {})


class PointsModelTests(unittest.TestCase):
    def test_points_run_from_one_to_n(self):
        s = standings({0: 0, 1: 0, 2: 0, 3: 0}, hand=99)
        self.assertEqual(s.expected_points({0: 50, 1: 0, 2: 0, 3: 0}, 0), 4.0)
        self.assertEqual(s.expected_points({0: -50, 1: 0, 2: 0, 3: 0}, 0), 1.0)
        self.assertEqual(s.expected_points({0: 0, 1: 0, 2: 0, 3: 0}, 0), 2.5)

    def test_inactive_outside_the_window_or_when_disabled(self):
        self.assertFalse(standings({0: 0, 1: 0}, hand=10).active(river(10)))
        self.assertTrue(standings({0: 0, 1: 0}, hand=90).active(river(90)))
        off = standings({0: 0, 1: 0}, hand=90, params=dict(PARAMS, endgame_enabled=False))
        self.assertFalse(off.active(river(90)))

    def test_price_is_pot_odds_when_far_from_the_end(self):
        # A wide window makes hand 1 active; with 98 hands left points are near linear.
        s = standings({0: 0, 1: 0, 2: 0, 3: 0}, hand=1, params=dict(PARAMS, endgame_window=100))
        state = river(1)
        self.assertAlmostEqual(s.call_price(state), pot_odds(state), delta=0.01)

    def test_linearised_price_is_exactly_pot_odds(self):
        s = standings({0: 30, 1: -10, 2: 0, 3: -20}, hand=95)
        s.linearise(river(95))
        try:
            self.assertAlmostEqual(s.call_price(river(95)), pot_odds(river(95)), places=6)
        finally:
            s.linearise(None)

    def test_safe_lead_on_the_last_hand_raises_the_price(self):
        # We lead the bettor by 100: calling 40 and losing costs first place.
        s = standings({0: 100, 1: 0, 2: -50, 3: -50}, hand=99)
        self.assertGreater(s.call_price(river(99)), pot_odds(river(99)) + 0.2)

    def test_near_miss_on_the_last_hand_lowers_the_price(self):
        # 50 behind the bettor: only winning this pot moves us up.
        s = standings({0: -50, 1: 0, 2: -150, 3: -150}, hand=99)
        self.assertLess(s.call_price(river(99)), pot_odds(river(99)) - 0.1)


class DecisionTests(unittest.TestCase):
    def test_marginal_call_folds_with_a_safe_lead(self):
        state = river(99)
        equity = pot_odds(state) + 0.10  # a clear chip-EV call
        self.assertEqual(decide(state, equity, {}, PARAMS, standings=standings(
            {0: 0, 1: 0, 2: 0, 3: 0}, hand=99, params=dict(PARAMS, endgame_enabled=False))).kind, "call")
        self.assertEqual(decide(state, equity, {}, PARAMS, standings=standings(
            {0: 100, 1: 0, 2: -50, 3: -50}, hand=99)).kind, "fold")

    def test_light_call_when_just_behind(self):
        state = river(99)
        equity = pot_odds(state) - 0.05
        self.assertEqual(decide(state, equity, {}, PARAMS).kind, "fold")
        # Taking this pot is the only way up, so it continues (calls or shoves).
        self.assertIn(decide(state, equity, {}, PARAMS, standings=standings(
            {0: -50, 1: 0, 2: -150, 3: -150}, hand=99)).kind, ("call", "raise"))

    def test_no_change_without_standings_or_early(self):
        state = river(40)
        for equity in (0.1, 0.3, 0.5, 0.9):
            self.assertEqual(decide(state, equity, {}, PARAMS),
                             decide(state, equity, {}, PARAMS, standings=standings({0: 0, 1: 0, 2: 0, 3: 0}, 40)))

    def test_shove_steps_down_with_a_safe_lead(self):
        # Checked to us on the last hand, ahead of the bettor: checking keeps 2nd at
        # worst, but losing a stack would drop us below player 2 as well.
        state = river(99, to_call=0, street_bets=[0, 0, 0, 0], pot=80, stacks=[160, 160, 200, 200],
                      history=[["preflop", 1, "raise", 6]], min_raise_to=2, max_raise_to=160)
        s = standings({0: 150, 1: 100, 2: 0, 3: -250}, hand=99)
        shove = state.raise_to(160)
        caller = {1: {"faced_us": 12, "fold_us": 1, "faced": 12, "fold": 1}}
        self.assertNotEqual(by_points(state, shove, 0.75, caller, PARAMS, False, s), shove)
        # The same lead keeps the shove early in the game, where chips decide.
        early = standings({0: 150, 1: 100, 2: 0, 3: -250}, hand=5, params=dict(PARAMS, endgame_window=100))
        state = river(5, to_call=0, street_bets=[0, 0, 0, 0], pot=80, stacks=[160, 160, 200, 200],
                      history=[["preflop", 1, "raise", 6]], min_raise_to=2, max_raise_to=160)
        self.assertEqual(by_points(state, shove, 0.75, caller, PARAMS, False, early), shove)

    def test_failures_fall_back_to_chip_ev(self):
        class Broken(Standings):
            def active(self, state):
                raise RuntimeError
        state = river(99)
        broken = Broken(PARAMS)
        self.assertEqual(decide(state, 0.9, {}, PARAMS, standings=broken), decide(state, 0.9, {}, PARAMS))


if __name__ == "__main__":
    unittest.main()
