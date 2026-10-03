"""CUDA oracle/parity checks plus CPU-only scheduling and batching contracts."""

from argparse import Namespace
from dataclasses import asdict
from pathlib import Path
from random import Random
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor/macpoker-src"))
sys.path.insert(0, str(ROOT))

from bot import engine
from harness import eval as harness
from harness.gpu_equity import CudaEvaluator, Driver, find_nvcc
from macpoker.evaluator import evaluate as sdk_evaluate


def gpu_available():
    try:
        find_nvcc()
        return bool(Driver().devices())
    except (OSError, RuntimeError, AttributeError):
        return False


def options(**changes):
    args = dict(device="auto", workers=4, gpu_workers=None, gpu_devices=None,
                gpu_batch_size=128)
    return Namespace(**(args | changes))


class WorkerSelectionTests(unittest.TestCase):
    def test_tournament_without_batch_hook_uses_cpu_without_probing_cuda(self):
        from harness import tournament
        legacy = Namespace(estimate_equity=lambda hole, board, ranges: None)
        with patch.object(harness, 'make_bot'), patch.object(harness, '_loaded', {'legacy': (legacy, object)}), \
                patch.object(harness, 'gpu_module', side_effect=AssertionError('CUDA touched')):
            plan = tournament.field_compute_plan(options(), ['legacy'])
        self.assertEqual(plan['device'], 'cpu')
        self.assertIn('compatible', plan['fallback_reason'])

    def test_cpu_never_imports_or_probes_cuda(self):
        with patch.object(harness, "gpu_module", side_effect=AssertionError("CUDA touched")):
            self.assertEqual(harness.compute_plan(options(device="cpu"))["device"], "cpu")

    def test_auto_falls_back_and_explicit_cuda_fails(self):
        with patch.object(harness, "gpu_module", side_effect=OSError("driver unavailable")):
            plan = harness.compute_plan(options())
            self.assertEqual(plan["device"], "cpu")
            self.assertIn("driver unavailable", plan["fallback_reason"])
            with self.assertRaisesRegex(RuntimeError, "CUDA requested"):
                harness.compute_plan(options(device="cuda"))

    def test_default_one_worker_per_gpu_and_explicit_shared_workers(self):
        backend = Mock()
        backend.Driver.return_value.devices.return_value = [dict(index=i, name="V100") for i in range(4)]
        with patch.object(harness, "gpu_module", return_value=backend):
            plan = harness.compute_plan(options(gpu_devices="3,1"))
            self.assertEqual(plan["workers"], 2)
            self.assertEqual([d["index"] for d in plan["devices"]], [3, 1])
            self.assertEqual(harness.compute_plan(options(gpu_workers=3))["workers"], 3)
            shared=harness.compute_plan(options(gpu_workers=12))
            self.assertEqual(shared['workers'],12)
            self.assertEqual(len(shared['devices']),4)
            for args in (options(gpu_workers=0), options(gpu_devices="1,1"), options(gpu_devices="9")):
                with self.assertRaises(ValueError):
                    harness.compute_plan(args)

    def test_shared_workers_each_receive_a_device_and_complete_startup(self):
        context,devices,ready=Mock(),Mock(),Mock()
        context.Queue.side_effect=[devices,ready]
        ready.get.side_effect=[dict(device=f'cuda:{i%2}') for i in range(6)]
        plan=dict(requested='cuda',device='cuda',workers=6,devices=[dict(index=0),dict(index=1)],batch_size=128)
        with patch.object(harness.mp,'get_context',return_value=context):
            pool,selected=harness.worker_pool(plan,options())
        self.assertEqual([call.args[0] for call in devices.put.call_args_list],[0,1,0,1,0,1])
        self.assertEqual(ready.get.call_count,6)
        self.assertEqual(len(selected['worker_startup']),6)

    def test_gates_and_incompatible_bots_are_not_marked_accelerated(self):
        with patch.object(harness, "gpu_module", side_effect=AssertionError("CUDA touched")):
            self.assertEqual(harness.compute_plan(options(), gating=True)["device"], "cpu")
            self.assertEqual(harness.compute_plan(options(), compatible=False)["device"], "cpu")
            with self.assertRaisesRegex(ValueError, "tournament clocks"):
                harness.compute_plan(options(device="cuda"), gating=True)
            with self.assertRaisesRegex(ValueError, "compatible"):
                harness.compute_plan(options(device="cuda"), compatible=False)

    def test_failed_worker_startup_cleans_up_before_cpu_fallback(self):
        for mode in ("auto", "cuda"):
            context, devices, ready = Mock(), Mock(), Mock()
            context.Queue.side_effect = [devices, ready]
            ready.get.return_value = dict(error="out of GPU memory")
            plan = dict(requested=mode, device="cuda", workers=1,
                        devices=[dict(index=0)], batch_size=128)
            with patch.object(harness.mp, "get_context", return_value=context):
                if mode == "auto":
                    pool, selected = harness.worker_pool(plan, options(workers=1))
                    self.assertIsNone(pool)
                    self.assertEqual(selected["device"], "cpu")
                    self.assertIn("out of GPU memory", selected["fallback_reason"])
                else:
                    with self.assertRaisesRegex(RuntimeError, "out of GPU memory"):
                        harness.worker_pool(plan, options())
            context.Pool.return_value.terminate.assert_called_once()
            context.Pool.return_value.join.assert_called_once()
            devices.close.assert_called_once()
            ready.close.assert_called_once()

    def test_startup_interrupt_terminates_workers_and_propagates(self):
        context, devices, ready = Mock(), Mock(), Mock()
        context.Queue.side_effect = [devices, ready]
        ready.get.side_effect = KeyboardInterrupt
        plan = dict(requested="auto", device="cuda", workers=1,
                    devices=[dict(index=0)], batch_size=128)
        with patch.object(harness.mp, "get_context", return_value=context):
            with self.assertRaises(KeyboardInterrupt):
                harness.worker_pool(plan, options())
        context.Pool.return_value.terminate.assert_called_once()
        context.Pool.return_value.join.assert_called_once()
        devices.close.assert_called_once()
        ready.close.assert_called_once()


