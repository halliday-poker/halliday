"""Paired inference preserves whole duplicate tables and game weighting."""
import unittest
from analysis.report_call_calibration import paired_interval, paired_tables


class PairedComparisonTests(unittest.TestCase):
    def test_ratio_weights_games_and_pairs_before_resampling(self):
        rows = [dict(games=4,main=400,candidate=440,difference=40),
                dict(games=6,main=-300,candidate=-180,difference=120)]
        result = paired_interval(rows)
        self.assertEqual(result['point'], [5.,13.,8.])
        repeated = [{k:v*10 for k,v in row.items()} for row in rows]
        self.assertEqual(result, paired_interval(repeated))

    def test_identical_candidates_have_exactly_zero_paired_uncertainty(self):
        rows = [dict(games=4,main=400,candidate=400,difference=0),
                dict(games=6,main=-300,candidate=-300,difference=0)]
        result = paired_interval(rows)
        self.assertEqual([result[k][2] for k in ('point','low','high')], [0.,0.,0.])

    def test_missing_candidate_or_seat_is_rejected(self):
        game = dict(cand_idx=0,game=0,table=0,chips=[3,-1,-1,-1],verdicts=['OK']*4,errors=[None]*4)
        with self.assertRaises(AssertionError):
            paired_tables(dict(tables=[['a','b','c']],games=[game]))


if __name__ == '__main__': unittest.main()
