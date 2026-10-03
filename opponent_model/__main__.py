"""python -m opponent_model --data-dir PATH --output analysis/results/report.json"""

import argparse
import json
from pathlib import Path
from time import perf_counter

from .compute import Compute
from .data import load_dataset, load_cache, save_dataset
from .pipeline import analyze
from .report import markdown


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline CUDA bot estimators and confirmed time segments")
    parser.add_argument("--data-dir", type=Path, help="directory with actions.jsonl, matches.json and state.json")
    parser.add_argument("--cache", type=Path, help="read an existing frozen feature snapshot instead of live inputs")
    parser.add_argument("--save-cache", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, help="Markdown companion; defaults to <output-stem>-summary.md")
    parser.add_argument("--device", default="cuda", help="cuda (default, required if selected); cpu only for explicit parity tests")
    parser.add_argument("--devices", nargs="+", help="distinct CUDA devices for parallel bot shards, e.g. cuda:0 cuda:1")
    parser.add_argument("--batch-size", type=int, help="limit candidate-grid and fit batches without reducing replicates or grid resolution")
    parser.add_argument("--memory-limit-mib", type=int, help="PyTorch allocation cap per GPU; leave room for CUDA context/library overhead")
    parser.add_argument("--bootstrap", type=int, default=500)
    parser.add_argument("--permutations", type=int, default=4999)
    parser.add_argument("--minimum", type=int, default=6, help="minimum discovery AND held-out matches per side")
    parser.add_argument("--grid-step", type=float, default=.05)
    parser.add_argument("--contamination", type=float, default=.05)
    parser.add_argument("--seed", type=int, default=20261003)
    parser.add_argument("--alpha", type=float, default=.05)
    parser.add_argument("--confidence", type=float, default=.95)
    parser.add_argument("--penalty-scale", type=float, default=1)
    parser.add_argument("--max-segments", type=int, default=6)
    parser.add_argument("--bot", action="append", dest="bots", help="optional exact display-name filter; repeatable")
    args = parser.parse_args(argv)
    if bool(args.data_dir) == bool(args.cache):
        parser.error("Choose exactly one of --data-dir or --cache")
    summary_path = args.summary or args.output.with_name(args.output.stem + "-summary.md")
    if summary_path.resolve() == args.output.resolve():
        parser.error("JSON and Markdown output paths must differ")
    start = perf_counter()
    computes = [Compute(device, args.seed, batch_size=args.batch_size, memory_limit_mib=args.memory_limit_mib)
                for device in (args.devices or [args.device])]
    compute = computes if args.devices else computes[0]
    for worker in computes:
        print(json.dumps(dict(event="compute", **worker.metadata())), flush=True)
    if args.cache:
        data = load_cache(args.cache)
    else:
        data = load_dataset(args.data_dir / "actions.jsonl", args.data_dir / "matches.json", args.data_dir / "state.json")
    if args.save_cache:
        args.save_cache.parent.mkdir(parents=True, exist_ok=True)
        save_dataset(data, args.save_cache)
    print(json.dumps(dict(event="input", **data.audit)), flush=True)
    keys = ("bootstrap", "permutations", "minimum", "grid_step", "contamination", "seed",
            "alpha", "confidence", "penalty_scale", "max_segments", "bots")
    report = analyze(data, compute, **{k: getattr(args, k) for k in keys},
                     progress=lambda phase, bot: print(json.dumps(dict(event=phase, bot=bot)), flush=True))
    report["elapsed_seconds"] = perf_counter()-start
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(markdown(report), encoding="utf-8")
    summary = {bot: len(r["segments"]) for bot, r in report["bots"].items()}
    print(json.dumps(dict(event="complete", output=str(args.output.resolve()), segments=summary,
                         summary=str(summary_path.resolve()),
                         seconds=report["elapsed_seconds"], compute=report["compute"])), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
