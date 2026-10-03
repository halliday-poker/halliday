"""Checks for replay-audit accounting and hindsight/decision separation."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.halliday_performance import pots, payout, has_any_draw
from analysis.halliday_report import classify


class PayoffTests(unittest.TestCase):
    def test_gutshots_are_draws_but_shared_board_draws_are_not(self):
        self.assertTrue(has_any_draw(['As','Kc'],['2s','3d','4h']))
        self.assertFalse(has_any_draw(['Qc','Kh'],['2s','3d','4h','5c']))
        self.assertTrue(has_any_draw(['As','Ks'],['2s','3d','4s']))

    def test_short_stack_cannot_win_the_richer_side_pot(self):
        self.assertEqual(pots([50,200,200],[0,1,2],0),[(150,[0,1,2])])
        values = np.array([[9,1,8],[8,1,9],[9,1,9]])
        np.testing.assert_equal(payout(values,[50,200,200],[0,1,2],0),[150,0,75])

    def test_dead_chips_count_but_folded_hands_cannot_win(self):
        np.testing.assert_equal(payout(np.array([[9,1,20]]),[100,100,20],[0,1],0),[220])

    def test_uncalled_money_is_returned_not_contested(self):
        np.testing.assert_equal(payout(np.array([[9,1]]),[100,50],[0,1],0),[150])
        np.testing.assert_equal(payout(np.array([[1,9]]),[100,50],[0,1],0),[50])


class ClassificationTests(unittest.TestCase):
    def row(self):
        return dict(action='fold',oracle=dict(call_ev=30,ev_se=0),public={},
                    terminal_call=True,hindsight_final_equity=1,street='river',
                    call=10,pot=30,guaranteed_profitable_call=False)

    def test_hindsight_winner_is_not_automatically_a_blunder(self):
        row=self.row()
        row['public']={k:dict(call_ev=-3,ev_se=0) for k in ('tight','loose')}
        classify(row,{})
        self.assertEqual(row['classification'],'hindsight_missed_call_only')

    def test_future_betting_prevents_a_terminal_blunder_label(self):
        row=self.row()
        row['terminal_call']=False
        row['public']={k:dict(call_ev=20,ev_se=.1) for k in ('tight','loose')}
        classify(row,{})
        self.assertEqual(row['classification'],'possible_nonterminal_overfold')

    def test_both_range_models_and_monte_carlo_margin_must_agree(self):
        row=self.row()
        row['public']=dict(tight=dict(call_ev=10,ev_se=1),loose=dict(call_ev=-1,ev_se=0))
        classify(row,{})
        self.assertEqual(row['classification'],'hindsight_missed_call_only')
        row['public']['loose']=dict(call_ev=3,ev_se=2)
        classify(row,{})
        self.assertEqual(row['classification'],'hindsight_missed_call_only')
        row['public']['loose']=dict(call_ev=10,ev_se=1)
        classify(row,{})
        self.assertEqual(row['classification'],'probable_missed_terminal_call')


if __name__=='__main__':
    unittest.main()
