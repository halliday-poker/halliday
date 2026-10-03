"""Readable companion to the complete machine-readable JSON report."""

from datetime import datetime, timezone
import re

from .fit import PARAMETERS


def markdown(report):
    if report.get('predictive_comparison'):
        return behavior_markdown(report)
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


def behavior_markdown(report):
    """Separate candidate upload intervals from statistically confirmed cuts."""
    comparison=report['predictive_comparison']
    audit=comparison['validation_audit']
    test=comparison['baseline']['test']
    lines=['# Opponent refresh and predictive validation','',
           f"Generated at {report['generated_at_utc']}.",'',
           f"Source SHA-256: `{report['input_audit']['actions_sha256']}`. "
           f"{report['input_audit']['bots']} observed identities, {report['input_audit']['matches_with_actions']} complete matches, "
           f"{report['input_audit']['actions']:,} actions. Only identities with collected action evidence are recreated.",'',
           '## Validation matches and behavior intervals','',
           f"The replay-backed dataset contains {audit['validation_matches']} validation matches: {audit.get('passed',0)} passed and {audit.get('failed_or_unknown',0)} failed or unknown. "
           f"{audit.get('trusted_play_time',0)} have trusted server play timestamps; {audit.get('not_house_call_pair',0)} are not team-versus-`house:call` pairs. "
           'The [official FAQ](https://docs.poker.monashcoding.com/faq/) explains that every upload is validated, but a passing upload must be selected as main (the first passing upload becomes main automatically). '
           'Thus validation marks an upload, not a guaranteed deployment. Failed checks and uncertain timestamps are excluded from candidate boundaries.','',
           f"The selected predictive interval mode is `{comparison['selected']}`. Candidate modes are compared on whole held-out matches, including randomized boundaries with matched per-bot counts. "
           'This is evidence that upload timing helps distinguish behavior, not proof that every event changed deployed code. Unknown-time games remain in a base interval. '
           'Latest-segment selection prioritizes intervals containing trusted play timestamps. Team validation hands are excluded from fits wherever ladder evidence exists.','',
           '## Predictive comparison','',
           comparison['split_policy']+'. Every action and every bot from the same game stays together. '
           'The original ten-parameter estimator, including its change detection, was refitted using training matches only. '
           'Four CUDA workers then trained the richer alternatives concurrently. Stopping and model choice used validation action log loss plus 0.2 times sizing-bin log loss. '
           f"The final test set contains {comparison['paired_comparisons'][0]['matches']} ladder games and {test['actions']:,} decisions and was excluded from selection.",'',
           '| Model | Test action log loss ↓ | Brier score ↓ | Action accuracy ↑ | Raise-size MAE, chips ↓ | Calibration error ↓ |',
           '|---|---:|---:|---:|---:|---:|']
    models={'Original ParamBot estimates':comparison['baseline']['test']}
    models.update({{'none':'Richer context, no time intervals','upload':'Richer context, successful-upload intervals','placebo':'Richer context, randomized intervals','change':'Richer context, detected-change intervals'}[key]:value['test'] for key,value in comparison['models'].items()})
    for name,m in models.items():
        lines.append(f"| {name} | {m['nll']:.4f} | {m['brier']:.4f} | {m['accuracy']:.2%} | {m['sizing_mae']:.2f} | {m['ece']:.4f} |")
    lines+=['','Lower log loss/Brier scores indicate better probability forecasts. Calibration error is aggregate confidence-bin error; it can hide subgroup errors. '
            'The individual training result JSONs retain per-bot, per-street and per-match diagnostics. Size MAE compares a predicted central target with the recorded raise target; it is not a full distributional size score. '
            'The models use legal-action masks. Their probability forecasts are not claims to solve poker optimally.','',
            '| Reference → candidate | Mean whole-match log-loss improvement | 95% paired bootstrap interval | Interval adjusted for seven comparisons |',
            '|---|---:|---|---|']
    for x in comparison['paired_comparisons']:
        ci=x['bootstrap_95_interval'];adjusted=x['bonferroni_7_comparisons_interval']
        lines.append(f"| {x['reference']} → {x['candidate']} | {x['mean_match_nll_gain']:.4f} | [{ci[0]:.4f}, {ci[1]:.4f}] | [{adjusted[0]:.4f}, {adjusted[1]:.4f}] |")
    lines+=['','Bootstrap resampling preserves complete matches and all players at each table. Games can still share opponents or versions, so these intervals do not cover all dependence or model uncertainty. '
            'The random split measures held-out games from observed versions; it does not establish reliability on unseen future versions. '
            f"Selected mode: **{comparison['selected']}**, epoch {comparison['selected_epoch']}. Its final replica was refitted on all available eligible data using that stopping epoch. "
            'Refit training scores are not substituted for held-out metrics.','',
            '## New estimates and executable behavior','',
            'The richer model conditions on own cards, board texture, position, live players, legal raises, call price, stack commitment, previous raises, and public opponent-action counters. '
            'It predicts action probabilities and a mixture over ten legal raise targets, including all-in. Runtime sampling uses a private per-game RNG. '
            'It sees no hidden opponent cards, future actions or outcomes. NumPy inference was checked against the PyTorch training network; the tournament candidate itself does not contain this learned replica model.','',
            'Each interval retains the ten scaffold estimates and whole-match bootstrap uncertainty. Additional conditional rates cover preflop shoves, preflop raise calls, folds facing large commitments, multiway postflop folds, river calls, checked-to bets and reraises. '
            'Executable scaffold styles shrink toward the full-bot estimate below six matches. Fewer than two ladder games in the latest interval, or only validation evidence, produces an explicit scaffold fallback.','',
            '## Latest interval per observed identity','',
            'VPIP/PFR/3-bet below are scaffold settings, not raw action percentages. Shove and river-call columns are measured opportunity-conditioned frequencies; a dash means no observations. '
            'Full confidence intervals, opportunity counts and sparse-data statuses are in the JSON and generated profiles manifest.','',
            '| Identity | Intervals | Latest matches | Policy | VPIP / PFR / 3-bet | Preflop shove rate | River call rate |',
            '|---|---:|---:|---|---|---:|---:|']
    def rate(value):return '—' if value is None else f'{value:.1%}'
    for name,result in sorted(report['bots'].items()):
        s=max(result['segments'],key=lambda s:tuple(s['selection_key']))
        style=s['surrogate_style'];context=s['context_rates']
        lines.append(f"| {name.replace('|','/')} | {len(result['segments'])} | {s['matches']} | {s['behavior']['status']} | "
                     f"{style['vpip']:.2f} / {style['pfr']:.2f} / {style['threebet']:.2f} | "
                     f"{rate(context['preflop_shove_when_raise_legal']['rate'])} | {rate(context['river_call_when_facing_bet']['rate'])} |")
    lines+=['','## Scope and next checks','',
            'These are reconstructed opponents, not their source code. Display names can be renamed teams or different code versions. '
            'Equal weighting of recorded names is not an authenticated final entrant list. '
            'The main replay field has eight seats, whereas tournament tables are commonly smaller; both contexts must be tested. '
            'Predictive improvements do not prove that closed-loop simulations reproduce real game winnings. '
            'Evaluate simulated behavior, winnings and strategy changes separately; predictive scores alone do not validate those outcomes.','']
    return '\n'.join(lines)
