"""Materialize the latest segment of every analyzed bot, without ML dependencies.

    python sparring/competitors/build.py analysis/results/opponent-estimates.json
"""

import argparse
from collections import Counter
from hashlib import sha256
import json
import keyword
import math
from pathlib import Path
import re
import unicodedata


ROOT = Path(__file__).resolve().parents[2]
PARAMETERS = ("vpip", "pfr", "threebet", "limp", "aggression", "cbet", "bluff",
              "stickiness", "size", "adaptive")


def slug(name):
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "bot"
    if value[0].isdigit() or keyword.iskeyword(value):
        value = "bot_" + value
    return value


def latest_profiles(report):
    """Select by collection chronology, not list order or segment number."""
    names = sorted(report["bots"])
    counts = Counter(slug(name) for name in names)
    profiles = {}
    for name in names:
        segments = report["bots"][name]["segments"]
        if not segments:
            raise ValueError(f"{name}: no fitted segments")
        segment = max(segments, key=lambda s: (s["observed_through"], s["observed_from"]))
        style = segment["surrogate_style"]
        if set(style) != set(PARAMETERS):
            raise ValueError(f"{name}: expected all ten surrogate parameters")
        for key, value in style.items():
            low, high = (.25, 1.5) if key == "size" else (0, 1)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name}: invalid {key}={value}")
        if not style["threebet"] <= style["pfr"] <= style["vpip"] or style["adaptive"] not in (0, 1):
            raise ValueError(f"{name}: inconsistent surrogate style")
        stem = slug(name)
        if counts[stem] > 1 or stem in {"build", "competitor_base"}:
            stem += "_" + sha256(name.encode()).hexdigest()[:8]
        profiles[name] = dict(file=stem + ".py", **segment)
    if len({p["file"] for p in profiles.values()}) != len(profiles):
        raise ValueError("Competitor filenames collide")
    return profiles


def build(report_path, destination, exclude=("Halliday",)):
    raw = Path(report_path).read_bytes()
    report = json.loads(raw)
    # Line endings normalised: Windows checkouts convert LF to CRLF.
    fingerprint = sha256((ROOT / "sparring/param.py").read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if report["surrogate_source_sha256"] != fingerprint:
        raise ValueError("param.py differs from the fitted scaffold; regenerate the analysis first")
    profiles = latest_profiles(report)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    excluded = set(exclude)
    unknown = excluded - set(profiles)
    if unknown:
        raise ValueError(f"Unknown excluded identities: {sorted(unknown)}")
    for name, profile in profiles.items():
        style = {key: profile["surrogate_style"][key] for key in PARAMETERS}
        source = (f'"""Generated fitted opponent: {name!r}. See profiles.json for uncertainty."""\n\n'
                  'import competitor_base\n\n\n'
                  'class CompetitorBot(competitor_base.FittedBot):\n'
                  f'    DISPLAY_NAME = {name!r}\n'
                  f'    STYLE = {style!r}\n\n\n'
                  'def make_seeded_bot(seed):\n'
                  '    return CompetitorBot(seed=seed)\n')
        (destination / profile["file"]).write_text(source, encoding="utf-8")
    manifest = dict(schema_version=1, report_sha256=sha256(raw).hexdigest(),
                    analysis_generated_at_utc=report["generated_at_utc"],
                    surrogate_source_sha256=fingerprint, input_audit=report["input_audit"],
                    analysis_settings=report["settings"], pool_excluded=sorted(excluded),
                    selection="Latest observed_through, then observed_from, per display name",
                    style_policy="Exact latest-segment surrogate_style; retain all uncertainty and fit diagnostics. Missing estimates remain null in parameters; their executable surrogate defaults are not measured values.",
                    profiles=profiles)
    (destination / "profiles.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    # The harness resolves specs relative to its repository root.
    prefix = destination.resolve().relative_to(ROOT).as_posix()
    for filename, omitted in (("pool.txt", excluded), ("all.txt", set())):
        lines = ["# Equal weight per recorded identity; latest fitted segment."]
        if omitted:
            lines.append("# Current bot replaces: " + ", ".join(sorted(omitted)))
        lines += [f"{prefix}/{p['file']} 1" for name, p in profiles.items() if name not in omitted]
        (destination / filename).write_text("\n".join(lines) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--exclude", action="append", help="identity replaced by the candidate; default Halliday")
    args = parser.parse_args()
    manifest = build(args.report, Path(__file__).resolve().parent / "from_data",
                     ("Halliday",) if args.exclude is None else args.exclude)
    print(f"Generated {len(manifest['profiles'])} competitors; "
          f"{len(manifest['profiles']) - len(manifest['pool_excluded'])} in the evaluation pool")


if __name__ == "__main__":
    main()
