"""Latest-segment selection, seed isolation and actual fitted-opponent games."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor/macpoker-src"))
sys.path.insert(0, str(ROOT))

from harness.eval import make_bot, play_game, read_pool
from macpoker.sdk import load_bot_from_file
from sparring.competitors.build import latest_profiles

DIRECTORY = ROOT / "sparring/competitors/from_data"
MANIFEST = json.loads((DIRECTORY / "profiles.json").read_text())


class CompetitorTests(unittest.TestCase):
    def test_selects_latest_timestamp_and_avoids_filename_collisions(self):
        original = deepcopy(next(iter(MANIFEST["profiles"].values())))
        original.pop("file")
        newest = dict(original, segment=2, observed_from=200, observed_through=300)
        oldest = dict(original, segment=99, observed_from=10, observed_through=100)
        profiles = latest_profiles({"bots": {name: {"segments": [newest, oldest]}
                                             for name in ("A B", "a-b", "build")}})
        self.assertEqual(len({p["file"] for p in profiles.values()}), 3)
        self.assertTrue(all(p["segment"] == 2 for p in profiles.values()))
        self.assertNotEqual(profiles["build"]["file"], "build.py")

    def test_all_profiles_match_scaffold_and_load_without_state_leaks(self):
        self.assertEqual(MANIFEST["surrogate_source_sha256"],
                         sha256((ROOT / "sparring/param.py").read_bytes()).hexdigest())
        for name, profile in MANIFEST["profiles"].items():
            with self.subTest(bot=name):
                spec = str(DIRECTORY / profile["file"])
                first = make_bot(spec, "same-seat")
                self.assertEqual(first.DISPLAY_NAME, name)
                self.assertEqual(first.base, profile["surrogate_style"])
                first.base["vpip"] = -1
                first.stats["opponent"] = [1, 1, 0, 1]
                second = make_bot(spec, "same-seat")
                self.assertEqual(second.base, profile["surrogate_style"])
                self.assertEqual(second.stats, {})

    def test_seat_seed_is_independent_of_global_rng_and_other_constructors(self):
        spec = str(DIRECTORY / "catherine.py")
        first = make_bot(spec, "seat-123")
        expected = [first.rng.random() for _ in range(8)]
        random.seed(7)
        for _ in range(100):
            random.random()
        make_bot(str(DIRECTORY / "halliday.py"), "other-seat")
        repeated = make_bot(spec, "seat-123")
        self.assertEqual(expected, [repeated.rng.random() for _ in range(8)])
        changed = make_bot(spec, "seat-456")
        self.assertNotEqual(expected, [changed.rng.random() for _ in range(8)])

    def test_sdk_loader_accepts_generated_file(self):
        bot = load_bot_from_file(str(DIRECTORY / "catherine.py"))
        self.assertEqual(bot.DISPLAY_NAME, "catherine")

    def test_pool_replaces_historical_halliday_and_covers_every_other_identity(self):
        pool = read_pool(DIRECTORY / "pool.txt", [])
        all_bots = read_pool(DIRECTORY / "all.txt", [])
        names = {make_bot(spec, "pool").DISPLAY_NAME for spec, _ in pool}
        self.assertEqual(names, set(MANIFEST["profiles"]) - {"Halliday"})
        self.assertEqual(len(all_bots), len(MANIFEST["profiles"]))
        self.assertTrue(all(weight == 1 for _, weight in pool))

    def test_entire_fitted_field_plays_legal_repeatable_games(self):
        specs = [str(DIRECTORY / p["file"]) for p in MANIFEST["profiles"].values()]
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
