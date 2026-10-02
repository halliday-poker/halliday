"""Reusable analysis API; outputs JSON-compatible estimates keyed by bot."""

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import torch

from .fit import BotModel, PARAMETERS
from .segments import propose_changes, confirm_family


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def analyze(dataset, compute, *, bootstrap=500, permutations=4999, minimum=6,
            grid_step=.05, contamination=.05, seed=20261003, alpha=.05,
            confidence=.95, penalty_scale=1.0, max_segments=6, bots=None, progress=None):
    if bootstrap < 20 or not 0 < confidence < 1 or not 0 < alpha < 1:
        raise ValueError("At least 20 bootstrap replicates and valid confidence/alpha are required")
    names = sorted(bots if bots is not None else dataset.observations)
    plans, individual = {}, {}
    for bot in names:
        if progress:
            progress("discover", bot)
        model = BotModel(dataset.observations[bot], dataset.hands[bot], compute,
                         grid_step=grid_step, contamination=contamination)
        individual[bot] = model.per_match()
        times = [dataset.matches[i]["collected_at"] for i in model.matches]
        ids = [dataset.matches[i]["id"] for i in model.matches]
        plans[bot] = propose_changes(individual[bot], times, ids, compute, seed=seed,
                                     minimum=minimum, penalty_scale=penalty_scale,
                                     max_segments=max_segments, permutations=permutations)
        del model
    confirm_family(list(plans.values()), alpha=alpha)
    results = {}
    for bot in names:
        if progress:
            progress("estimate", bot)
        model = BotModel(dataset.observations[bot], dataset.hands[bot], compute,
                         grid_step=grid_step, contamination=contamination)
        times = [dataset.matches[i]["collected_at"] for i in model.matches]
        cuts = plans[bot]["accepted_cut_times"]
        bounds = [-float("inf"), *cuts, float("inf")]
        segments = []
        for number, (lower, upper) in enumerate(zip(bounds, bounds[1:]), 1):
            selected = [i for i, t in enumerate(times) if lower <= t < upper]
            report = model.estimate(selected, bootstrap=bootstrap, confidence=confidence)
            first, last = min(times[i] for i in selected), max(times[i] for i in selected)
            variance = {}
            for i, name in enumerate(PARAMETERS):
                x = individual[bot][selected, i]
                x = x[torch.isfinite(x)]
                variance[name] = x.var(unbiased=True).item() if len(x) > 1 else None
            selected_ids = [dataset.matches[model.matches[i]]["id"] for i in selected]
            segments.append(dict(segment=number, observed_from=first, observed_through=last,
                                 observed_from_utc=iso(first), observed_through_utc=iso(last),
                                 boundary_from=lower if number > 1 else None,
                                 boundary_to=upper if number < len(bounds)-1 else None,
                                 match_ids=selected_ids, matches=len(selected),
                                 between_match_parameter_variance=variance, **report))
        results[bot] = dict(segmentation=plans[bot], segments=segments)
        del model
    param_source = Path(__file__).resolve().parents[1] / "sparring" / "param.py"
    return dict(schema_version=1, generated_at_utc=datetime.now(timezone.utc).isoformat(),
                compute=compute.metadata(), input_audit=dataset.audit,
                timeline_diagnostics=dict(seed_from_raw_matches=sum(m.get("source") == "seed-from-raw" for m in dataset.matches),
                                          distinct_collection_timestamps=len({m["collected_at"] for m in dataset.matches}),
                                          warning="Backfilled or delayed collection can reorder play history; collection-time changes are not verified deployment times."),
                surrogate_source_sha256=sha256(param_source.read_bytes()).hexdigest(),
                settings=dict(bootstrap=bootstrap, permutations=permutations, minimum=minimum,
                              grid_step=grid_step, contamination=contamination, seed=seed,
                              alpha=alpha, confidence=confidence, penalty_scale=penalty_scale,
                              max_segments=max_segments),
                interpretation=[
                    "Offline surrogate estimates, not recovered opponent code or tournament runtime profiles.",
                    "Timestamp ranges use collected_at, which need not be the actual game/update chronology.",
                    "Bot display names are identities in these files; renames and same-name replacements cannot be resolved.",
                    "Segmentation globally minimizes penalized discovery SSE, then rejects unsupported boundaries using held-out matches and Holm correction.",
                    "Change significance is conditional on exchangeable independent match units; changing opponents or game contexts can also cause changes.",
                    "Bootstrap intervals condition on selected boundaries, opportunity definitions and finite parameter grids; they exclude boundary-selection and model uncertainty.",
                    "Likelihood-support intervals are diagnostic profiles, not guaranteed-coverage confidence intervals.",
                    "Zero bootstrap variance may reflect grid resolution or rare data, not certainty; inspect identifiability and model residuals.",
                    "Adaptive selection frequency compares two surrogate modes; it is not proof or a posterior probability that the real bot adapts.",
                    "Missing parameters and significant model residuals require a richer model; no estimator guarantees all unknown logic is captured.",
                ], bots=results)


def lookup(report, bot, collected_at):
    """Find the fitted segment inside the observed timeline; never extrapolate."""
    segments = report["bots"][bot]["segments"]
    if not segments[0]["observed_from"] <= collected_at <= segments[-1]["observed_through"]:
        raise ValueError("Timestamp outside this bot's observed collection range")
    return next(s for s in segments if (s["boundary_from"] is None or s["boundary_from"] <= collected_at)
                and (s["boundary_to"] is None or collected_at < s["boundary_to"]))
