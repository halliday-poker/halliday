"""Evaluation harness: score bot versions against a pool of opponents.

    python harness/eval.py run bot                     # gate: must beat each league version
    python harness/eval.py promote v3 --note "..."     # accept a gated version into the league
    python harness/eval.py run bot/ snapshots/v1/      # plain A/B, first = baseline
    python harness/eval.py smoke bot/
    python harness/eval.py snapshot v2
    python harness/eval.py package

`run` draws random tables (4-6 seats) from an opponent pool and plays a full
duplicate set at each one (one game per seat, same decks, seats shifted).
When several candidates are given, each plays the identical tables and seeds
from the same slot, so the difference between them is decisions, not cards
or opponents.

With a single candidate, `run` is a gate: the last K promoted league versions
become baselines (and opponents), and the candidate must be significantly
better than each of them. Inconclusive gates extend automatically.

A bot spec is a .py file, a directory containing main.py, house:<name>, or
param:<archetype>[@seed] (see sparring/param.py). In a pool file,
param:random draws a jittered random archetype for every seat it fills.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
import math
import multiprocessing as mp
import os
import random
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from collections import defaultdict
from functools import partial
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "harness"
RESULTS = HARNESS / "results"
LEAGUE = HARNESS / "league.json"
DEFAULT_POOL = HARNESS / "pools" / "default.txt"
PARAM_BOT = ROOT / "sparring" / "param.py"

from macpoker.bots import BUILTINS  # noqa: E402
from macpoker.match import VERDICT_OK, MatchConfig, MatchRunner  # noqa: E402
from macpoker.sdk import Bot  # noqa: E402
from macpoker.transport import BotDied, InProcessTransport, ProtocolError  # noqa: E402


# --------------------------------------------------------------------------
# Bot loading
#
# Every version of our bot imports sibling modules with the same names
# (engine.py, strategy.py, ...). To seat two versions at once in one process,
# each load gets its own copy of its siblings: before and after importing a
# bot we evict every module that lives in any bot directory seen so far.
# Bots must import their siblings at module top level for this to work.
# --------------------------------------------------------------------------

_bot_dirs: set[Path] = set()
_loaded: dict[str, tuple] = {}
_load_count = 0
_gpu_evaluator = None
_worker_init_error = None


def gpu_module():
    if __package__:
        from . import gpu_equity
    else:
        import gpu_equity
    return gpu_equity


def supports_gpu(module):
    function = getattr(module, "estimate_equity", None)
    try:
        return callable(function) and "_evaluate_batch" in inspect.signature(function).parameters
    except (TypeError, ValueError):
        return False


def resolve_path(spec: str) -> Path:
    p = Path(spec)
    if not p.is_absolute():
        p = ROOT / p if (ROOT / p).exists() else Path.cwd() / p
    if p.is_dir():
        p = p / "main.py"
    if not p.is_file():
        raise SystemExit(f"bot not found: {spec}")
    return p.resolve()


def _evict_bot_modules() -> None:
    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None)
        if f and any(d in Path(f).resolve().parents for d in _bot_dirs):
            del sys.modules[name]


def _load_module(path: Path):
    global _load_count
    _load_count += 1
    d = path.parent
    _bot_dirs.add(d)
    _evict_bot_modules()
    sys.path.insert(0, str(d))
    try:
        spec = importlib.util.spec_from_file_location(f"_harness_bot_{_load_count}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if _gpu_evaluator is not None and supports_gpu(module):
            module.estimate_equity = partial(module.estimate_equity,
                                            _evaluate_batch=_gpu_evaluator.evaluate,
                                            _batch_size=_gpu_evaluator.batch_size)
    finally:
        sys.path.remove(str(d))
        _evict_bot_modules()
    candidate = getattr(module, "bot", None)
    if isinstance(candidate, Bot):
        return module, type(candidate)
    classes = [v for v in vars(module).values()
               if isinstance(v, type) and issubclass(v, Bot) and v is not Bot
               and v.__module__ == module.__name__]
    if len(classes) != 1:
        raise ValueError(f"{path} must define `bot = YourBot()` or exactly one Bot subclass")
    return module, classes[0]


def _cached_module(path: Path):
    key = str(path)
    if key not in _loaded:
        _loaded[key] = _load_module(path)
    return _loaded[key]


def param_module():
    return _cached_module(PARAM_BOT)[0]


def make_bot(spec: str, seed: str) -> Bot:
    """A fresh bot instance for one game. Our bots' modules are imported once
    per worker; each game gets a new instance, as the tournament's fresh
    process would give it fresh state on self."""
    if spec.startswith("house:"):
        cls = BUILTINS[spec.split(":", 1)[1]]
        try:
            return cls(seed=seed)
        except TypeError:
            return cls()
    if spec.startswith("param:"):
        module, cls = _cached_module(PARAM_BOT)
        return cls(style=module.style_for(spec.split(":", 1)[1]), seed=seed)
    path = resolve_path(spec)
    module, cls = _cached_module(path)
    # Optional factory for stochastic file bots: keep their private RNG tied
    # to the seat seed, independent of other bots' constructor side effects.
    factory = getattr(module, "make_seeded_bot", None)
    if factory is not None:
        bot = factory(seed)
        if not isinstance(bot, Bot):
            raise TypeError(f"{path}: make_seeded_bot must return a Bot")
        return bot
    try:
        return cls()
    except TypeError:
        _loaded[str(path)] = _load_module(path)
        return _loaded[str(path)][0].bot


def bot_hash(spec: str) -> str:
    """Short content hash of a bot's directory, to identify uncommitted versions."""
    if spec.startswith(("house:", "param:")):
        return spec.split(":", 1)[0]
    h = hashlib.sha1()
    d = resolve_path(spec).parent
    for f in sorted(d.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts and f.suffix not in (".md", ".pyc"):
            h.update(str(f.relative_to(d)).encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:8]


# --------------------------------------------------------------------------
# League: promoted versions of our bot
# --------------------------------------------------------------------------

def load_league() -> list[dict]:
    if not LEAGUE.exists():
        return []
    return json.loads(LEAGUE.read_text())["versions"]


def league_specs(k: int) -> list[str]:
    """The last k promoted versions, newest first."""
    return [f"snapshots/{v['name']}" for v in reversed(load_league()[-k:])] if k > 0 else []


def copy_snapshot(source: str, name: str) -> Path:
    path = resolve_path(source)
    if path.name != "main.py":
        raise SystemExit(f"{source}: snapshots copy a bot directory with main.py, not a single file")
    src = path.parent
    dst = ROOT / "snapshots" / name
    if dst.exists():
        raise SystemExit(f"{dst.relative_to(ROOT)} already exists; pick a new name")
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "README.md"))
    return dst


