"""Evaluation harness: score bot versions against a pool of opponents.

    python harness/eval.py run bot/ snapshots/v1/ --tables 100 --seed s1
    python harness/eval.py smoke bot/
    python harness/eval.py snapshot v2
    python harness/eval.py package

`run` draws random tables (4-6 seats) from an opponent pool and plays a full
duplicate set at each one (one game per seat, same decks, seats shifted).
When several candidates are given, each plays the identical tables and seeds
from the same slot, so the difference between them is decisions, not cards
or opponents. The first candidate is the baseline for paired comparisons.

A bot spec is a .py file, a directory containing main.py, or house:<name>.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "harness"
RESULTS = HARNESS / "results"
DEFAULT_POOL = HARNESS / "pools" / "default.txt"

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
    path = str(resolve_path(spec))
    if path not in _loaded:
        _loaded[path] = _load_module(Path(path))
    module, cls = _loaded[path]
    try:
        return cls()
    except TypeError:
        _loaded[path] = _load_module(Path(path))
        return _loaded[path][0].bot


def bot_hash(spec: str) -> str:
    """Short content hash of a bot's directory, to identify uncommitted versions."""
    if spec.startswith("house:"):
        return "house"
    h = hashlib.sha1()
    d = resolve_path(spec).parent
    for f in sorted(d.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts and f.suffix not in (".md", ".pyc"):
            h.update(str(f.relative_to(d)).encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:8]


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

    def _record(self, exc: BaseException) -> None:
        if self.error is None:
            cause = exc.__cause__ or exc
            self.error = "".join(traceback.format_exception(cause))[-2000:]

    def send(self, msg):
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


def _worker_init() -> None:
    # Bots print freely; keep worker output off the console.
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")


def play_game(job: dict) -> dict:
    """Play game k of one table's duplicate set with one candidate seated."""
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
    return {
        **{k: job[k] for k in ("cand_idx", "table", "game")},
        "chips": result.chips,
        "verdicts": result.verdicts,
        "max_ms": [round(t.max_ms, 2) for t in transports],
        "think_ms": [round(t.total_ms, 1) for t in transports],
        "errors": [t.error for t in transports],
        "wall_s": round(time.perf_counter() - t0, 3),
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
    weight without replacement (with replacement once the pool runs out)."""
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
            opps.append(specs[pick])
            remaining.pop(pick)
        tables.append(opps)
    return tables


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


def mean_ci(xs: list[float]) -> tuple[float, float]:
    """Mean and 95% confidence half-width."""
    n = len(xs)
    if n == 0:
        return float("nan"), float("nan")
    m = sum(xs) / n
    if n < 2:
        return m, float("inf")
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, 1.96 * math.sqrt(var / n)


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
    if spec.startswith("house:"):
        return spec.split(":", 1)[1]
    p = Path(spec.rstrip("/\\"))
    return p.parent.name if p.name == "main.py" else p.stem


def fmt(m: float, ci: float, digits=1) -> str:
    return f"{m:+.{digits}f} +-{ci:.{digits}f}"


def cmd_run(args) -> int:
    candidates = args.bots
    for c in candidates:
        make_bot(c, "check")  # fail fast on import errors, before forking workers
    pool = read_pool(Path(args.pool), args.add)
    sizes = [int(s) for s in args.sizes.split(",")]
    tables = draw_tables(pool, args.tables, sizes, args.seed)
    budget_ms = args.time_ms + args.increment_ms * args.deals

    jobs = [
        {"cand_idx": ci, "candidate": cand, "opponents": opps, "table": t, "game": k,
         "seed": args.seed, "deals": args.deals, "time_ms": args.time_ms,
         "increment_ms": args.increment_ms}
        for t, opps in enumerate(tables)
        for k in range(len(opps) + 1)
        for ci, cand in enumerate(candidates)
    ]
    print(f"{len(candidates)} candidate(s) x {len(tables)} tables -> {len(jobs)} games "
          f"of {args.deals} hands on {args.workers} workers")

    t0 = time.perf_counter()
    rows = []
    if args.workers <= 1:
        it = map(play_game, jobs)
    else:
        procs = mp.Pool(args.workers, initializer=_worker_init)
        it = procs.imap_unordered(play_game, jobs, chunksize=1)
    step = max(1, len(jobs) // 20)
    for i, row in enumerate(it, 1):
        rows.append(row)
        if i % step == 0 or i == len(jobs):
            el = time.perf_counter() - t0
            print(f"\r  {i}/{len(jobs)} games  {el:.0f}s elapsed, ~{el / i * (len(jobs) - i):.0f}s left ",
                  end="", flush=True)
    print()
    if args.workers > 1:
        procs.close()

    # group into duplicate sets per (candidate, table)
    sets = defaultdict(list)
    for r in rows:
        r["opponents"] = tables[r["table"]]
        sets[(r["cand_idx"], r["table"])].append(r)
    scored = {key: score_set(sorted(g, key=lambda r: r["game"]), args.deals, 2, budget_ms)
              for key, g in sets.items()}

    names = [c if len(c) <= 28 else "..." + c[-25:] for c in candidates]
    per_cand = []
    print(f"\n{'candidate':<29}{'mbb/hand':>16}{'game pts':>14}{'round pts':>14}"
          f"{'1st %':>7}{'max ms':>8}{'bank':>6}  verdicts")
    for ci, cand in enumerate(candidates):
        s = [scored[(ci, t)] for t in range(len(tables))]
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

    if len(candidates) > 1:
        print(f"\npaired vs baseline {names[0]} (same tables, same cards):")
        for ci in range(1, len(candidates)):
            d_mbb = mean_ci([scored[(ci, t)]["mbb"] - scored[(0, t)]["mbb"] for t in range(len(tables))])
            d_rp = mean_ci([scored[(ci, t)]["round_pts"] - scored[(0, t)]["round_pts"]
                            for t in range(len(tables))])
            lo, hi = d_mbb[0] - d_mbb[1], d_mbb[0] + d_mbb[1]
            call = ("identical" if lo == hi == 0 else "BETTER" if lo > 0
                    else "WORSE" if hi < 0 else "inconclusive")
            print(f"  {names[ci]:<29} d_mbb {fmt(*d_mbb):>16}   d_round_pts {fmt(*d_rp, 2):>12}   {call}")
            per_cand[ci]["vs_baseline"] = {"d_mbb": d_mbb, "d_round_pts": d_rp, "call": call}

    # breakdowns: by table size and by opponent present (mbb/hand)
    col = 12
    short = [short_name(c)[:col - 1] for c in candidates]
    print(f"\nmbb/hand by table size and by opponent present:")
    print(f"  {'':<26}{'tables':>7}" + "".join(f"{n:>{col}}" for n in short))
    groups = defaultdict(list)
    for t, opps in enumerate(tables):
        groups[f"{len(opps) + 1} seats"].append(t)
    for spec in sorted({s for opps in tables for s in opps}):
        groups[spec] = [t for t, opps in enumerate(tables) if spec in opps]
    for label, ts in groups.items():
        vals = "".join(f"{mean_ci([scored[(ci, t)]['mbb'] for t in ts])[0]:>+{col}.0f}"
                       for ci in range(len(candidates)))
        print(f"  {label[-26:]:<26}{len(ts):>7}{vals}")

    opp_bad = defaultdict(int)
    for x in scored.values():
        for spec, v in x["opp_bad"]:
            opp_bad[(spec, v)] += 1
    if opp_bad:
        print("\nopponent failures (their results are distorted): " +
              ", ".join(f"{s} {v} x{n}" for (s, v), n in opp_bad.items()))

    for ci, cand in enumerate(candidates):
        errs = [e for t in range(len(tables)) for e in scored[(ci, t)]["errors"]]
        if errs:
            print(f"\n--- {cand}: {len(errs)} crash(es), first traceback ---\n{errs[0]}")

    # save
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    commit = git_commit()
    out = RESULTS / f"{stamp}.json"
    out.write_text(json.dumps({
        "args": {k: v for k, v in vars(args).items() if k != "func"},
        "commit": commit, "tables": tables, "summary": per_cand, "games": rows,
    }))
    log = RESULTS / "log.csv"
    new = not log.exists()
    with log.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "commit", "label", "bot", "hash", "tables", "seed", "deals",
                        "mbb", "mbb_ci", "round_pts", "round_pts_ci", "game_pts", "won_pct",
                        "bad_games", "max_ms", "bank_pct", "d_mbb_vs_baseline", "d_mbb_ci", "call"])
        for p in per_cand:
            vb = p.get("vs_baseline", {})
            w.writerow([stamp, commit, args.label, p["bot"], p["hash"], args.tables, args.seed,
                        args.deals, round(p["mbb"][0], 1), round(p["mbb"][1], 1),
                        round(p["round_pts"][0], 3), round(p["round_pts"][1], 3),
                        round(p["game_pts"][0], 3), round(p["won_pct"], 1), p["bad_games"],
                        round(p["max_ms"]), round(p["bank_pct"], 1),
                        round(vb["d_mbb"][0], 1) if vb else "", round(vb["d_mbb"][1], 1) if vb else "",
                        vb.get("call", "")])
    print(f"\n{time.perf_counter() - t0:.0f}s total. Results: {out.relative_to(ROOT)}, "
          f"appended to {log.relative_to(ROOT)}")
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
    src = resolve_path(args.source).parent
    dst = ROOT / "snapshots" / args.name
    if dst.exists():
        raise SystemExit(f"{dst.relative_to(ROOT)} already exists; pick a new name")
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "README.md"))
    print(f"copied {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}  (hash {bot_hash(str(dst))})")
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

    r = sub.add_parser("run", help="score candidates over random tables (first = baseline)")
    r.add_argument("bots", nargs="+", help="candidates: bot dir, .py file or house:<name>")
    r.add_argument("--tables", type=int, default=200, help="tables (duplicate sets) per candidate")
    r.add_argument("--seed", default="eval", help="seed for table draws and decks")
    r.add_argument("--pool", default=str(DEFAULT_POOL), help="opponent pool file")
    r.add_argument("--add", nargs="*", default=[], help="extra opponents added to the pool")
    r.add_argument("--sizes", default="4,5,5,6", help="seat counts to draw from (repeat to weight)")
    r.add_argument("--deals", type=int, default=100, help="hands per game")
    r.add_argument("--time-ms", type=int, default=30_000, dest="time_ms")
    r.add_argument("--increment-ms", type=int, default=100, dest="increment_ms")
    r.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    r.add_argument("--label", default="", help="note stored in the results log")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("smoke", help="two subprocess games vs house and sparring bots, like the tournament")
    s.add_argument("bot", nargs="?", default="bot")
    s.add_argument("--deals", type=int, default=100)
    s.add_argument("--seed", default="smoke")
    s.set_defaults(func=cmd_smoke)

    sn = sub.add_parser("snapshot", help="freeze a bot version into snapshots/<name>/")
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
