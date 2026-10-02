"""Offline estimator tests; CUDA is used when installed, CPU is parity only."""

from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
from random import Random
import tempfile
import unittest
from unittest.mock import patch

try:
    import numpy as np
    import torch
except ImportError:
    torch = None

if torch is not None:
    from opponent_model.compute import Compute
    from opponent_model.data import COL, FIELDS, Dataset, load_dataset, reconstruct_hand, save_dataset, load_cache
    from opponent_model.fit import BotModel, PARAMETERS, free_bet_probability
    from opponent_model.pipeline import lookup
    from opponent_model.segments import optimal_partition, propose_changes, confirm_family, split_discovery
    from macpoker import GameState
    from sparring.param import ParamBot, hand_percentile


def fixture():
    holes = {"a": ["As", "Kh"], "b": ["7s", "2h"]}
    return [
        dict(match="m", hand=0, street="preflop", seat=0, bot="a", action="call", amount=1, pot=4, holes=holes),
        dict(match="m", hand=0, street="preflop", seat=1, bot="b", action="check", amount=0, pot=4, holes=holes),
        dict(match="m", hand=0, street="flop", event="board", board=["Ac", "7d", "2c"]),
        dict(match="m", hand=0, street="flop", seat=1, bot="b", action="raise", amount=2, pot=6, holes=holes),
        dict(match="m", hand=0, street="flop", seat=0, bot="a", action="fold", amount=0, pot=6, holes=holes),
        dict(match="m", hand=0, event="hand_end", board=["Ac", "7d", "2c"], holes=holes),
    ]


@unittest.skipIf(torch is None, "Install opponent_model's offline NumPy/PyTorch dependencies")
class ReplayTests(unittest.TestCase):
    def test_reconstructs_preaction_pot_blinds_and_board(self):
        rows, hands = reconstruct_hand(fixture(), dict(names=["a", "b"]), 0,
                                       defaultdict(lambda: [0, 0, 0, 0]))
        self.assertEqual([r[1][COL["pot"]] for r in rows], [3, 4, 4, 6])
        self.assertEqual(rows[0][1][COL["call"]], 1)
        self.assertEqual(rows[0][1][COL["maximum"]], 200)
        self.assertTrue(np.isnan(rows[0][1][COL["strength"]]))
        self.assertEqual(hands, {"a": [1, 1, 0], "b": [1, 0, 0]})

    def test_seat_mapping_does_not_depend_on_hole_dict_order(self):
        events = fixture()
        for row in events:
            if "holes" in row:
                row["holes"] = dict(reversed(list(row["holes"].items())))
        rows, _ = reconstruct_hand(events, dict(names=["b", "a"]), 2,
                                   defaultdict(lambda: [0, 0, 0, 0]))
        self.assertEqual(rows[0][0], "a")
        self.assertEqual(rows[0][1][COL["match"]], 2)

    def test_rejects_incomplete_illegal_and_inconsistent_replays(self):
        variants = [fixture()[:-1]]
        wrong = fixture(); wrong[0]["pot"] = 99; variants.append(wrong)
        wrong = fixture(); wrong[0]["bot"] = "b"; variants.append(wrong)
        wrong = fixture(); wrong[0]["action"] = "check"; variants.append(wrong)
        for events in variants:
            with self.assertRaises(ValueError):
                reconstruct_hand(events, dict(names=["a", "b"]), 0,
                                 defaultdict(lambda: [0, 0, 0, 0]))

    def test_metadata_join_cache_and_duplicate_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "matches.json").write_text(json.dumps([dict(id="m", names=["a", "b"], collected_at=50)]))
            (root / "state.json").write_text(json.dumps(dict(collected={"m": dict(status="collected", collected_at=100)})))
            (root / "actions.jsonl").write_text("\n".join(map(json.dumps, fixture())) + "\n")
            data = load_dataset(root / "actions.jsonl", root / "matches.json", root / "state.json")
            self.assertEqual(data.matches[0]["collected_at"], 100)
            self.assertEqual(data.audit["timestamp_disagreements_state_used"], 1)
            save_dataset(data, root / "cache.npz")
            cached = load_cache(root / "cache.npz")
            np.testing.assert_equal(cached.observations["a"], data.observations["a"])
            self.assertEqual(cached.hands, data.hands)
            with (root / "actions.jsonl").open("a") as f:
                f.write("\n".join(map(json.dumps, fixture())) + "\n")
            with self.assertRaises(ValueError):
                load_dataset(root / "actions.jsonl", root / "matches.json", root / "state.json")