# --------------------------------------------------------------------------
# Running games
# --------------------------------------------------------------------------

class TimedTransport(InProcessTransport):
    """In-process transport that also records think time and the first crash."""

    def __init__(self, bot, name):
        super().__init__(bot, name)
        self.max_ms = 0.0
        self.total_ms = 0.0
        self.error: str | None = None
        self.player = None
        self.action_counts = defaultdict(lambda: defaultdict(int))
        self.vpip_hands = set()
        self.pfr_hands = set()

    def _record(self, exc: BaseException) -> None:
        if self.error is None:
            cause = exc.__cause__ or exc
            self.error = "".join(traceback.format_exception(cause))[-2000:]

    def send(self, msg):
        if msg.get('type')=='hello':
            self.player=msg['player']
        if msg.get('type')=='action' and msg['players'][msg['seat']]==self.player:
            self.action_counts[msg['street']][msg['action']]+=1
            if msg['street']=='preflop':
                if msg['action'] in ('call','raise'):self.vpip_hands.add(msg['hand'])
                if msg['action']=='raise':self.pfr_hands.add(msg['hand'])
        try:
            super().send(msg)
        except BotDied as exc:
            self._record(exc)
            raise

    def act(self, view, timeout_ms):
        try:
            action, ms = super().act(view, timeout_ms)
        except (BotDied, ProtocolError) as exc:
            self._record(exc)
            raise
        self.max_ms = max(self.max_ms, ms)
        self.total_ms += ms
        return action, ms


def _worker_init(device_queue=None, ready_queue=None, batch_size=128) -> None:
    # Bots print freely; keep worker output off the console. Workers import
    # the same bots at once, so leave bytecode caching to the main process.
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")
    sys.dont_write_bytecode = True
    if device_queue is not None:
        global _gpu_evaluator, _worker_init_error
        try:
            device = device_queue.get(timeout=5)
            _gpu_evaluator = gpu_module().CudaEvaluator(device, batch_size)
            ready_queue.put(_gpu_evaluator.metadata())
        except Exception as exc:
            # Report once rather than letting Pool endlessly respawn failures.
            _worker_init_error = f"{type(exc).__name__}: {exc}"
            ready_queue.put(dict(error=_worker_init_error))


def compute_plan(args, *, gating=False, compatible=True):
    """Detect optional CUDA support without creating a context in the parent."""
    mode = args.device
    if args.workers < 1 or args.gpu_workers is not None and args.gpu_workers < 1:
        raise ValueError("Worker counts must be positive")
    if not 1 <= args.gpu_batch_size <= 4096:
        raise ValueError("GPU batch size must be between 1 and 4096")
    cpu = dict(requested=mode, device="cpu", workers=args.workers, devices=[])
    if mode == "cpu":
        return cpu
    if gating:
        if mode == "cuda":
            raise ValueError("GPU runs cannot validate tournament clocks; use --no-league for GPU exploration or --device cpu for a promotion gate")
        return dict(cpu, fallback_reason="promotion gates use CPU tournament timings")
    if not compatible:
        reason = "no bot in this field exposes a compatible batched equity engine"
        if mode == "cuda":
            raise ValueError(reason)
        return dict(cpu, fallback_reason=reason)
    try:
        backend = gpu_module()
        backend.find_nvcc()
        devices = backend.Driver().devices()
        if not devices:
            raise RuntimeError("no CUDA devices available")
    except (OSError, RuntimeError, AttributeError) as exc:
        if mode == "cuda":
            raise RuntimeError(f"CUDA requested but unavailable: {exc}") from exc
        return dict(cpu, fallback_reason=str(exc))
    if args.gpu_devices:
        selected = [int(d) for d in args.gpu_devices.split(",")]
        available = {d["index"]: d for d in devices}
        if len(selected) != len(set(selected)) or any(d not in available for d in selected):
            raise ValueError("--gpu-devices must list distinct available CUDA indices")
        devices = [available[d] for d in selected]
    if args.gpu_workers is not None:
        devices = devices[:args.gpu_workers]
    return dict(requested=mode, device="cuda", workers=args.gpu_workers or len(devices), devices=devices,
                batch_size=args.gpu_batch_size)


