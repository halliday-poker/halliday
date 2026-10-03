"""Public-event and decision guards for the isolated steal experiments."""
from collections import Counter
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.eval import make_bot
from macpoker import GameState


def state(**changes):
    value = dict(hole=['7s', '2d'], board=[], players=list(range(100,106)), seat=0,
                 button=0, folded=[False, False, False, True, True, True],
                 stacks=[200,199,198,200,200,200], pot=3, to_call=2, hand=1,
                 clock_ms=30000, street='preflop', street_bets=[0,1,2,0,0,0],
                 history=[['preflop', s, 'fold', 0] for s in (3,4,5)],
                 can_raise=True, min_raise_to=4, max_raise_to=200)
    return GameState(value | changes)


class StealTests(unittest.TestCase):
    def setUp(self):
        self.bot = make_bot('analysis/candidates/adaptive_steal', 'steal-test')
        self.context = type(self.bot).act.__globals__
        self.params = self.context['DEFAULT_PARAMS']
        self.decide = self.context['decide']
        self.profiles = {i:Counter(open_faced=20,open_fold=20) for i in range(100,106)}

    def test_garbage_raises_only_after_adequate_fold_evidence(self):
        self.assertEqual(self.decide(state(), None, self.profiles, self.params).kind, 'raise')
        self.assertEqual(self.decide(state(), None, {}, self.params).kind, 'fold')
        self.profiles[101] = Counter(open_faced=5,open_fold=5)
        self.assertEqual(self.decide(state(), None, self.profiles, self.params).kind, 'fold')
        self.profiles[101] = Counter(open_faced=20,open_fold=10)
        self.assertEqual(self.decide(state(), None, self.profiles, self.params).kind, 'fold')

    def test_limpers_raises_early_position_and_short_stack_disable_extra_open(self):
        cases = [dict(history=[['preflop',3,'call',2]]),
                 dict(history=[['preflop',3,'raise',5]],pot=8,to_call=5,street_bets=[0,1,2,5,0,0]),
                 dict(seat=3,folded=[False]*6,history=[]),
                 dict(max_raise_to=4,stacks=[4,199,198,200,200,200])]
        for changes in cases:
            with self.subTest(changes=changes):
                self.assertEqual(self.decide(state(**changes),None,self.profiles,self.params).kind,'fold')

    def test_value_open_survives_zero_frequency_and_no_evidence(self):
        params = dict(self.params,steal_frequency=0)
        self.assertEqual(self.decide(state(hole=['As','Ah']),None,{},params).amount,5)
        self.assertEqual(self.decide(state(),None,self.profiles,params).kind,'fold')

    def test_minimum_steal_keeps_value_size_and_only_reduces_extra_open(self):
        bot=make_bot('analysis/candidates/minimum_steal','minimum-steal-test')
        context=type(bot).act.__globals__
        decide,params=context['decide'],context['DEFAULT_PARAMS']
        self.assertEqual(decide(state(),None,self.profiles,params).amount,4)
        self.assertEqual(decide(state(hole=['As','Ah']),None,self.profiles,params).amount,5)
        self.assertEqual(decide(state(),None,{},params).kind,'fold')
        self.assertEqual(decide(state(min_raise_to=6),None,self.profiles,params).kind,'fold')

    def test_cutoff_needs_three_opponent_variant(self):
        s = state(seat=5,folded=[False,False,False,True,True,False],history=[])
        self.assertEqual(self.decide(s,None,self.profiles,self.params).kind,'fold')
        self.assertEqual(self.decide(s,None,self.profiles,dict(self.params,steal_max_opponents=3)).amount,5)

    def test_open_counts_exclude_limpers_and_reraises(self):
        tracker = self.bot.opponents
        players = list(range(100,106))
        tracker.on_hand_start(dict(players=players,stacks=[200]*6,seat=0))
        def event(seat, action, amount):
            tracker.on_action(dict(players=players,seat=seat,street='preflop',action=action,amount=amount))
        event(1,'call',2)
        event(2,'raise',5)
        event(1,'call',3)  # Previously limped, not a first response.
        event(3,'fold',0)
        event(4,'call',5)
        event(0,'raise',20)
        event(2,'fold',0)  # Facing a re-raise, not the opening bet.
        self.assertEqual(tracker.profiles[101]['open_faced'],0)
        self.assertEqual(tracker.profiles[102]['open_faced'],0)
        self.assertEqual(tracker.profiles[103]['open_faced'],1)
        self.assertEqual(tracker.profiles[103]['open_fold'],1)
        self.assertEqual(tracker.profiles[104]['open_faced'],1)
        self.assertEqual(tracker.profiles[104]['open_fold'],0)
        self.assertEqual(tracker.profiles[100]['open_faced'],1)
        tracker.on_hand_start(dict(players=players,stacks=[200]*6,seat=0))
        event(2,'raise',20)
        event(3,'fold',0)  # Oversized open is excluded.
        self.assertEqual(tracker.profiles[103]['open_faced'],1)
        tracker.on_action({})  # Observer robustness remains intact.


if __name__ == '__main__':
    unittest.main()
