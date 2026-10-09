"""Readable companion to the complete machine-readable JSON report."""

from datetime import datetime, timezone
import re

from .fit import PARAMETERS


def markdown(report):
    escape = lambda text: re.sub(r"([\\`*_{}\[\]<>()#+.!|])", r"\\\1", str(text))
    date = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    number = lambda value: "unavailable" if value is None else f"{value:.4g}"
    audit, settings = report["input_audit"], report["settings"]
    lines = ["# Opponent parameter estimates", "",
             f"{audit['bots']} bots; {audit['matches_with_actions']} matches; {audit['actions']:,} actions.", "",
             f"Computed on {escape(report['compute']['gpu'] or report['compute']['device'])}, "
             f"{settings['bootstrap']} whole-match bootstrap replicates and {settings['permutations']} held-out permutations.", "",
             "These are fitted sparring-model settings. Collection-time changes are evidence of different behaviour, "
             "not confirmed deployments. Confidence intervals condition on the selected segments and model. "
             "Inspect identifiability and fit residuals before using a style.", "",
             "## Confirmed boundaries", "",
             "| Bot | Proposed boundary | Discovery gap | Holm-adjusted p |",
             "|---|---|---|---:|"]
    changes = 0
    for bot, result in report["bots"].items():
        for p in result["segmentation"]["proposals"]:
            if p["accepted"]:
                changes += 1
                lines.append(f"| {escape(bot)} | {date(p['cut_at'])} | "
                             f"{date(p['last_discovery_before'])} to {date(p['first_discovery_after'])} | "
                             f"{p['adjusted_p_value']:.4g} |")
    if not changes:
        lines.append("| No boundaries confirmed | | | |")
    lines += ["", "The discovery gap is not a confidence interval for the update time. "
              "Unsupported proposed cuts are retained with their test evidence in the JSON.", ""]
    for bot, result in report["bots"].items():
        lines += [f"## {escape(bot)}", ""]
        for segment in result["segments"]:
            lines += [f"### Segment {segment['segment']}", "",
                      f"{date(segment['observed_from'])} through {date(segment['observed_through'])}; "
                      f"{segment['matches']} matches.", "",
                      "| Parameter | Estimate | 95% bootstrap interval | Estimator variance | Status |",
                      "|---|---:|---|---:|---|"]
            # Use the actual requested confidence level, not a hard-coded label.
            lines[-2] = lines[-2].replace("95%", f"{100*settings['confidence']:g}%")
            for name in PARAMETERS:
                parameter = segment["parameters"][name]
                ci = parameter["confidence_interval"]
                interval = "unavailable" if ci is None else f"[{number(ci[0])}, {number(ci[1])}]"
                lines.append(f"| {name} | {number(parameter['estimate'])} | {interval} | "
                             f"{number(parameter['variance'])} | {parameter['status']} |")
            residuals = [f"{key}: {item['incompatible_action_fraction']:.1%} incompatible actions"
                         for key, item in segment["model_diagnostics"].items() if "incompatible_action_fraction" in item]
            lines += ["", "Model diagnostics: " + "; ".join(residuals) + ".", ""]
    lines += ["## Reading uncertainty", "",
              "The JSON also contains standard errors, profile support, flat likelihood ranges, covariance, "
              "between-match variance, empirical rates, sizing diagnostics and match IDs. Zero grid-bootstrap "
              "variance is not certainty. Parameter p-values are null where no regular test is justified; "
              "change-point p-values use held-out match permutations and family-wide Holm correction.", ""]
    return "\n".join(lines)