def worker_pool(plan, args):
    """Warm every GPU before play; auto mode can fall back before games start."""
    if plan["device"] == "cuda":
        context = mp.get_context("spawn")
        devices, ready = context.Queue(), context.Queue()
        for index in range(plan['workers']):
            devices.put(plan['devices'][index%len(plan['devices'])]['index'])
        pool = None
        try:
            pool = context.Pool(plan["workers"], initializer=_worker_init,
                                initargs=(devices, ready, plan["batch_size"]))
            started = time.monotonic()
            info = [ready.get(timeout=max(1, 120 - (time.monotonic() - started)))
                    for _ in range(plan['workers'])]
            errors = [item["error"] for item in info if "error" in item]
            if errors:
                raise RuntimeError("; ".join(errors))
            plan["worker_startup"] = sorted(info, key=lambda d: d["device"])
            return pool, plan
        except BaseException as exc:
            if pool is not None:
                pool.terminate()
                pool.join()
            if not isinstance(exc, Exception):
                raise
            if plan["requested"] == "cuda":
                raise RuntimeError(f"GPU worker initialization failed: {exc}") from exc
            plan = dict(requested="auto", device="cpu", workers=args.workers,
                        devices=[], fallback_reason=f"GPU worker initialization failed: {exc}")
        finally:
            devices.close()
            ready.close()
    if plan["workers"] <= 1:
        return None, plan
    return mp.Pool(plan["workers"], initializer=_worker_init), plan


def play_game(job: dict) -> dict:
    """Play one game; harness or engine failures name the exact game."""
    try:
        return _play_game(job)
    except (Exception, SystemExit) as exc:  # SystemExit would kill the worker and hang the pool
        raise RuntimeError(
            f"game failed: candidate={job['candidate']} opponents={job['opponents']} "
            f"table={job['table']} game={job['game']} seed={job['seed']}\n{traceback.format_exc()}"
        ) from exc


def _play_game(job: dict) -> dict:
    """Play game k of one table's duplicate set with one candidate seated."""
    if _worker_init_error:
        raise RuntimeError(_worker_init_error)
    before = _gpu_evaluator.metadata() if _gpu_evaluator else None
    specs = [job["candidate"]] + job["opponents"]
    game_seed = f"{job['seed']}:{job['table']}:{job['game']}"
    random.seed(game_seed)
    try:
        import numpy as np
        np.random.seed(int(hashlib.md5(game_seed.encode()).hexdigest()[:8], 16))
    except ImportError:
        pass
    transports = [TimedTransport(make_bot(s, f"{game_seed}:{i}"), s) for i, s in enumerate(specs)]
    cfg = MatchConfig(
        seats=len(specs),
        deals=job["deals"],
        offset=job["game"],
        seed=f"{job['seed']}:{job['table']}",
        base_time_ms=job["time_ms"],
        increment_ms=job["increment_ms"],
    )
    t0 = time.perf_counter()
    result = MatchRunner(cfg, transports).run()
    compute = dict(device="cpu")
    if before is not None:
        compute = _gpu_evaluator.metadata()
        compute['worker_pid']=os.getpid()
        for key in ("batches", "ranked_hands", "gpu_seconds"):
            compute[key] -= before[key]
    return {
        **{k: job[k] for k in ("cand_idx", "table", "game")},
        "chips": result.chips,
        "verdicts": result.verdicts,
        "max_ms": [round(t.max_ms, 2) for t in transports],
        "think_ms": [round(t.total_ms, 1) for t in transports],
        "errors": [t.error for t in transports],
        "wall_s": round(time.perf_counter() - t0, 3),
        "compute": compute,
        "behavior": [dict(actions={street:dict(counts) for street,counts in t.action_counts.items()},
                          vpip_hands=len(t.vpip_hands),pfr_hands=len(t.pfr_hands)) for t in transports],
    }


# --------------------------------------------------------------------------
# Tables and scoring
# --------------------------------------------------------------------------

