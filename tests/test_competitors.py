"""Latest-segment selection, seed isolation and actual fitted-opponent games."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import random
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor/macpoker-src"))
sys.path.insert(0, str(ROOT))

from harness.eval import bot_hash, make_bot, play_game, read_pool
from harness.tournament import is_house
from sparring.competitors.build import build, latest_profiles
from sparring.competitors.catalog import load_record, spec, write_catalog

DIRECTORY = ROOT / "sparring/competitors/from_data"
MANIFEST = json.loads((DIRECTORY / "profiles.json").read_text())


class CompetitorTests(unittest.TestCase):
    def test_selects_latest_timestamp_and_avoids_id_collisions(self):
        original = deepcopy(next(iter(MANIFEST["profiles"].values())))
        original.pop("id")
        newest = dict(original, segment=2, observed_from=200, observed_through=300)
        oldest = dict(original, segment=99, observed_from=10, observed_through=100)
        profiles = latest_profiles({"bots": {name: {"segments": [newest, oldest]}
                                             for name in ("A B", "a-b", "build")}})
        self.assertEqual(len({p["id"] for p in profiles.values()}), 3)
        self.assertTrue(all(p["segment"] == 2 for p in profiles.values()))
        self.assertNotEqual(profiles["build"]["id"], "build")

    def test_all_profiles_match_scaffold_and_load_without_state_leaks(self):
        self.assertEqual(MANIFEST["surrogate_source_sha256"],
                         sha256((ROOT / "sparring/param.py").read_bytes()).hexdigest())
        for name, profile in MANIFEST["profiles"].items():
            with self.subTest(bot=name):
                opponent = spec(DIRECTORY/'bots.json', profile['id'])
                first = make_bot(opponent, "same-seat")
                self.assertEqual(first.DISPLAY_NAME, name)
                self.assertEqual(first.base, profile["surrogate_style"])
                first.base["vpip"] = -1
                first.stats["opponent"] = [1, 1, 0, 1]
                second = make_bot(opponent, "same-seat")
                self.assertEqual(second.base, profile["surrogate_style"])
                self.assertEqual(second.stats, {})

    def test_seat_seed_is_independent_of_global_rng_and_other_constructors(self):
        opponent = spec(DIRECTORY/'bots.json', 'catherine')
        first = make_bot(opponent, "seat-123")
        expected = [first.rng.random() for _ in range(8)]
        random.seed(7)
        for _ in range(100):
            random.random()
        make_bot(spec(DIRECTORY/'bots.json', 'halliday'), "other-seat")
        repeated = make_bot(opponent, "seat-123")
        self.assertEqual(expected, [repeated.rng.random() for _ in range(8)])
        changed = make_bot(opponent, "seat-456")
        self.assertNotEqual(expected, [changed.rng.random() for _ in range(8)])

    def test_house_is_excluded_by_identity_in_data_catalogue(self):
        self.assertTrue(is_house(spec(DIRECTORY/'bots.json', 'house_call')))
        self.assertFalse(is_house(spec(DIRECTORY/'bots.json', 'halliday')))

    def test_archived_pool_specs_resolve_without_python_wrappers(self):
        old = str(DIRECTORY/'halliday.py')
        current = spec(DIRECTORY/'bots.json', 'halliday')
        self.assertFalse(Path(old).exists())
        self.assertEqual(make_bot(old, 'seed').base, make_bot(current, 'seed').base)
        self.assertEqual(bot_hash(old), bot_hash(current))

    def test_catalogue_edits_reload_and_change_only_affected_bot_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'bots.json'
            original = load_record(DIRECTORY/'bots.json', 'halliday')
            original.pop('policy')
            records = dict(first=original, second=deepcopy(original))
            write_catalog(path, records)
            first, second = spec(path, 'first'), spec(path, 'second')
            before = bot_hash(first), bot_hash(second)
            initial = make_bot(first, 'seed')
            initial_style = dict(initial.base)
            records['first']['style']['bluff'] = .123456
            write_catalog(path, records)
            self.assertEqual(make_bot(first, 'seed').base['bluff'], .123456)
            self.assertEqual(initial.base, initial_style)
            self.assertNotEqual(before[0], bot_hash(first))
            self.assertEqual(before[1], bot_hash(second))

    def test_policy_paths_are_relative_to_catalogue_and_configs_are_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            record = load_record(DIRECTORY/'bots.json', 'halliday')
            shutil.copyfile(DIRECTORY/'behavior-policy.npz', directory/'weights.npz')
            record['policy']['file'] = 'weights.npz'
            write_catalog(directory/'bots.json', {'hero': record})
            opponent = spec(directory/'bots.json', 'hero')
            first = make_bot(opponent, 'seed')
            first.policy_config['weight'] = 0
            second = make_bot(opponent, 'seed')
            self.assertEqual(second.policy_config['weight'], 1)
            self.assertIs(first.policy, second.policy)
            before = bot_hash(opponent)
            # Policy bytes, not just the JSON file, identify a fitted bot.
            with (directory/'weights.npz').open('ab') as stream:
                stream.write(b'fingerprint-test')
            self.assertNotEqual(before, bot_hash(opponent))

    def test_bad_parameters_and_unknown_identity_fail_clearly(self):
        with self.assertRaisesRegex(ValueError, 'unknown opponent ID'):
            make_bot(spec(DIRECTORY/'bots.json', 'missing'), 'seed')
        with tempfile.TemporaryDirectory() as tmp:
            record = load_record(DIRECTORY/'bots.json', 'halliday')
            for value in (float('nan'), -1, 2):
                record['style']['vpip'] = value
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'vpip'):
                    write_catalog(Path(tmp)/'bots.json', {'hero': record})

    def test_builder_updates_catalogue_and_removes_only_generated_wrappers(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'analysis/results') as tmp:
            directory = Path(tmp)
            segment = deepcopy(MANIFEST['profiles']['Halliday'])
            segment.pop('id')
            segment.pop('behavior')
            report = dict(surrogate_source_sha256=MANIFEST['surrogate_source_sha256'],
                          generated_at_utc='test', input_audit={}, settings={},
                          bots={'Halliday': {'segments': [segment]}, 'Old': {'segments': [segment]}})
            path = directory/'report.json'
            path.write_text(json.dumps(report))
            destination = directory/'competitors'
            destination.mkdir()
            (destination/'old.py').write_text('"""Generated fitted opponent: old."""\n')
            (destination/'custom.py').write_text('# User-owned helper\n')
            build(path, destination)
            self.assertFalse((destination/'old.py').exists())
            self.assertTrue((destination/'custom.py').exists())
            report['bots'].pop('Old')
            report['bots']['Halliday']['segments'][0]['surrogate_style']['bluff'] = .123456
            path.write_text(json.dumps(report))
            build(path, destination)
            data = json.loads((destination/'bots.json').read_text())
            self.assertEqual(set(data['bots']), {'halliday'})
            self.assertEqual(data['bots']['halliday']['style']['bluff'], .123456)
            self.assertEqual(read_pool(destination/'pool.txt', []), [])
            self.assertEqual(len(read_pool(destination/'all.txt', [])), 1)
            self.assertEqual(list(destination.glob('*.py')), [destination/'custom.py'])

    def test_pool_replaces_historical_halliday_and_covers_every_other_identity(self):
        pool = read_pool(DIRECTORY / "pool.txt", [])
        all_bots = read_pool(DIRECTORY / "all.txt", [])
        names = {make_bot(spec, "pool").DISPLAY_NAME for spec, _ in pool}
        self.assertEqual(names, set(MANIFEST["profiles"]) - {"Halliday"})
        self.assertEqual(len(all_bots), len(MANIFEST["profiles"]))
        self.assertTrue(all(weight == 1 for _, weight in pool))

    def test_entire_fitted_field_plays_legal_repeatable_games(self):
        specs = [spec(DIRECTORY/'bots.json', p['id']) for p in MANIFEST['profiles'].values()]
        # Every profile acts in a real game; avoid a final one-player group.
        for start in range(0, len(specs), 6):
            table = specs[start:start + 6]
            if len(table) == 1:
                table.append(specs[0])
            job = dict(candidate=table[0], opponents=table[1:], cand_idx=0,
                       table=start, game=0, seed="fitted-field-test", deals=12,
                       time_ms=30_000, increment_ms=100)
            with self.subTest(table=start):
                first = play_game(job)
                self.assertEqual(first["verdicts"], ["OK"] * len(table))
                self.assertEqual(first["errors"], [None] * len(table))
                self.assertEqual(sum(first["chips"]), 0)
                second = play_game(job)
                self.assertEqual(first["chips"], second["chips"])


if __name__ == "__main__":
    unittest.main()
