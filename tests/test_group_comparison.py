"""The study must retain matched duplicate sets and compare all three policies."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/macpoker-src'));sys.path.insert(0,str(ROOT))
from analysis.report_opponent_groups import paired_tables,paired_interval,placement_interval
from bot.main import MyBot
from bot.params import DEFAULT_PARAMS
from harness import eval as harness
from test_strategy import postflop


def fixture():
    report=dict(tables=[['a']*3,['b']*5],games=[])
    for table,n in enumerate((4,6)):
        for game in range(n):
            for candidate in range(4):
                chips=10+4*candidate+table*30
                report['games'].append(dict(cand_idx=candidate,table=table,game=game,
                    opponents=report['tables'][table],
                    chips=[chips,-chips]+[0]*(n-2),verdicts=['OK']*n,errors=[None]*n,
                    max_ms=[10]*n,think_ms=[100]*n))
    return report


class ComparisonTests(unittest.TestCase):
    def test_game_weighted_return_and_paired_improvement(self):
        tables=paired_tables(fixture());interval=paired_interval(tables,500)
        self.assertEqual(interval['point'],[14,16,18,20,2,6,-2,-4])
        self.assertEqual(interval['low'][4],2)
        self.assertEqual(interval['high'][4],2)
        self.assertLess(interval['low'][0],interval['high'][0])

    def test_missing_candidate_or_seat_rotation_cannot_pass(self):
        report=fixture();report['games'].pop()
        with self.assertRaises(AssertionError):paired_tables(report)

    def test_non_zero_sum_results_cannot_pass(self):
        report=fixture();report['games'][0]['chips'][0]+=1
        with self.assertRaises(AssertionError):paired_tables(report)

    def test_placement_points_use_complete_duplicate_tables(self):
        result=placement_interval(paired_tables(fixture()),500)
        self.assertEqual(result['points'],[5]*4)
        self.assertEqual(result['wins'],[1]*4)
        self.assertEqual(result['delta'],[0]*3)

    def assert_disabled_matches(self,candidate_path,baseline_path):
        candidate_module=harness._cached_module(harness.resolve_path(candidate_path))[0]
        baseline_module=harness._cached_module(harness.resolve_path(baseline_path))[0]
        self.assertEqual({k:candidate_module.DEFAULT_PARAMS[k] for k in baseline_module.DEFAULT_PARAMS},dict(baseline_module.DEFAULT_PARAMS))
        disabled=dict(candidate_module.DEFAULT_PARAMS,group_enabled=False)
        with patch.object(candidate_module,'DEFAULT_PARAMS',disabled):
            candidate,control=candidate_module.MyBot(seed=1),baseline_module.MyBot()
            for board in (['Ac','7h','2d'],['Ac','7h','2d','Tc'],['Ac','7h','2d','Tc','9h']):
                street={3:'flop',4:'turn',5:'river'}[len(board)]
                for call in (0,10,50):
                    state=postflop(board=board,street=street,to_call=call,street_bets=[0,call],
                                   history=[] if not call else [[street,1,'raise',call]])
                    original=deepcopy(state.raw())
                    for equity in (0.,.25,.5,.75,1.):
                        estimate=SimpleNamespace(equity=equity,method='monte_carlo',samples=768)
                        with patch.object(candidate_module,'estimate_equity',return_value=estimate),patch.object(baseline_module,'estimate_equity',return_value=estimate):
                            self.assertEqual(candidate.act(state).to_wire(),control.act(state).to_wire())
                    self.assertEqual(state.raw(),original)

    def test_disabling_groups_retains_call_calibration_parameters_and_actions(self):
        self.assert_disabled_matches('snapshots/opponent_groups_full','snapshots/call_calibration_e186308_group_study')

    def test_disabling_groups_retains_main_parameters_and_actions(self):
        self.assert_disabled_matches('snapshots/opponent_groups_main','snapshots/main_6cfdf0f_opponent_groups')

    def test_both_group_variants_apply_identical_counter_adjustments(self):
        modules=[harness._cached_module(harness.resolve_path(p))[0] for p in ('snapshots/opponent_groups_main','snapshots/opponent_groups_full')]
        a,b=modules
        for ga,gb in zip(a.GROUPS,b.GROUPS):
            self.assertEqual({k:v for k,v in ga.items() if k!='counter'},{k:v for k,v in gb.items() if k!='counter'})
            for key in ga['counter']:
                self.assertAlmostEqual(ga['counter'][key]-a.DEFAULT_PARAMS[key],gb['counter'][key]-b.DEFAULT_PARAMS[key])


if __name__=='__main__':unittest.main()