def read_pool(path: Path, extra: list[str]) -> list[tuple[str, float]]:
    pool = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            parts = line.split()
            pool.append((parts[0], float(parts[1]) if len(parts) > 1 else 1.0))
    pool += [(s, 1.0) for s in extra]
    return pool


def draw_tables(pool, n_tables: int, sizes: list[int], seed: str) -> list[list[str]]:
    """Each table: a seat count drawn from `sizes`, then opponents drawn by
    weight without replacement (with replacement once the pool runs out).
    param:random can fill any number of seats; each becomes a concrete
    param:<archetype>@<seed>, so every candidate meets the same opponent."""
    archetypes = sorted(param_module().ARCHETYPES) if any(s == "param:random" for s, _ in pool) else []
    tables = []
    for t in range(n_tables):
        rng = random.Random(f"{seed}:table:{t}")
        n_opp = rng.choice(sizes) - 1
        remaining = list(pool)
        opps = []
        for _ in range(n_opp):
            if not remaining:
                remaining = list(pool)
            specs, weights = zip(*remaining)
            pick = rng.choices(range(len(remaining)), weights=weights)[0]
            if specs[pick] == "param:random":
                opps.append(f"param:{rng.choice(archetypes)}@{seed}:{t}:{len(opps)}")
            else:
                opps.append(specs[pick])
                remaining.pop(pick)
        tables.append(opps)
    return tables


def group_key(spec: str) -> str:
    """Breakdown row for an opponent: jittered param bots group by archetype."""
    return spec.split("@", 1)[0] if spec.startswith("param:") else spec


def placement_points(values: list[float]) -> list[float]:
    """n points for 1st down to 1 for last; ties share the average."""
    n = len(values)
    order = sorted(range(n), key=lambda i: -values[i])
    pts = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = sum(n - p for p in range(i, j + 1)) / (j - i + 1)
        for p in range(i, j + 1):
            pts[order[p]] = avg
        i = j + 1
    return pts


def mean_ci(xs: list[float], z: float = 1.96) -> tuple[float, float]:
    """Mean and confidence half-width (z = 1.96 for 95%)."""
    n = len(xs)
    if n == 0:
        return float("nan"), float("nan")
    m = sum(xs) / n
    if n < 2:
        return m, float("inf")
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, z * math.sqrt(var / n)


def compare(diffs: list[float], z: float) -> tuple[float, float, str]:
    m, ci = mean_ci(diffs, z)
    if all(d == 0 for d in diffs):
        return m, ci, "identical"
    return m, ci, "BETTER" if m - ci > 0 else "WORSE" if m + ci < 0 else "inconclusive"


def score_set(games: list[dict], deals: int, bb: int, budget_ms: float) -> dict:
    """Metrics for slot 0 (the candidate) over one table's duplicate set."""
    n = len(games[0]["chips"])
    chips = sum(g["chips"][0] for g in games)
    game_pts_by_bot = [0.0] * n
    for g in games:
        for b, p in enumerate(placement_points(g["chips"])):
            game_pts_by_bot[b] += p
    round_pts = placement_points(game_pts_by_bot)[0]
    return {
        "seats": n,
        "mbb": chips / bb / (deals * len(games)) * 1000,
        "game_pts": game_pts_by_bot[0] / len(games),
        "round_pts": round_pts,
        "won_round": round_pts == n,
        "bad": [g["verdicts"][0] for g in games if g["verdicts"][0] != VERDICT_OK],
        "max_ms": max(g["max_ms"][0] for g in games),
        "bank_used": max(g["think_ms"][0] for g in games) / budget_ms,
        "errors": [g["errors"][0] for g in games if g["errors"][0]],
        "opp_bad": [(spec, g["verdicts"][i + 1]) for g in games
                    for i, spec in enumerate(g["opponents"]) if g["verdicts"][i + 1] != VERDICT_OK],
    }


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip()
        return sha + ("+dirty" if dirty else "")
    except OSError:
        return "?"


def short_name(spec: str) -> str:
    """bot/ -> bot, snapshots/v1 -> v1, sparring/tag.py -> tag, house:call -> call."""
    if spec.startswith(("house:", "param:")):
        return spec.split(":", 1)[1]
    p = Path(spec.rstrip("/\\"))
    return p.parent.name if p.name == "main.py" else p.stem


def fmt(m: float, ci: float, digits=1) -> str:
    return f"{m:+.{digits}f} +-{ci:.{digits}f}"


