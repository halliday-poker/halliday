"""Protect the archived-control comparison against pairing and scoring errors."""
from copy import deepcopy
import unittest

from analysis.report_main_calibration import interval, paired_tables


def fixture():
    tables=[[f'a{i}' for i in range(3)],[f'b{i}' for i in range(5)]]
    reports=[]
    for candidate in (1,0):
        report=dict(tables=deepcopy(tables),seed='same-decks',
                    args=dict(deals=100,time_ms=30000,increment_ms=100),games=[])
        for t,opponents in enumerate(tables):
            for game in range(len(opponents)+1):
                chips=10+30*t+(4 if candidate==0 else 0)
                n=len(opponents)+1
                report['games'].append(dict(table=t,game=game,cand_idx=candidate,opponents=opponents,
                    chips=[chips,-chips]+[0]*(n-2),verdicts=['OK']*n,errors=[None]*n,
                    max_ms=[1]*n,think_ms=[10]*n))
        reports.append(report)
    return reports[1],reports[0]


class ArchivedControlTests(unittest.TestCase):
    def test_constant_paired_effect_and_game_weighting(self):
        tables=paired_tables(*fixture());result=interval(tables,replicates=500)
        self.assertEqual(result['point'],[14,16,2])
        self.assertEqual(result['low'][2],2)
        self.assertEqual(result['high'][2],2)
        # Equal-table weighting would give 12.5; it is wrong for chip return.
        self.assertNotEqual(result['point'][0],12.5)

    def test_tournament_placement_weights_tables_equally(self):
        tables=paired_tables(*fixture())
        result=interval(tables,('calibration_points','main_points','points_delta'),False,500)
        self.assertEqual(result['point'],[5,5,0])

    def test_missing_seat_rotation_rejected(self):
        new,old=fixture();new['games'].pop()
        with self.assertRaises(AssertionError):paired_tables(new,old)

    def test_different_seed_rejected(self):
        new,old=fixture();new['seed']='different'
        with self.assertRaises(AssertionError):paired_tables(new,old)

    def test_reordered_opponents_rejected(self):
        new,old=fixture();new['tables'][0].reverse()
        with self.assertRaises(AssertionError):paired_tables(new,old)

    def test_unexpected_control_policy_rejected(self):
        new,old=fixture();old['games'][0]['cand_idx']=2
        with self.assertRaises(AssertionError):paired_tables(new,old)

    def test_failure_or_non_zero_sum_rejected(self):
        for failure in (True,False):
            new,old=fixture()
            if failure:new['games'][0]['verdicts'][0]='TIMEOUT'
            else:new['games'][0]['chips'][0]+=1
            with self.assertRaises(AssertionError):paired_tables(new,old)

    def test_duplicate_game_rejected(self):
        new,old=fixture();new['games'].append(new['games'][0])
        with self.assertRaises(AssertionError):paired_tables(new,old)


if __name__=='__main__':unittest.main()
