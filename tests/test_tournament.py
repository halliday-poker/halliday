import unittest
from harness.tournament import groups, score_round, standings


class TournamentTests(unittest.TestCase):
    def test_group_sizes_preserve_score_order(self):
        for count in range(2,101):
            order=list(range(count))
            tables=groups(order)
            self.assertEqual(sum(tables,[]),order)
            self.assertTrue(all(2<=len(t)<=7 for t in tables))
            self.assertLessEqual(max(map(len,tables))-min(map(len,tables)),1)

    def test_two_stage_scoring_and_ties(self):
        placement,game_points=[0.]*3,[0.]*3
        rows={0:[dict(game=0,chips=[10,-5,-5]),dict(game=1,chips=[-20,10,10]),
                 dict(game=2,chips=[0,0,0])]}
        score_round([[2,0,1]],rows,placement,game_points)
        self.assertEqual(game_points,[6.,6.,6.])
        self.assertEqual(placement,[2.,2.,2.])
        self.assertEqual(standings([10,12,10,4]),[2.5,1.,2.5,4.])

    def test_incomplete_or_nonzero_sum_rejected(self):
        for rows in ({0:[dict(game=0,chips=[1,-1])]},
                     {0:[dict(game=0,chips=[1,0]),dict(game=1,chips=[1,-1])]}):
            with self.assertRaises(ValueError):
                score_round([[0,1]],rows,[0.,0.],[0.,0.])


if __name__=='__main__':unittest.main()