def evaluate(candidates: list[str], pool, n_tables: int, seed: str, args, n_gate: int = 0,
             plan=None) -> dict:
    """Play every candidate over the same tables, print the report and save it.
    With n_gate > 0, the last candidate is gated against the first n_gate."""
    sizes = [int(s) for s in args.sizes.split(",")]
    if getattr(args,'tables_json',None):
        tables=json.loads(Path(args.tables_json).read_text())
        if not isinstance(tables,list) or not tables or any(not isinstance(t,list) or not 1<=len(t)<=8 for t in tables):
            raise ValueError('tables-json must contain a nonempty list of opponent-spec lists (1–8 opponents)')
        for table in tables:
            if len(set(table))!=len(table):
                raise ValueError('Duplicate opponent identity in predefined table')
            for spec in table:
                make_bot(spec,'predefined-table-check')
    else:
        tables = draw_tables(pool, n_tables, sizes, seed)
    n_tables=len(tables)
    budget_ms = args.time_ms + args.increment_ms * args.deals

    jobs = [
        {"cand_idx": ci, "candidate": cand, "opponents": opps, "table": t, "game": k,
         "seed": seed, "deals": args.deals, "time_ms": args.time_ms,
         "increment_ms": args.increment_ms}
        for t, opps in enumerate(tables)
        for k in range(len(opps) + 1)
        for ci, cand in enumerate(candidates)
    ]
    if plan is None:
        plan = dict(requested="cpu", device="cpu", workers=args.workers, devices=[])
    procs, plan = worker_pool(dict(plan), args)
    print(f"{len(candidates)} candidate(s) x {len(tables)} tables -> {len(jobs)} games "
          f"of {args.deals} hands on {plan['workers']} {plan['device']} workers, seed {seed}")
    if plan.get("fallback_reason"):
        print(f"CPU selection: {plan['fallback_reason']}")
    if plan["device"] == "cuda":
        print("CUDA workers: " + ", ".join(d["device"] for d in plan["worker_startup"]))

    t0 = time.perf_counter()
    rows = []
    if procs is None:
        it = map(play_game, jobs)
    else:
        it = procs.imap_unordered(play_game, jobs, chunksize=1)
    step = max(1, len(jobs) // 20)
    try:
        for i, row in enumerate(it, 1):
            rows.append(row)
            if i % step == 0 or i == len(jobs):
                el = time.perf_counter() - t0
                print(f"\r  {i}/{len(jobs)} games  {el:.0f}s elapsed, ~{el / i * (len(jobs) - i):.0f}s left ",
                      end="", flush=True)
    except BaseException:
        if procs:
            procs.terminate()
        raise
    finally:
        if procs:
            procs.close()
            procs.join()
    print()
    usage = {}
    for row in rows:
        compute = row["compute"]
        if compute["device"] != "cpu":
            total = usage.setdefault(compute["device"], dict(games=0, batches=0, ranked_hands=0, gpu_seconds=0.0))
            total["games"] += 1
            for key in ("batches", "ranked_hands", "gpu_seconds"):
                total[key] += compute[key]
    plan["gpu_usage"] = usage
    if usage:
        print("CUDA work: " + ", ".join(f"{device}: {v['ranked_hands']:,} ranked hands / {v['batches']:,} batches"
                                       for device, v in sorted(usage.items())))

    # group into duplicate sets per (candidate, table)
    sets = defaultdict(list)
    for r in rows:
        r["opponents"] = tables[r["table"]]
        sets[(r["cand_idx"], r["table"])].append(r)
    scored = {key: score_set(sorted(g, key=lambda r: r["game"]), args.deals, 2, budget_ms)
              for key, g in sets.items()}
    ts = range(len(tables))

    names = [c if len(c) <= 28 else "..." + c[-25:] for c in candidates]
    per_cand = []
    print(f"\n{'candidate':<29}{'mbb/hand':>16}{'game pts':>14}{'round pts':>14}"
          f"{'1st %':>7}{'max ms':>8}{'bank':>6}  verdicts")
    for ci, cand in enumerate(candidates):
        s = [scored[(ci, t)] for t in ts]
        mbb = mean_ci([x["mbb"] for x in s])
        gp = mean_ci([x["game_pts"] for x in s])
        rp = mean_ci([x["round_pts"] for x in s])
        won = sum(x["won_round"] for x in s) / len(s) * 100
        bad = [v for x in s for v in x["bad"]]
        max_ms = max(x["max_ms"] for x in s)
        bank = max(x["bank_used"] for x in s) * 100
        verdict = "OK" if not bad else f"{len(bad)} bad ({', '.join(sorted(set(bad)))})"
        print(f"{names[ci]:<29}{fmt(*mbb):>16}{fmt(*gp, 2):>14}{fmt(*rp, 2):>14}"
              f"{won:>6.0f}%{max_ms:>8.0f}{bank:>5.0f}%  {verdict}")
        per_cand.append({"bot": cand, "hash": bot_hash(cand), "mbb": mbb, "game_pts": gp,
                         "round_pts": rp, "won_pct": won, "bad_games": len(bad),
                         "max_ms": max_ms, "bank_pct": bank})

    gate = None
    if n_gate:
        # The candidate must beat every baseline at once, so each interval is
        # widened (Bonferroni) to keep a 5% overall chance of a false pass.
        x = len(candidates) - 1
        z = NormalDist().inv_cdf(1 - 0.05 / (2 * n_gate))
        level = 100 * (1 - 0.05 / n_gate)
        print(f"\ngate: {names[x]} must beat each of "
              f"{', '.join(short_name(c) for c in candidates[:n_gate])} ({level:.1f}% intervals)")
        gate_rows = []
        for b in range(n_gate):
            d_mbb = compare([scored[(x, t)]["mbb"] - scored[(b, t)]["mbb"] for t in ts], z)
            d_rp = mean_ci([scored[(x, t)]["round_pts"] - scored[(b, t)]["round_pts"] for t in ts], z)
            print(f"  vs {short_name(candidates[b]):<12} d_mbb {fmt(*d_mbb[:2]):>16}   "
                  f"d_round_pts {fmt(*d_rp, 2):>12}   {d_mbb[2]}")
            gate_rows.append({"baseline": candidates[b], "d_mbb": d_mbb[:2], "d_round_pts": d_rp,
                              "call": d_mbb[2]})
        calls = [r["call"] for r in gate_rows]
        me = per_cand[x]
        if me["bad_games"]:
            verdict, why = "FAIL", f"{me['bad_games']} games ended TLE/RTE/PV"
        elif me["bank_pct"] > args.max_bank:
            verdict, why = "FAIL", f"used {me['bank_pct']:.0f}% of the clock (limit {args.max_bank}%)"
        elif "identical" in calls:
            verdict, why = "FAIL", "identical to a league version"
        elif "WORSE" in calls:
            verdict, why = "FAIL", "significantly worse than a league version"
        elif all(c == "BETTER" for c in calls):
            verdict, why = "PASS", "significantly better than every league version"
        else:
            verdict, why = "INCONCLUSIVE", "not yet separated from every league version"
        print(f"  GATE {verdict}: {why}")
        gate = {"candidate": candidates[x], "hash": me["hash"], "baselines": candidates[:n_gate],
                "verdict": verdict, "reason": why, "rows": gate_rows, "tables": n_tables, "seed": seed,
                "promotion_eligible": plan["device"] == "cpu"}
    elif len(candidates) > 1:
        print(f"\npaired vs baseline {names[0]} (same tables, same cards):")
        for ci in range(1, len(candidates)):
            d_mbb = compare([scored[(ci, t)]["mbb"] - scored[(0, t)]["mbb"] for t in ts], 1.96)
            d_rp = mean_ci([scored[(ci, t)]["round_pts"] - scored[(0, t)]["round_pts"] for t in ts])
            print(f"  {names[ci]:<29} d_mbb {fmt(*d_mbb[:2]):>16}   d_round_pts {fmt(*d_rp, 2):>12}   "
                  f"{d_mbb[2]}")
            per_cand[ci]["vs_baseline"] = {"d_mbb": d_mbb[:2], "d_round_pts": d_rp, "call": d_mbb[2]}

    # breakdowns: by table size and by opponent present (mbb/hand)
    col = 12
    short = [short_name(c)[:col - 1] for c in candidates]
    print(f"\nmbb/hand by table size and by opponent present:")
    print(f"  {'':<26}{'tables':>7}" + "".join(f"{n:>{col}}" for n in short))
    groups = defaultdict(list)
    for t, opps in enumerate(tables):
        groups[f"{len(opps) + 1} seats"].append(t)
    for key in sorted({group_key(s) for opps in tables for s in opps}):
        groups[key] = [t for t, opps in enumerate(tables) if any(group_key(s) == key for s in opps)]
    for label, group in groups.items():
        vals = "".join(f"{mean_ci([scored[(ci, t)]['mbb'] for t in group])[0]:>+{col}.0f}"
                       for ci in range(len(candidates)))
        print(f"  {label[-26:]:<26}{len(group):>7}{vals}")

    opp_bad = defaultdict(int)
    for x in scored.values():
        for spec, v in x["opp_bad"]:
            opp_bad[(group_key(spec), v)] += 1
    if opp_bad:
        print("\nopponent failures (their results are distorted): " +
              ", ".join(f"{s} {v} x{n}" for (s, v), n in opp_bad.items()))

    for ci, cand in enumerate(candidates):
        errs = [e for t in ts for e in scored[(ci, t)]["errors"]]
        if errs:
            print(f"\n--- {cand}: {len(errs)} crash(es), first traceback ---\n{errs[0]}")

    # save
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    commit = git_commit()
    params = sorted({s for opps in tables for s in opps if s.startswith("param:")})
    out = RESULTS / f"{stamp}.json"
    out.write_text(json.dumps({
        "args": {k: v for k, v in vars(args).items() if k != "func"},
        "seed": seed, "commit": commit, "tables": tables, "summary": per_cand, "gate": gate,
        "param_styles": {s: param_module().style_for(s.split(":", 1)[1]) for s in params},
        "games": rows, "compute": plan,
    }))
    log = RESULTS / "log.csv"
    new = not log.exists()
    with log.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "commit", "label", "bot", "hash", "tables", "seed", "deals",
                        "mbb", "mbb_ci", "round_pts", "round_pts_ci", "game_pts", "won_pct",
                        "bad_games", "max_ms", "bank_pct", "d_mbb_vs_baseline", "d_mbb_ci", "call",
                        "gate"])
        for ci, p in enumerate(per_cand):
            vb = p.get("vs_baseline", {})
            w.writerow([stamp, commit, args.label, p["bot"], p["hash"], n_tables, seed,
                        args.deals, round(p["mbb"][0], 1), round(p["mbb"][1], 1),
                        round(p["round_pts"][0], 3), round(p["round_pts"][1], 3),
                        round(p["game_pts"][0], 3), round(p["won_pct"], 1), p["bad_games"],
                        round(p["max_ms"]), round(p["bank_pct"], 1),
                        round(vb["d_mbb"][0], 1) if vb else "", round(vb["d_mbb"][1], 1) if vb else "",
                        vb.get("call", ""),
                        gate["verdict"] if gate and ci == len(candidates) - 1 else ""])
    print(f"\n{time.perf_counter() - t0:.0f}s. Results: {out.relative_to(ROOT)}, "
          f"appended to {log.relative_to(ROOT)}")
    return {"gate": gate, "file": out}