class BatchContractTests(unittest.TestCase):
    def test_batched_cpu_oracle_preserves_sampling_and_weighted_exact_results(self):
        def many(hands):
            return [engine._evaluate(hand) for hand in hands]
        cases = [
            (["As", "Ks"], [], [None] * 8, 137),
            (["As", "Ks"], ["Qs", "7s", "2d"], [None] * 3, 137),
            (["9h", "8h"], ["Ac", "Ad", "Ah", "As", "2d"],
             [{("Kh", "Qh"): 1, ("7h", "6h"): 3},
              {("Kh", "5c"): 2, ("4c", "3c"): 1}], 1000),
        ]
        for hole, board, ranges, draws in cases:
            expected = engine.estimate_equity(hole, board, ranges, draws, None, seed=14)
            for batch in (1, 17, 128):
                actual = engine.estimate_equity(hole, board, ranges, draws, None, seed=14,
                                               _evaluate_batch=many, _batch_size=batch)
                self.assertEqual(asdict(actual), asdict(expected))

    def test_partial_batch_is_flushed_at_deadline(self):
        calls = []
        def many(hands):
            calls.append(len(hands))
            return [engine._evaluate(hand) for hand in hands]
        # Start/preparation take three checks; three draws finish before the
        # next attempt hits the deadline. Those pending samples must survive.
        with patch.object(engine, "perf_counter", side_effect=[0, 0, 0, 0, 0, 0, 1]):
            report = engine.estimate_equity(["As", "Ks"], [], [None], 50, 100,
                                            seed=1, _evaluate_batch=many, _batch_size=128)
        self.assertEqual(report.samples, 3)
        self.assertEqual(report.stop_reason, "time_budget")
        self.assertEqual(calls, [6])

    def test_zero_budget_does_not_launch_cuda(self):
        with self.assertRaises(engine.EquityTimeout):
            engine.estimate_equity(["As", "Ks"], [], [None], 50, 0,
                                   _evaluate_batch=Mock(side_effect=AssertionError("launched")))


