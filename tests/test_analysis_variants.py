"""Evidence-sensitive changes in the isolated Halliday experiments."""
from collections import Counter
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/macpoker-src'))
sys.path.insert(0,str(ROOT))
from harness.eval import make_bot
from macpoker import GameState


class ShoveCallerTests(unittest.TestCase):
    def setUp(self):
        self.bot=make_bot('analysis/candidates/shove_callers','cold-caller-test')
        self.state=GameState(dict(seat=0,button=0,players=[0,1,2],hole=['Js','Jh'],board=[],street='preflop',
                                 folded=[False]*3,stacks=[195,0,0],street_bets=[5,200,200],pot=405,to_call=195,
                                 can_raise=False,min_raise_to=200,max_raise_to=200,
                                 history=[['preflop',0,'raise',5],['preflop',1,'raise',200],['preflop',2,'call',198]],clock_ms=30000))
        self.bot.opponents._start_stacks=[200]*3
        self.bot.opponents.profiles[1]=Counter(hands=10,shoves=10)
        self.bot.opponents.profiles[2]=Counter(hands=10,shoves=10)

    def test_cold_caller_retains_its_range_even_if_it_previously_shoved(self):
        caller={('Kc','Kd'):1}
        self.bot.ranges.ranges_for=Mock(return_value=[{('Ac','Ad'):1},caller])
        self.assertEqual(self.bot.opponent_ranges(self.state,[1,2]),[None,caller])

    def test_calling_behind_shover_requires_ranged_equity_above_price(self):
        context=type(self.bot).act.__globals__
        decide=context['decide'];params=context['DEFAULT_PARAMS']
        self.assertEqual(decide(self.state,.60,self.bot.opponents.profiles,params,True).kind,'call')
        self.assertEqual(decide(self.state,.60,self.bot.opponents.profiles,params,False).kind,'fold')
        self.assertEqual(decide(self.state,.30,self.bot.opponents.profiles,params,True).kind,'fold')


if __name__=='__main__':unittest.main()