def cmd_run(args) -> int:
    league = [] if args.no_league else league_specs(args.league)
    for spec in league:
        resolve_path(spec)  # a promoted snapshot must exist
    gating = bool(league) and len(args.bots) == 1
    candidates = league + args.bots if gating else list(args.bots)
    for c in candidates:
        make_bot(c, "check")  # fail fast on import errors, before forking workers
    pool = read_pool(Path(args.pool), args.add + league)
    for spec, _ in pool:
        if spec != "param:random":
            make_bot(spec, "check")  # a typo in the pool should fail here, not in a worker
    plan = compute_plan(args, gating=gating,
                        compatible=any(supports_gpu(module) for module, _ in _loaded.values()))
    n_tables = args.tables or (400 if gating else 200)
    base_seed = args.seed or (f"gate-{dt.datetime.now():%m%d%H%M%S}" if gating else "eval")
    seed = base_seed

    while True:
        report = evaluate(candidates, pool, n_tables, seed, args,
                          n_gate=len(league) if gating else 0, plan=plan)
        gate = report["gate"]
        if not gate or gate["verdict"] != "INCONCLUSIVE" or args.no_extend or getattr(args,'tables_json',None) \
                or n_tables * 2 > args.max_tables:
            break
        n_tables *= 2
        seed = f"{base_seed}+{n_tables}"
        print(f"\n=== gate inconclusive: extending to {n_tables} tables on fresh seed {seed} ===\n")

    if gate:
        print(f"\nFINAL GATE {gate['verdict']} for {gate['candidate']} (hash {gate['hash']}) "
              f"at {gate['tables']} tables: {gate['reason']}")
        if gate["verdict"] == "PASS":
            print("promote it with: python harness/eval.py promote <name> --note \"...\"")
        return 0 if gate["verdict"] == "PASS" else 1
    return 0