@unittest.skipUnless(gpu_available(), "CUDA driver and toolkit required")
class CudaParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gpu = CudaEvaluator(0, 128)

    @classmethod
    def tearDownClass(cls):
        cls.gpu.close()

    def test_all_hand_categories_and_random_hands_match_independent_sdk(self):
        examples = ["As Ks Qs Js Ts 2d 2c", "As 2s 3s 4s 5s Kd Qh",
                    "As Ah Ac Ad Ks Qs Js", "As Ah Ac Ks Kh Kc 2d",
                    "As 9s 7s 5s 3s Ks Qs", "As 2c 3h 4d 5s 6h 7s",
                    "As Ah Ac Ks Qs Js 9s", "As Ah Ks Kh Qs Qh 2s",
                    "As Ah Ks Qh Js 9h 2c", "As Kd Qh Js 9c 8h 2d"]
        hands = [tuple(engine._parse_card(c) for c in text.split()) for text in examples]
        rng = Random(772)
        hands += [tuple(rng.sample(range(52), 7)) for _ in range(10000)]
        actual = self.gpu.evaluate(hands)
        for hand, value in zip(hands, actual):
            self.assertEqual((value[0], *(rank - 2 for rank in value[1:])), sdk_evaluate(list(hand)))

    def test_invalid_cards_are_rejected_before_kernel_launch(self):
        before = self.gpu.batches
        for hand in ((0, 1, 2), (-1, 1, 2, 3, 4, 5, 6), (0, 1, 2, 3, 4, 5, 52)):
            with self.assertRaises(ValueError):
                self.gpu.evaluate([hand])
        self.assertEqual(self.gpu.batches, before)

    def test_gpu_equity_matches_cpu_on_every_street_and_table_size(self):
        for board in ([], ["Qs", "7s", "2d"], ["Qs", "7s", "2d", "3h"],
                      ["Qs", "7s", "2d", "3h", "9c"]):
            for opponents in (1, 4, 8):
                args = (["As", "Ks"], board, [None] * opponents, 257, None)
                cpu = engine.estimate_equity(*args, seed=8)
                gpu = engine.estimate_equity(*args, seed=8, _evaluate_batch=self.gpu.evaluate)
                self.assertEqual(asdict(gpu), asdict(cpu))

    def test_weighted_rejection_and_exact_enumeration_match_cpu(self):
        ranges = [{("Kh", "Qh"): 1, ("7h", "6h"): 3},
                  {("Kh", "5c"): 2, ("4c", "3c"): 1}]
        for budget in (None, 60_000):
            args = (["9h", "8h"], ["Ac", "Ad", "Ah", "As", "2d"], ranges, 500, budget)
            cpu = engine.estimate_equity(*args, seed=41)
            gpu = engine.estimate_equity(*args, seed=41, _evaluate_batch=self.gpu.evaluate)
            self.assertEqual(asdict(gpu), asdict(cpu))

    def test_harness_runs_real_cuda_work(self):
        # Exercise the same loading/injection path used by spawned workers.
        # The harness deliberately evicts sibling bot modules. Restore them so
        # subsequent suites patch the same modules as their imported classes.
        with patch.dict(sys.modules), patch.object(harness, "_bot_dirs", set()), \
                patch.object(harness, "_gpu_evaluator", self.gpu), patch.object(harness, "_loaded", {}):
            result = harness.play_game(dict(candidate="bot", opponents=["param:station", "param:tag", "param:lag"],
                                            cand_idx=0, table=0, game=0, seed="gpu-integration",
                                            deals=20, time_ms=30_000, increment_ms=100))
        self.assertEqual(result["verdicts"], ["OK"] * 4)
        self.assertEqual(result["compute"]["device"], "cuda:0")
        self.assertGreater(result["compute"]["ranked_hands"], 0)
        self.assertGreater(result["compute"]["batches"], 0)


if __name__ == "__main__":
    unittest.main()
