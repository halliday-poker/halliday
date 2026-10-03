"""Write a catalogue of latest opponent parameters and optional NumPy policies.

    python sparring/competitors/build.py analysis/results/opponent-estimates.json
"""

import argparse
from collections import Counter
from hashlib import sha256
import json
import keyword
from pathlib import Path
import re
import shutil
import unicodedata


ROOT = Path(__file__).resolve().parents[2]
if __package__:
    from .catalog import record, spec, validate_style, write_catalog
else:
    from catalog import record, spec, validate_style, write_catalog


def slug(name):
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "bot"
    if value[0].isdigit() or keyword.iskeyword(value):
        value = "bot_" + value
    return value


def latest_profiles(report):
    """Prefer trusted play-time keys when present, else collection chronology."""
    names = sorted(report["bots"])
    counts = Counter(slug(name) for name in names)
    profiles = {}
    for name in names:
        segments = report["bots"][name]["segments"]
        if not segments:
            raise ValueError(f"{name}: no fitted segments")
        segment = max(segments, key=lambda s: tuple(s.get('selection_key',(False,s['observed_through'])))+(s['observed_from'],))
        style = segment["surrogate_style"]
        validate_style(name, style)
        stem = slug(name)
        if counts[stem] > 1 or stem in {"build", "competitor_base"}:
            stem += "_" + sha256(name.encode()).hexdigest()[:8]
        profiles[name] = dict(id=stem, **segment)
    if len({p["id"] for p in profiles.values()}) != len(profiles):
        raise ValueError("Competitor IDs collide")
    return profiles


def build(report_path, destination, exclude=("Halliday",), policy_path=None):
    raw = Path(report_path).read_bytes()
    report = json.loads(raw)
    fingerprint = sha256((ROOT / "sparring/param.py").read_bytes()).hexdigest()
    if report["surrogate_source_sha256"] != fingerprint:
        raise ValueError("param.py differs from the fitted scaffold; regenerate the analysis first")
    profiles = latest_profiles(report)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    if report.get('behavior_model_sha256'):
        if policy_path is None:
            raise ValueError('This report requires the refitted behavior policy; pass --policy')
        if sha256(Path(policy_path).read_bytes()).hexdigest()!=report['behavior_model_sha256']:
            raise ValueError('Policy fingerprint differs from the selected report')
        shutil.copyfile(policy_path,destination/'behavior-policy.npz')
    excluded = set(exclude)
    unknown = excluded - set(profiles)
    if unknown:
        raise ValueError(f"Unknown excluded identities: {sorted(unknown)}")
    write_catalog(destination/'bots.json', {p['id']: record(name, p) for name, p in profiles.items()})
    # Remove only wrappers produced by previous versions of this generator.
    # This also removes obsolete identities when the report's roster shrinks.
    for path in destination.glob('*.py'):
        if path.read_text().startswith('"""Generated fitted opponent:'):
            path.unlink()
    manifest = dict(schema_version=3, catalog='bots.json', report_sha256=sha256(raw).hexdigest(),
                    analysis_generated_at_utc=report["generated_at_utc"],
                    surrogate_source_sha256=fingerprint, input_audit=report["input_audit"],
                    analysis_settings=report["settings"], pool_excluded=sorted(excluded),
                    selection="Explicit trusted-time selection_key when present, otherwise latest observed_through; per display name",
                    style_policy="Use latest-segment executable surrogate_style and optional public-context policy. Retain uncertainty, sparse-segment shrinkage and fallback status; defaults are not measured values.",
                    behavior_model_sha256=report.get('behavior_model_sha256'),
                    predictive_comparison=report.get('predictive_comparison'),
                    profiles=profiles)
    (destination / "profiles.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    # The harness resolves specs relative to its repository root.
    prefix = destination.resolve().relative_to(ROOT).as_posix()
    for filename, omitted in (("pool.txt", excluded), ("all.txt", set())):
        lines = ["# Equal weight per recorded identity; latest fitted segment."]
        if omitted:
            lines.append("# Current bot replaces: " + ", ".join(sorted(omitted)))
        lines += [f"{spec(prefix+'/bots.json', p['id'])} 1" for name, p in profiles.items() if name not in omitted]
        (destination / filename).write_text("\n".join(lines) + "\n")
    if all('known_play_times' in p and 'validation_only' in p for p in profiles.values()):
        lines = ['# Latest trusted observed ladder interval per external identity.']
        lines += [f"{spec(prefix+'/bots.json', p['id'])} 1" for name, p in profiles.items()
                  if name not in excluded and not name.startswith('house:')
                  and p['known_play_times'] and not p['validation_only']]
        (destination/'latest-pool.txt').write_text('\n'.join(lines)+'\n')
    else:
        (destination/'latest-pool.txt').unlink(missing_ok=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--exclude", action="append", help="identity replaced by the candidate; default Halliday")
    parser.add_argument('--policy',type=Path,help='Refitted NumPy policy required by a schema-2 behavior report')
    parser.add_argument('--destination', type=Path, default=Path(__file__).resolve().parent/'from_data')
    args = parser.parse_args()
    manifest = build(args.report, args.destination,
                     ("Halliday",) if args.exclude is None else args.exclude,policy_path=args.policy)
    print(f"Generated {len(manifest['profiles'])} competitors; "
          f"{len(manifest['profiles']) - len(manifest['pool_excluded'])} in the evaluation pool")


if __name__ == "__main__":
    main()