def cmd_promote(args) -> int:
    """Freeze a gated version into snapshots/<name>/ and add it to the league."""
    h = bot_hash(args.source)
    league = load_league()
    current = league_specs(args.league)
    evidence = None
    for f in sorted(RESULTS.glob("*.json"), reverse=True) if RESULTS.exists() else []:
        gate = json.loads(f.read_text()).get("gate")
        if gate and gate["hash"] == h:
            evidence = (f, gate)
            break
    if evidence is None:
        problem = f"no gate run found for {args.source} as it is now (hash {h}); run `eval.py run {args.source}`"
    elif evidence[1]["verdict"] != "PASS":
        problem = f"latest gate for hash {h} was {evidence[1]['verdict']} ({evidence[0].name})"
    elif not evidence[1].get("promotion_eligible", True):
        problem = "GPU timings cannot qualify a promotion; rerun the gate with --device cpu"
    elif evidence[1]["baselines"] != current:
        problem = "the league changed since that gate run; run it again"
    else:
        problem = None
    if problem and not args.force:
        raise SystemExit(f"not promoting: {problem}")

    dst = copy_snapshot(args.source, args.name)
    league.append({
        "name": args.name,
        "hash": h,
        "commit": git_commit(),
        "time": dt.datetime.now().isoformat(timespec="seconds"),
        "note": args.note,
        "evidence": evidence[0].name if evidence else None,
        "gate": {k: evidence[1][k] for k in ("verdict", "baselines", "tables", "seed")} if evidence else None,
        "forced": bool(problem),
    })
    LEAGUE.write_text(json.dumps({"versions": league}, indent=2) + "\n")
    print(f"promoted {args.source} as {dst.relative_to(ROOT)} (hash {h})"
          + (f"  [FORCED: {problem}]" if problem else ""))
    print(f"league is now: {', '.join(v['name'] for v in league)}. Commit snapshots/ and harness/league.json.")
    return 0