def synthetic_observations(style, *, matches=36, actions=800, seed=19):
    """Generate labels with the REAL ParamBot, not the estimator probability code.

    Inject diverse heuristic-strength outputs to exercise every latent branch
    without making this test depend on an expensive duplicate deck simulator.
    """
    rng, bot, rows = Random(seed), ParamBot(style, seed), []
    deck = [r+s for r in "23456789TJQKA" for s in "cdhs"]
    for match in range(matches):
        for i in range(actions):
            mode = rng.randrange(5)
            pre = mode <= 1
            street = 0 if pre else rng.choice([1, 2, 3])
            cbet = mode == 3 and street == 1
            facing = pre or mode == 4
            call = (2 if mode == 0 else 6) if pre else rng.choice([2, 6, 15, 30]) if facing else 0
            made, draw = rng.choice([.1, .2, .35, .45, .55, .60, .65, .7, .75, .82, .88, .95]), street in (1, 2) and rng.random() < .3
            hole = rng.sample(deck, 2)
            pre_history = [] if mode == 0 else [["preflop", 0 if cbet else 1, "raise", 6]]
            history = pre_history + ([[["preflop", "flop", "turn", "river"][street], 1, "raise", call]] if not pre and facing else [])
            bets = [0, call, 2 if pre else 0, 0]
            pot = 3 if mode == 0 else (9 if pre else rng.randrange(20, 100) + call)
            msg = dict(hole=hole, board=["2c", "7d", "Jh", "Qc", "9s"][:{0:0, 1:3, 2:4, 3:5}[street]],
                       history=history, street=["preflop", "flop", "turn", "river"][street],
                       seat=0, players=[0, 1, 2, 3], folded=[False]*4, stacks=[200]*4,
                       to_call=call, pot=pot, can_raise=True, min_raise_to=max(2, 2*call),
                       max_raise_to=200, street_bets=bets)
            state = GameState(msg)
            high_agg = rng.random() < .5
            fold_case = rng.randrange(3)
            folds = [10, 35, 60][fold_case]
            bot.me = 0
            bot.stats = {j: [100, 40 if high_agg else 10, folds, 100] for j in (1, 2, 3)}
            effective = bot.style(state)
            with patch("sparring.param.strength", return_value=(made, draw)):
                action = bot.preflop(state, effective) if pre else bot.postflop(state, effective)
            row = np.zeros(len(FIELDS))
            values = dict(match=match, street=street, seat=0, players=4, pct=hand_percentile(hole),
                          strength=np.nan if pre else made, draw=draw, facing=facing,
                          can_raise=1, pre_raises=len(pre_history), cbet=cbet,
                          action={"fold":0,"check":1,"call":2,"raise":3}[action.kind], amount=action.amount,
                          pot=pot, minimum=msg["min_raise_to"], maximum=200, call=call,
                          stack=200, top=max(bets), bet=0, agg_high=high_agg,
                          fold_high=fold_case == 2, fold_low=fold_case == 0, hand=i)
            for name, value in values.items(): row[COL[name]] = value
            rows.append(row)
    return np.asarray(rows), {i: [actions, 0, 0] for i in range(matches)}


