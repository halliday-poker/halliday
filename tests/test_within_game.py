"""Public-history isolation, game resets and no-action hand accounting."""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from opponent_model.data import COL, FIELDS
from opponent_model.within_game import PublicHistory, design, prepare, read
from sparring.param import ARCHETYPES


class WithinGameTests(unittest.TestCase):
    def test_history_is_prior_only_and_resets_between_games(self):
        history = PublicHistory(['a', 'b'])
        before = history.before('a').copy()
        actions = [dict(bot='a', street='preflop', action='raise', amount=200),
                   dict(bot='b', street='preflop', action='fold', amount=0)]
        history.finish(actions, {'a': 2, 'b': -2})
        self.assertEqual(before[0], 0)
        self.assertAlmostEqual(history.before('a')[0], .002)
        self.assertEqual(history.before('a')[1], 1)
        self.assertGreater(history.before('a')[6], before[6])
        self.assertGreater(history.before('b')[5], 0)
        np.testing.assert_array_equal(PublicHistory(['a', 'b']).before('a'), before)

    def test_hidden_cards_and_boards_do_not_enter_history(self):
        left, right = PublicHistory(['a', 'b']), PublicHistory(['a', 'b'])
        action = dict(bot='a', street='preflop', action='fold', amount=0)
        left.finish([action | {'holes': {'b': ['As', 'Ad']}, 'board': ['Ks']}], {'a': -1, 'b': 1})
        right.finish([action | {'holes': {'b': ['2s', '3d']}, 'board': ['2h']}], {'a': -1, 'b': 1})
        np.testing.assert_array_equal(left.before('a'), right.before('a'))

    def test_bad_settlement_cannot_contaminate_following_hands(self):
        history = PublicHistory(['a', 'b'])
        with self.assertRaisesRegex(ValueError, 'settlement'):
            history.finish([], {'a': 3, 'b': -1})
        self.assertEqual(history.hands, 0)
        self.assertEqual(history.score, {'a': 0, 'b': 0})

    def test_ablation_design_has_identical_capacity_and_zeros_only_removed_groups(self):
        data = dict(x=np.ones((2, 3)), progress=np.full((2, 2), 2), history=np.full((2, 4), 3))
        for mode in ('static', 'progress', 'history', 'combined'):
            x = design(data, mode)
            self.assertEqual(x.shape, (2, 9))
            np.testing.assert_array_equal(x[:, :3], data['x'])
            self.assertEqual(float(x[:, 3:5].sum()), 8 if mode in ('progress', 'combined') else 0)
            self.assertEqual(float(x[:, 5:].sum()), 24 if mode in ('history', 'combined') else 0)

    def test_walks_are_included_in_hand_denominators_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'source').mkdir()
            events = []
            for hand, folding in enumerate(('a', 'b')):
                events += [dict(match='m', hand=hand, bot=folding, street='preflop', action='fold', amount=0),
                           dict(match='m', hand=hand, event='hand_end', deltas_bot_names=['a', 'b'],
                                deltas_by_bot=[-1, 1] if hand == 0 else [1, -1])]
            raw = ''.join(json.dumps(e)+'\n' for e in events).encode()
            (root/'source/actions.jsonl').write_bytes(raw)
            profiles = {name: {'segments': [dict(surrogate_style=ARCHETYPES['tag'], segment=1, epoch=1,
                observed_from=1, observed_through=2, validation_only=False, known_play_times=1, match_ids=['m'])]}
                for name in ('a', 'b')}
            (root/'opponent-estimates.json').write_text(json.dumps(dict(segmentation_policy={'mode': 'upload'}, bots=profiles)))
            rows = np.zeros((2, len(FIELDS)), dtype=np.float32); rows[1, COL['hand']] = 1
            meta = dict(bots=['a', 'b'], matches=[dict(id='m', names=['a', 'b'], kind='ladder', played_at=1)],
                        input_audit={'actions_sha256': sha256(raw).hexdigest()}, split_policy='whole match')
            np.savez_compressed(root/'behavior-data.npz', metadata=np.asarray(json.dumps(meta)), rows=rows,
                x=np.zeros((2, 3)), legal=np.ones((2, 4), bool), y=np.zeros(2, dtype=np.int64),
                size_y=np.zeros(2, dtype=np.int64), size_targets=np.zeros((2, 10)), bot=np.arange(2),
                match=np.zeros(2, dtype=np.int64), split=np.zeros(2, dtype=np.int64),
                baseline=np.zeros((2, 4)), baseline_size=np.zeros(2))
            prepare(root)
            _, data = read(root)
            self.assertEqual(len(data['hands']), 4)
            self.assertEqual(data['hands'][:, 6].sum(), 2)
            self.assertEqual(data['history'][0, 0], 0)
            self.assertAlmostEqual(data['history'][1, 0], .001)


if __name__ == '__main__':
    unittest.main()