def cmd_smoke(args) -> int:
    """Tournament-parity check: real subprocesses over the wire protocol."""
    path = resolve_path(args.bot)
    # Two lineups: shove bots end most hands preflop, so the first keeps
    # hands going to the river and the second covers all-in and fold spots.
    lineups = [
        ["house:call", "house:random", str(ROOT / "sparring/station.py"), str(ROOT / "sparring/tag.py")],
        ["house:allin", "house:checkfold", str(ROOT / "sparring/maniac.py"), str(ROOT / "sparring/nit.py")],
    ]
    ok = True
    for opponents in lineups:
        cmd = [sys.executable, "-m", "macpoker", "play", str(path), *opponents, "--subprocess",
               "--deals", str(args.deals), "--seed", args.seed]
        print("running:", " ".join(cmd[2:]))
        proc = subprocess.run(cmd, cwd=path.parent, capture_output=True, text=True)
        print(proc.stdout, proc.stderr)
        line = next((l for l in proc.stdout.splitlines() if l.startswith(str(path))), "")
        ok &= proc.returncode == 0 and line.rstrip().endswith("OK")
    print("SMOKE PASS" if ok else "SMOKE FAIL: see output above")
    return 0 if ok else 1


def cmd_snapshot(args) -> int:
    dst = copy_snapshot(args.source, args.name)
    print(f"copied {args.source} -> {dst.relative_to(ROOT)}  (hash {bot_hash(str(dst))})")
    return 0


def cmd_package(args) -> int:
    src = resolve_path(args.source).parent
    out = ROOT / "dist" / f"submission-{dt.datetime.now():%Y%m%d-%H%M%S}-{bot_hash(str(src))}.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(src.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc":
                z.write(f, f.relative_to(src))
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    print(f"wrote {out.relative_to(ROOT)}: {', '.join(names)}")
    if "main.py" not in names:
        print("WARNING: no main.py at the zip root")
        return 1
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="eval.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="one candidate: gate vs the league; several: A/B, first = baseline")
    r.add_argument("bots", nargs="+", help="candidates: bot dir, .py file, house:<name> or param:<archetype>")
    r.add_argument("--tables", type=int, default=None,
                   help="tables (duplicate sets) per candidate (default 400 gate, 200 A/B)")
    r.add_argument("--seed", default=None, help="seed for table draws and decks (default: fresh for gates)")
    r.add_argument("--pool", default=str(DEFAULT_POOL), help="opponent pool file")
    r.add_argument("--add", nargs="*", default=[], help="extra opponents added to the pool")
    r.add_argument("--sizes", default="4,5,5,6", help="seat counts to draw from (repeat to weight)")
    r.add_argument('--tables-json',help='Explicit ordered opponent tables, for matching observed field composition; overrides --tables and --sizes')
    r.add_argument("--deals", type=int, default=100, help="hands per game")
    r.add_argument("--time-ms", type=int, default=30_000, dest="time_ms")
    r.add_argument("--increment-ms", type=int, default=100, dest="increment_ms")
    r.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    r.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto",
                   help="auto uses available CUDA workers for field/A-B runs; promotion gates stay on CPU")
    r.add_argument("--gpu-devices", help="comma-separated CUDA indices, e.g. 0,1,2,3; default all available")
    r.add_argument("--gpu-workers", type=int, help="GPU worker processes; default one per device, larger counts share devices round-robin and need additional CUDA-context memory")
    r.add_argument("--gpu-batch-size", type=int, default=128,
                   help="equity deals per CUDA batch (1-4096); default 128")
    r.add_argument("--league", type=int, default=3, help="league versions used as gate baselines and opponents")
    r.add_argument("--no-league", action="store_true", help="no league baselines or opponents")
    r.add_argument("--max-tables", type=int, default=1600, help="largest run an inconclusive gate extends to")
    r.add_argument("--no-extend", action="store_true", help="never extend an inconclusive gate")
    r.add_argument("--max-bank", type=float, default=50, help="gate fails above this %% of clock used")
    r.add_argument("--label", default="", help="note stored in the results log")
    r.set_defaults(func=cmd_run)

    pr = sub.add_parser("promote", help="add a version that passed the gate to the league")
    pr.add_argument("name", help="snapshot name, e.g. v3")
    pr.add_argument("--source", default="bot")
    pr.add_argument("--note", default="", help="what changed")
    pr.add_argument("--league", type=int, default=3, help="league size the gate was run with")
    pr.add_argument("--force", action="store_true", help="promote without a passing gate (recorded)")
    pr.set_defaults(func=cmd_promote)

    s = sub.add_parser("smoke", help="two subprocess games vs house and sparring bots, like the tournament")
    s.add_argument("bot", nargs="?", default="bot")
    s.add_argument("--deals", type=int, default=100)
    s.add_argument("--seed", default="smoke")
    s.set_defaults(func=cmd_smoke)

    sn = sub.add_parser("snapshot", help="freeze a bot version into snapshots/<name>/ (not the league)")
    sn.add_argument("name")
    sn.add_argument("--source", default="bot")
    sn.set_defaults(func=cmd_snapshot)

    pk = sub.add_parser("package", help="zip a bot directory for upload into dist/")
    pk.add_argument("source", nargs="?", default="bot")
    pk.set_defaults(func=cmd_package)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