@unittest.skipIf(torch is None, "Offline dependencies not installed")
class EstimatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compute = Compute("cuda" if torch.cuda.is_available() else "cpu", seed=91)
        cls.style = dict(vpip=.4, pfr=.3, threebet=.1, limp=.2, aggression=.6,
                         cbet=.65, bluff=.2, stickiness=.5, size=.8, adaptive=1)
        cls.rows, cls.hands = synthetic_observations(cls.style)

    def test_recovers_known_surrogate_and_reports_joint_uncertainty(self):
        model = BotModel(self.rows, self.hands, self.compute)
        report = model.estimate(list(range(len(self.hands))), bootstrap=100)
        for name in PARAMETERS[:-1]:
            tolerance = .025 if name in ("vpip", "pfr", "threebet", "stickiness", "size") else .15
            self.assertAlmostEqual(report["parameters"][name]["estimate"], self.style[name], delta=tolerance, msg=name)
            self.assertIsNotNone(report["parameters"][name]["variance"])
        self.assertEqual(report["surrogate_style"]["adaptive"], 1)
        self.assertEqual(len(report["uncertainty"]["covariance"]), len(PARAMETERS))
        self.assertGreater(report["uncertainty"]["adaptive_selection_frequency"], .8)

    def test_no_data_is_not_a_precise_zero(self):
        model = BotModel(np.empty((0, len(FIELDS))), {0: [10, 0, 0], 1: [10, 0, 0]}, self.compute)
        report = model.estimate([0, 1], bootstrap=20)
        for parameter in report["parameters"].values():
            self.assertIsNone(parameter["estimate"])
            self.assertEqual(parameter["status"], "insufficient_data")

    @unittest.skipUnless(torch is not None and torch.cuda.is_available(), "CUDA parity test requires GPU")
    def test_gpu_cpu_likelihood_and_point_estimate_parity(self):
        rows = self.rows[self.rows[:, COL["match"]] < 2]
        hands = {k:v for k,v in self.hands.items() if k < 2}
        gpu = BotModel(rows, hands, self.compute, grid_step=.1)
        cpu = BotModel(rows, hands, Compute("cpu"), grid_step=.1)
        for key in gpu.blocks:
            torch.testing.assert_close(gpu.blocks[key].loss.cpu(), cpu.blocks[key].loss, rtol=1e-10, atol=1e-8)
        a, _ = gpu.fit_weights(self.compute.array([[1, 1]]))
        b, _ = cpu.fit_weights(torch.ones((1, 2), dtype=torch.float64))
        torch.testing.assert_close(a.cpu(), b)

    def test_gpu_requirement_never_silently_falls_back(self):
        with patch("torch.cuda.is_available", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "no CPU fallback"):
                Compute("cuda")

    def test_clipped_size_is_censored_not_treated_as_target(self):
        rows = self.rows.copy()
        # A legal ceiling of 10 on every free postflop raise removes all
        # information about sizes which would have exceeded that ceiling.
        mask = (rows[:, COL["street"]] > 0) & (rows[:, COL["facing"]] == 0) & (rows[:, COL["action"]] == 3)
        rows[mask, COL["maximum"]] = 10
        rows[mask, COL["amount"]] = np.minimum(10, rows[mask, COL["amount"]])
        model = BotModel(rows, self.hands, self.compute)
        report = model.estimate(list(range(len(self.hands))), bootstrap=20)
        self.assertGreater(report["parameters"]["size"]["likelihood_support_interval"][1], 1.3)


@unittest.skipIf(torch is None, "Offline dependencies not installed")
class ChangePointTests(unittest.TestCase):
    def setUp(self):
        self.compute = Compute("cuda" if torch.cuda.is_available() else "cpu", seed=1)

    def test_known_change_is_discovered_and_independently_confirmed(self):
        values = np.zeros((100, 10))
        values[50:, :9] = 1
        plan = propose_changes(self.compute.array(values), list(range(100)), [f"m{i}" for i in range(100)],
                               self.compute, minimum=6, permutations=199)
        confirm_family([plan])
        self.assertEqual(len(plan["accepted_cut_times"]), 1)
        self.assertLess(abs(plan["accepted_cut_times"][0] - 50), 5)

    def test_constant_bot_stays_unsplit(self):
        values = self.compute.array(np.full((60, 10), .3))
        plan = propose_changes(values, list(range(60)), [f"m{i}" for i in range(60)], self.compute, permutations=199)
        self.assertEqual(plan["proposals"], [])

    def test_dynamic_programming_matches_small_exhaustive_cost(self):
        values = self.compute.array([[0], [0], [0], [1], [1], [1], [0], [0]])
        cuts, objective = optimal_partition(values, list(range(8)), minimum=2, penalty=.1, max_segments=3)
        self.assertEqual(cuts, [3, 6])
        self.assertAlmostEqual(objective["penalized_cost"], .2)

    def test_tied_timestamps_share_split_and_cannot_be_boundary(self):
        assignment = split_discovery(["a", "b", "c", "d"], [0, 0, 1, 1], 8)
        self.assertEqual(assignment[0], assignment[1])
        self.assertEqual(assignment[2], assignment[3])
        values = self.compute.array([[0], [0], [1], [1]])
        cuts, _ = optimal_partition(values, [0, 1, 1, 2], minimum=2, penalty=0, max_segments=2)
        self.assertEqual(cuts, [])

    def test_holm_corrects_all_bots_together(self):
        plans = [dict(proposals=[dict(cut_at=1, p_value=.01), dict(cut_at=2, p_value=.04)]),
                 dict(proposals=[dict(cut_at=3, p_value=.03)])]
        confirm_family(plans)
        self.assertEqual(plans[0]["accepted_cut_times"], [1])
        self.assertEqual(plans[1]["accepted_cut_times"], [])
        self.assertAlmostEqual(plans[0]["proposals"][1]["adjusted_p_value"], .06)

    def test_lookup_does_not_extrapolate(self):
        report = dict(bots={"a": dict(segments=[dict(observed_from=10, observed_through=20,
                                                    boundary_from=None, boundary_to=None)])})
        self.assertEqual(lookup(report, "a", 15)["observed_from"], 10)
        with self.assertRaises(ValueError):
            lookup(report, "a", 21)


if __name__ == "__main__":
    unittest.main()
