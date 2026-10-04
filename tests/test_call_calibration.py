"""Regressions from reviewed decisions, plus guards on wider terminal calls."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor/macpoker-src'))
sys.path.insert(0, str(ROOT))
from macpoker import GameState
from harness import eval as harness
# Both main-based and calibrated grouping branches retain these regression
# fixtures, but only the calibrated snapshot should take the rescued calls.
module=harness._cached_module(harness.resolve_path('snapshots/opponent_groups_full'))[0]
MyBot,terminal_call,decide=module.MyBot,module.terminal_call,module.decide


def jacks(**updates):
    view = dict(type='act', hand=75, seat=2, street='preflop', board=[], hole=['Jc', 'Js'],
        pot=602, to_call=198, min_raise_to=200, max_raise_to=200, can_raise=False,
        stacks=[0, 0, 198, 200, 0, 200], street_bets=[200, 200, 2, 0, 200, 0],
        folded=[False, False, False, True, False, True], button=0,
        history=[['preflop', 3, 'fold', 0], ['preflop', 4, 'raise', 200],
                 ['preflop', 5, 'fold', 0], ['preflop', 0, 'call', 200], ['preflop', 1, 'call', 199]],
        players=[4, 5, 0, 1, 2, 3], clock_ms=37392)
    view.update(updates)
    return GameState(view)


def full_house(**updates):
    view = dict(type='act', hand=4, seat=2, street='river',
        board=['4d', '2s', '5s', '5c', '2c'], hole=['Ad', '5d'],
        pot=340, to_call=61, min_raise_to=154, max_raise_to=154, can_raise=False,
        stacks=[0, 199, 61, 200, 200, 200], street_bets=[154, 0, 93, 0, 0, 0],
        folded=[False, True, False, True, True, True], button=0,
        history=[['river', 2, 'raise', 93], ['river', 0, 'raise', 154]],
        players=[4, 5, 0, 1, 2, 3], clock_ms=30439)
    view.update(updates)
    return GameState(view)


class TerminalCallTests(unittest.TestCase):
    def test_reviewed_jacks_call_uses_range_equity_and_price(self):
        state = jacks()
        self.assertTrue(terminal_call(state))
        self.assertEqual(decide(state, .400716, ranged=True).kind, 'call')
        self.assertEqual(decide(state, .26, ranged=True).kind, 'fold')
        self.assertEqual(decide(state, .400716, ranged=False).kind, 'fold')
        self.assertEqual(decide(state, None, ranged=True).kind, 'fold')

    def test_wider_rule_requires_betting_to_end(self):
        state = jacks(stacks=[200, 200, 198, 200, 0, 200])
        self.assertFalse(terminal_call(state))
        self.assertEqual(decide(state, .8, ranged=True).kind, 'fold')

    def test_unanswered_action_is_not_terminal(self):
        state = jacks(stacks=[200, 0, 198, 200, 0, 200], street_bets=[0, 200, 2, 0, 200, 0])
        self.assertFalse(terminal_call(state))
        self.assertFalse(terminal_call(full_house(to_call=0)))

    def test_river_closure_still_requires_other_players_to_respond(self):
        state = full_house(stacks=[100, 199, 61, 200, 200, 200])
        self.assertTrue(terminal_call(state))
        state._m.update(folded=[False, False, False, True, True, True])
        self.assertFalse(terminal_call(state))


class PartialEquityTests(unittest.TestCase):
    def act_with_partial(self, state, equity, samples):
        bot = MyBot()
        estimate = SimpleNamespace(equity=equity, samples=samples, method='monte_carlo',
                                   stop_reason='time_budget')
        with patch.object(bot, 'opponent_ranges', return_value=[{('Ks', 'Kc'): 1}]), \
             patch.object(module,'estimate_equity', return_value=estimate):
            action = bot.act(state)
        return bot, action

    def test_reviewed_full_house_calls_after_104_winning_samples(self):
        bot, action = self.act_with_partial(full_house(), 1., 104)
        self.assertEqual(action.kind, 'call')
        self.assertGreater(bot.last_equity, .7)
        self.assertLess(bot.last_equity, .8)
        self.assertEqual(bot.last_estimate.equity, 1.)

    def test_one_sample_and_borderline_estimate_do_not_rescue_a_call(self):
        for equity, samples in [(1., 1), (.3, 104), (float('nan'), 104)]:
            _, action = self.act_with_partial(full_house(), equity, samples)
            self.assertEqual(action.kind, 'fold')

    def test_partial_equity_is_not_used_before_future_betting(self):
        state = full_house(board=['4d', '2s', '5s'], street='flop',
            stacks=[100, 199, 100, 200, 200, 200], history=[['flop', 0, 'raise', 154]])
        bot, action = self.act_with_partial(state, 1., 104)
        self.assertFalse(terminal_call(state))
        self.assertIsNone(bot.last_equity)
        self.assertEqual(action.kind, 'fold')


if __name__ == '__main__':
    unittest.main()
