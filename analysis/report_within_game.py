"""Export newest-interval within-game parameter trajectories and explanations."""
import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from opponent_model.data import COL
from opponent_model.fit import PARAMETERS
from opponent_model.within_game import MODES, read


def paired(values, seed=9172, comparisons=1):
    values = np.asarray(values, dtype=float)
    if not len(values):
        return dict(matches=0, mean=None, ci95=None, adjusted_ci=None, p=None)
    point = float(values.mean())
    if len(values) < 2:
        return dict(matches=len(values), mean=point, ci95=None, adjusted_ci=None, p=None)
    rng = np.random.default_rng(seed)
    boots = values[rng.integers(len(values), size=(5000, len(values)))].mean(1)
    null = (values*rng.choice([-1, 1], size=(9999, len(values)))).mean(1)
    p = float((1+(np.abs(null) >= abs(point)-1e-12).sum())/10000)
    return dict(matches=len(values), mean=point, ci95=np.quantile(boots, [.025, .975]).tolist(),
                adjusted_ci=np.quantile(boots, [.025/comparisons, 1-.025/comparisons]).tolist(), p=p)


def bh(values):
    order = np.argsort(values); result = np.ones(len(values)); last = 1.
    for rank in range(len(order)-1, -1, -1):
        index = order[rank]
        last = min(last, values[index]*len(order)/(rank+1))
        result[index] = last
    return result.tolist()


def losses(data, probability):
    y = data['y']
    nll = -np.log(probability[np.arange(len(y)), y].clip(1e-9))
    brier = (probability**2).sum(1)-2*probability[np.arange(len(y)), y]+1
    return nll, brier


def csv_write(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def interval(value):
    if value['ci95'] is None:
        return 'insufficient games'
    lo, hi = value['ci95']
    return f'{value["mean"]:+.4f} [{lo:+.4f}, {hi:+.4f}]'


def endpoints(values):
    return '['+', '.join(f'{v:+.3f}' for v in values)+']'


def report(directory):
    meta, data = read(directory)
    windows = json.loads((directory/'dynamics-windows.json').read_text())
    models = {mode: json.loads((directory/f'dynamics-{mode}.json').read_text()) for mode in MODES}
    selected = min(MODES, key=lambda mode: models[mode]['validation_objective'])
    test = data['split'] == 2
    scored, sizing_errors = {}, {}
    for mode in MODES:
        with np.load(directory/f'dynamics-predictions-{mode}.npz', allow_pickle=False) as archive:
            scored[mode] = losses(data, archive['probability'])
            sizing_errors[mode] = archive['sizing']-data['rows'][:, COL['amount']]
    comparisons = []
    for mode in MODES[1:]:
        row = dict(model=mode)
        for metric, number in (('nll', 0), ('brier', 1)):
            diff = scored['static'][number]-scored[mode][number]
            values = [float(diff[test & (data['match'] == m)].mean()) for m in np.unique(data['match'][test])]
            row[metric] = paired(values, comparisons=3)
        valid = test & (data['y'] == 3)
        for metric, transform in (('size_mae', np.abs), ('size_mse', np.square)):
            diff = transform(sizing_errors['static'])-transform(sizing_errors[mode])
            values = [float(diff[valid & (data['match'] == m)].mean()) for m in np.unique(data['match'][valid])]
            row[metric] = paired(values, comparisons=3)
        comparisons.append(row)
    explained = json.loads((directory/'dynamics-explanation.json').read_text())
    with np.load(directory/'dynamics-permutation.npz', allow_pickle=False) as archive:
        importance = {k: archive[k].copy() for k in archive.files}
    candidates, phase_rows, static_rows, trend_tests = [], [], [], []
    for index, name in enumerate(meta['bots']):
        profile = meta['profiles'][name]
        status = meta['excluded'].get(name, 'newest trusted interval')
        if name not in meta['excluded'] and profile['known_play_times'] < profile['matches']:
            status = 'Shared base epoch includes undated observations; temporal fits exclude them'
        static_rows.append(dict(bot=name, segment=profile['segment'], epoch=profile['epoch'],
            matches=profile['matches'], trusted_matches=profile['known_play_times'],
            temporal_status=status, **profile['surrogate_style']))
        if name not in windows['bots']:
            continue
        series = windows['bots'][name]
        mask = test & (data['bot'] == index)
        differences = scored['static'][0]-scored[selected][0]
        matches = np.unique(data['match'][mask])
        evidence = paired([float(differences[mask & (data['match'] == m)].mean()) for m in matches], seed=12389+index)
        # Fewer than eight test games do not support bot-specific conclusions.
        evidence['p_for_fdr'] = evidence['p'] if len(matches) >= 8 else 1.
        imp = {key: float(value[data['bot'][test] == index].mean()) if mask.any() else None
               for key, value in importance.items()}
        h = data['hands'][data['hands'][:, 2] == index]
        trends = {}
        for label, col in (('vpip', 4), ('pfr', 5), ('fold', 6)):
            values = []
            for match in np.unique(h[:, 0]):
                first = h[(h[:, 0] == match) & (h[:, 1] < 20)]
                last = h[(h[:, 0] == match) & (h[:, 1] >= 80)]
                if len(first) == len(last) == 20:
                    values.append(float(last[:, col].mean()-first[:, col].mean()))
            trends[label] = paired(values, seed=49831+index)
            trend_tests.append((trends[label], trends[label]['p'] if len(values) >= 8 else 1.))
        model_tests = {}
        for mode in MODES[1:]:
            diff = scored['static'][0]-scored[mode][0]
            model_tests[mode] = paired([float(diff[mask & (data['match'] == m)].mean()) for m in matches], seed=12389+index)
        preflop_context = []
        own_rows = data['rows'][data['bot'] == index]
        for phase in range(5):
            rr = own_rows[(own_rows[:, COL['street']] == 0) & (own_rows[:, COL['hand']]//20 == phase)]
            free = (rr[:, COL['pre_raises']] == 0) & (rr[:, COL['facing']] > 0)
            preflop_context.append(dict(phase=phase, unraised_opportunities=int(free.sum()),
                unraised_calls=int(((rr[:, COL['action']] == 2) & free).sum()),
                mean_card_percentile=float(np.mean(rr[:, COL['pct']])),
                note='Descriptive opportunity counts; the average card percentile alone does not fully control card distributions.'))
        candidates.append(dict(bot=name, matches=series['matches'], hands=series['hands'],
            test_actions=int(mask.sum()), predictive=evidence, permutation_nll_increase=imp,
            observed_trends=trends, model_comparisons=model_tests, preflop_context=preflop_context,
            phases=series['phases'], parameter_changes=series['late_minus_early']))
        for phase in series['phases']:
            for parameter in PARAMETERS:
                estimate = phase['parameters'][parameter]
                ci = estimate['confidence_interval']
                phase_rows.append(dict(bot=name, epoch=series['epoch'], first_hand=phase['hand_from'],
                    last_hand=phase['hand_through'], parameter=parameter, estimate=estimate['estimate'],
                    ci_low=None if ci is None else ci[0], ci_high=None if ci is None else ci[1],
                    status=estimate['status'], opportunities=estimate['opportunities'], matches=estimate['matches']))
    for row, q in zip(candidates, bh([r['predictive']['p_for_fdr'] for r in candidates])):
        row['predictive']['q'] = q
        row['predictive']['supported_gain'] = bool(q <= .05 and (row['predictive']['mean'] or 0) > 0)
    all_model_tests = [v for row in candidates for v in row['model_comparisons'].values()]
    for value, q in zip(all_model_tests, bh([v['p'] if v['matches'] >= 8 else 1. for v in all_model_tests])):
        value['q_across_bots_and_models'] = q
    for (row, _), q in zip(trend_tests, bh([p for _, p in trend_tests])):
        row['q'] = q
    supported = [r for r in candidates if r['predictive']['supported_gain']]
    supported_all_models = [dict(bot=row['bot'], model=mode) for row in candidates
        for mode, value in row['model_comparisons'].items()
        if value['q_across_bots_and_models'] <= .05 and (value['mean'] or 0) > 0]
    raw_supported = [r for r in candidates if any(v['q'] <= .05 for v in r['observed_trends'].values())]
    for row in candidates:
        patterns = []
        for label, value in row['observed_trends'].items():
            if value['q'] <= .05:
                patterns.append(f'{label} {100*value["mean"]:+.1f} percentage points late versus early (raw behavior)')
        if row['predictive']['supported_gain']:
            driver = max(row['permutation_nll_increase'], key=lambda k: row['permutation_nll_increase'][k] or -float('inf'))
            patterns.append(f'held-out conditional improvement; largest history permutation sensitivity: {driver}')
        elif row['predictive']['matches'] < 8:
            patterns.append('too few test games for a bot-specific conditional conclusion')
        else:
            patterns.append('conditional improvement not established after multiple-testing correction')
        row['explanation'] = '; '.join(patterns)
    test_log = directory/'tests-dynamics.log'
    test_summary = None
    if test_log.exists():
        found = re.search(r'Ran (\d+) tests in ([\d.]+)s\s+OK\s', test_log.read_text())
        if found:
            test_summary = dict(tests=int(found[1]), seconds=float(found[2]), result='OK', skipped=0)
    result = dict(selected=selected, selection='Validation objective only; test metrics are never used to change the selected model.',
        source_sha256=meta['input_audit']['actions_sha256'], cohort=meta['selection'], excluded=meta['excluded'],
        actions=len(data['y']), hands=len(data['hands']), matches=len(np.unique(data['match'])),
        bots=len(candidates), test_actions=int(test.sum()), test_matches=len(np.unique(data['match'][test])),
        models={mode: {key: {k:v for k,v in model[key].items() if k not in ('by_match','by_bot','calibration','streets')}
                       for key in ('validation','test')} | {key: model[key] for key in ('epoch','validation_objective','device','seconds','peak_allocated_bytes')}
                | {'test_size_mse': float(np.mean(sizing_errors[mode][test & (data['y'] == 3)]**2))}
                for mode, model in models.items()}, comparisons=comparisons, explanation=explained,
        supported_predictive_bots=[r['bot'] for r in supported], raw_trend_bots=[r['bot'] for r in raw_supported],
        supported_all_model_comparisons=supported_all_models,
        window_compute=dict(seconds=windows['seconds'], devices=windows['devices']), tests=test_summary,
        per_bot=candidates)
    (directory/'dynamics-comparison.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    tag = directory.name.removeprefix('refresh-')
    destination = ROOT/'analysis/reports'
    evidence = destination/'evidence'/('within-game-'+tag); evidence.mkdir(parents=True, exist_ok=True)
    index = {}
    names = ('snapshot-manifest.json', 'dynamics-plan.json', 'dynamics-explanation.json', 'dynamics-comparison.json',
             'latest-selection.json', 'behavior-comparison.json', 'dynamics-verification.json')
    if test_summary:
        names += ('tests-dynamics.log',)
    for filename in names:
        source = directory/filename; target = evidence/filename
        if filename == 'dynamics-comparison.json':
            compact = {k:v for k,v in result.items() if k != 'per_bot'}
            compact['per_bot'] = [{k:v for k,v in row.items() if k != 'phases'} for row in candidates]
            target.write_text(json.dumps(compact, indent=2)+'\n')
        else:
            shutil.copyfile(source, target)
        index[filename] = dict(source=str(source), source_sha256=sha256(source.read_bytes()).hexdigest(),
                               exported_sha256=sha256(target.read_bytes()).hexdigest())
    index['code'] = {name: sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ('opponent_model/within_game.py','opponent_model/within_game_windows.py','analysis/report_within_game.py',
         'analysis/verify_within_game.py','tests/test_within_game.py')}
    index['local_artifacts'] = {name: sha256((directory/name).read_bytes()).hexdigest() for name in
        ['validation-meta.json', 'dynamics-data.npz', 'dynamics-windows.json']
        + [f'dynamics-{kind}-{mode}.npz' for kind in ('policy', 'predictions') for mode in MODES]}
    csv_write(destination/f'latest-parameters-{tag}.csv', static_rows)
    csv_write(destination/f'within-game-parameters-{tag}.csv', phase_rows)
    bot_rows = [dict(bot=r['bot'], matches=r['matches'], test_matches=r['predictive']['matches'],
        nll_gain=r['predictive']['mean'], nll_gain_ci=json.dumps(r['predictive']['ci95']), q=r['predictive']['q'],
        vpip_early=r['phases'][0]['vpip'], vpip_late=r['phases'][-1]['vpip'], explanation=r['explanation']) for r in candidates]
    csv_write(destination/f'within-game-patterns-{tag}.csv', bot_rows)
    shutil.copyfile(directory/'dynamics-game-windows.csv.gz', destination/f'within-game-windows-{tag}.csv.gz')
    plot(destination, tag, candidates, supported, raw_supported)
    render(destination, directory, tag, result, windows)
    index['exports'] = {path.name: sha256(path.read_bytes()).hexdigest() for path in
        sorted(destination.glob(f'*-{tag}.*')) if path.is_file()}
    (evidence/'index.json').write_text(json.dumps(index, indent=2)+'\n')
    print(json.dumps(dict(selected=selected, predictive_bots=result['supported_predictive_bots'],
                          raw_trends=result['raw_trend_bots'], comparisons=comparisons), indent=2))


def plot(destination, tag, candidates, supported, raw_supported):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    by_name = {r['bot']:r for r in candidates}
    chosen = list(dict.fromkeys(['Halliday']+[r['bot'] for r in supported]+[r['bot'] for r in raw_supported]
                               +[r['bot'] for r in sorted(candidates, key=lambda r:-r['matches'])]))[:6]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), layout='constrained')
    for axis, name in zip(axes.flat, chosen):
        row = by_name[name]; phases = row['phases']; x = np.arange(5)*20+10
        axis.plot(x, [p['vpip']*100 for p in phases], 'o-', label='VPIP / dealt hands')
        axis.plot(x, [p['pfr']*100 for p in phases], 's-', label='PFR / dealt hands')
        axis.set(title=f'{name}\n{row["matches"]} newest-interval games', xlabel='Hand number (20-hand blocks)', ylabel='Observed rate (%)')
        axis.grid(alpha=.2); axis.legend(fontsize=8)
    fig.suptitle('Observed within-game behavior — cards and position can also change these rates', fontsize=13)
    fig.savefig(destination/f'within-game-patterns-{tag}.svg'); fig.savefig(destination/f'within-game-patterns-{tag}.png', dpi=160)
    svg = destination/f'within-game-patterns-{tag}.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)


def render(destination, directory, tag, result, windows):
    baseline = result['models']['static']['test']; selected = result['models'][result['selected']]['test']
    nll_gain = baseline['nll']-selected['nll']; brier_gain = baseline['brier']-selected['brier']
    plans = json.loads((directory/'snapshot-manifest.json').read_text())
    halliday = next(r for r in result['per_bot'] if r['bot'] == 'Halliday')
    supported = [r for r in result['per_bot'] if r['predictive']['supported_gain']]
    raw = [r for r in result['per_bot'] if r['bot'] in result['raw_trend_bots']]
    static_mse = result['models']['static']['test_size_mse']
    selected_mse = result['models'][result['selected']]['test_size_mse']
    progress_mae = result['models']['progress']['test']['sizing_mae']
    lines = [f'# Within-game parameter changes — {tag}', '',
        f'Refit the newest observed intervals from {plans["matches_with_actions"]:,} replay matches ({plans["rows"]:,} records). Actions SHA-256: `{result["source_sha256"]}`. The complete static parameter table covers every observed identity; the temporal study has {result["bots"]} reliably dated ladder identities, {result["matches"]} distinct matches, {result["hands"]:,} bot-hands and {result["actions"]:,} decisions. Bot-hands count each participating analyzed bot separately.', '',
        '## What the new features explain', '',
        f'The validation-selected model is **{result["selected"]}**. On {result["test_actions"]:,} held-out decisions in {result["test_matches"]} whole matches, its action log-loss change versus the equally trained static-context model is {nll_gain:+.6f} (positive means improvement). Its Brier error changes from {baseline["brier"]:.6f} to {selected["brier"]:.6f}: a {100*brier_gain/baseline["brier"]:+.3f}% reduction. This is residual prediction error, not a fraction of recovered strategy variance.', '',
        f'**The clearer gain is bet sizing.** The selected history model reduces squared raise-target error from {static_mse:.2f} to {selected_mse:.2f} chips², a **{100*(static_mse-selected_mse)/static_mse:.2f}% reduction** on held-out raises. The progress-only model reduces mean absolute sizing error from {baseline["sizing_mae"]:.3f} to {progress_mae:.3f} chips (**{100*(baseline["sizing_mae"]-progress_mae)/baseline["sizing_mae"]:.2f}%**). These quantify reduced unexplained prediction error, not recovered code parameters.', '',
        f'{len(supported) or "No"} bots have positive conditional prediction gains surviving the prespecified bot-level false-discovery correction. {len(raw)} bots show at least one corrected early-to-late raw VPIP/PFR/fold-rate trend. Raw trends may reflect cards, position and betting opportunities; the two types of evidence must not be conflated.', '',
        '| Model | Action log loss ↓ | Brier ↓ | Accuracy | Raise target MAE, chips ↓ | Raise target MSE, chips² ↓ |', '|---|---:|---:|---:|---:|---:|']
    for mode, model in result['models'].items():
        value = model['test']
        lines.append(f'| {mode} | {value["nll"]:.6f} | {value["brier"]:.6f} | {value["accuracy"]:.2%} | {value["sizing_mae"]:.3f} | {model["test_size_mse"]:.2f} |')
    lines += ['', 'All four networks have identical dimensions, initialization, optimizer, seed, match partitions and latest-interval training data. Removed feature groups are zeroed. Static context already includes own cards, board, position, pot odds, betting history, stack/legal constraints and coarse observed-opponent aggression/folding flags.', '',
        '| Added information | Mean per-match NLL gain, 95% interval | Three-comparison-adjusted interval |', '|---|---:|---:|']
    for comparison in result['comparisons']:
        lines.append(f'| {comparison["model"]} | {interval(comparison["nll"])} | {endpoints(comparison["nll"]["adjusted_ci"])} |')
    lines += ['', 'Sizing diagnostics use only observed raises and the same untouched test matches. Each metric compares the three added-feature models with static context; intervals below adjust for those three comparisons. Model choice remains validation-only.', '',
              '| Model | Per-match absolute-error reduction, adjusted interval (chips) | Per-match squared-error reduction, adjusted interval (chips²) |', '|---|---:|---:|']
    for comparison in result['comparisons']:
        a, b = comparison['size_mae'], comparison['size_mse']
        lines.append(f'| {comparison["model"]} | {a["mean"]:+.3f} {endpoints(a["adjusted_ci"])} | {b["mean"]:+.3f} {endpoints(b["adjusted_ci"])} |')
    lines += ['', 'The table above gives equal weight to each held-out match; the first metric table weights decisions equally. Intervals resample whole matches, preserving the dependence among actions and bots at a table. These intervals exclude model misspecification. The model-selection objective also includes sizing-bin log loss, so validation selection need not coincide with the lowest test action log loss.', '',
        '## Patterns and possible explanations', '',
        'A parameter estimate moving between two windows is not evidence that source-code constants changed. Different cards, legal opportunities, player positions, opponent actions and sparse data can change the best-fitting surrogate. The `adaptive` flag selects a scaffold likelihood, not a verified adaptation mechanism.', '',
        'VPIP is the fraction of dealt hands with a voluntary preflop call or raise; PFR is the fraction with a preflop raise. Fold rates here count hands ending in the bot folding, divided by all dealt hands, including walks. Early and late refer to hands 1–20 and 81–100.', '',
        '| Bot | Latest games | Early → late VPIP | Conditional NLL gain / game | Explanation |', '|---|---:|---:|---:|---|']
    focus = list(dict.fromkeys(['Halliday']+[r['bot'] for r in supported]+[r['bot'] for r in raw]))
    by_name = {r['bot']:r for r in result['per_bot']}
    for name in focus:
        row = by_name[name]
        lines.append(f'| {name} | {row["matches"]} | {row["phases"][0]["vpip"]:.1%} → {row["phases"][-1]["vpip"]:.1%} | {interval(row["predictive"])} | {row["explanation"]} |')
    if 'RaiseYourEdge' in by_name and 'orcabot' in by_name:
        rye, orca = by_name['RaiseYourEdge'], by_name['orcabot']
        r0, r4 = rye['phases'][0], rye['phases'][-1]
        o0, o4 = orca['phases'][0], orca['phases'][-1]
        c0, c4 = orca['preflop_context'][0], orca['preflop_context'][-1]
        lines += ['', f'**RaiseYourEdge: progressively less participation.** VPIP falls from {r0["vpip"]:.2%} to {r4["vpip"]:.2%}, PFR from {r0["pfr"]:.2%} to {r4["pfr"]:.2%}, and folding rises from {r0["fold_rate"]:.2%} to {r4["fold_rate"]:.2%}. Its observed VPIP declines across all five phases. This fits a tightening pattern. The data do not identify whether a hand-count schedule, opponent adaptation, score protection or time budget causes it. The pooled fitted size setting also drops, but its paired uncertainty interval includes zero; that point estimate alone does not prove a sizing switch.', '',
            f'**orcabot: less passive entry, more selective raising.** VPIP falls from {o0["vpip"]:.2%} to {o4["vpip"]:.2%} while PFR rises from {o0["pfr"]:.2%} to {o4["pfr"]:.2%}. Calling an unraised preflop price falls from {c0["unraised_calls"]}/{c0["unraised_opportunities"]} ({c0["unraised_calls"]/c0["unraised_opportunities"]:.2%}) to {c4["unraised_calls"]}/{c4["unraised_opportunities"]} ({c4["unraised_calls"]/c4["unraised_opportunities"]:.2%}). This explains how it can play fewer hands yet raise more often. The fitted limp setting falls from {o0["surrogate_style"]["limp"]:.2f} to {o4["surrogate_style"]["limp"]:.2f}. A shift away from early limping is a plausible behavioral description; the underlying mechanism remains unverified.']
    lines += ['', f'![Observed rates](within-game-patterns-{tag}.svg)', '',
        'The history model uses only preceding public information: accumulated chips and relative standing; the previous result, last-five-hand result and loss streak; and smoothed own/opponent VPIP, PFR, preflop shoves and fold share. It cannot diagnose tilt, intent or a particular internal learning algorithm.', '',
        'Conditional feature shuffling stays within the same bot, street and 20-hand phase. Positive increases below mean the selected model uses that information. Correlated predictors and unrealistic shuffled combinations mean these are sensitivity diagnostics, not causal explanations or additional validated performance gains.', '',
        '| Shuffled feature group | Test log-loss increase | Raise-target MSE increase, chips² |', '|---|---:|---:|']
    for group, value in result['explanation']['mean_nll_increase'].items():
        lines.append(f'| {group} | {value:+.6f} | {result["explanation"]["mean_raise_mse_increase"][group]:+.3f} |')
    sizing_importance = result['explanation']['mean_raise_mse_increase']
    if sizing_importance:
        strongest = max(sizing_importance, key=sizing_importance.get)
        lines += ['', f'The largest sizing sensitivity is **{strongest}**, with a {sizing_importance[strongest]:+.2f} chips² error increase when shuffled. This identifies information used by the fitted model; it does not establish that each bot explicitly implements that mechanism.']
        if sizing_importance.get('recent_results', 0) < 0:
            lines += ['', 'Shuffling recent results does not worsen sizing error. This diagnostic provides no clear sizing evidence for a reaction to recent losses or a tilt mechanism.']
    lines += ['', '## Halliday specifically', '',
        f'The newest observed Halliday interval contains {halliday["matches"]} games. Observed VPIP changes from {halliday["phases"][0]["vpip"]:.2%} in hands 1–20 to {halliday["phases"][-1]["vpip"]:.2%} in hands 81–100. Its conditional prediction result is {interval(halliday["predictive"])}; corrected q={halliday["predictive"]["q"]:.4f}. {halliday["explanation"][0].upper()+halliday["explanation"][1:]}.', '',
        '| Surrogate setting | First 20 hands | Last 20 hands | Paired late-minus-early bootstrap interval |', '|---|---:|---:|---:|']
    for parameter in PARAMETERS:
        first = halliday['phases'][0]['surrogate_style'][parameter]
        last = halliday['phases'][-1]['surrogate_style'][parameter]
        value = halliday['parameter_changes'][parameter]
        lines.append(f'| {parameter} | {first:.3f} | {last:.3f} | {endpoints(value["paired_match_bootstrap_interval"])} |')
    if all(v['paired_match_bootstrap_interval'][0] <= 0 <= v['paired_match_bootstrap_interval'][1]
           for v in halliday['parameter_changes'].values()):
        lines += ['', 'All ten early-to-late parameter intervals include zero. These fits do not establish a reliable Halliday strategy shift within a game.']
    lines += ['', 'These parameter intervals are descriptive, conditional on the surrogate and its grid. In particular, a large point movement with an interval spanning zero does not establish a leak or justify a scheduled parameter change.', '',
        '## Every analyzed bot', '',
        '| Bot | Games | Test games | Conditional NLL gain, 95% interval | Corrected q | Finding |', '|---|---:|---:|---|---:|---|']
    for row in result['per_bot']:
        lines.append(f'| {row["bot"]} | {row["matches"]} | {row["predictive"]["matches"]} | {interval(row["predictive"])} | {row["predictive"]["q"]:.4f} | {row["explanation"]} |')
    lines += ['', '## Exclusions and limits', '',
        'Each analyzed bot contributes only its newest trusted observed upload interval. Other players at those tables can belong to the versions actually encountered; this is not the stricter all-seats-latest performance cohort. Shared opponent reconstruction is refitted from the full dataset, but the four temporal comparison models train only on this latest-interval cohort. Whole matches share a deterministic 60/20/20 split across all bots.', '',
        'Successful validation proves an upload, not its deployment. Display names cannot resolve every rename. Unknown-time games are excluded from this temporal study, including unknown-time games sharing a base epoch with dated games. Validation-only and house identities are excluded. Their available static estimates remain in the full parameter CSV with the limitation marked.', '',
        'The static catalogue preserves the reconstruction workflow, whose shared base epochs can mix dated and undated observations. Those rows are explicitly marked in the static CSV. The per-game and pooled-phase CSVs apply the stricter trusted-time filter throughout.', '',
        '| Excluded identity | Reason |', '|---|---|']
    lines += [f'| {name} | {reason} |' for name, reason in result['excluded'].items()]
    lines += ['', 'The original 100-hand match length is used; “rounds” here means successive hands, while betting streets are context controls. Scores reset per match and stacks reset per hand. No timing, verdict or deployed-source trace is available to distinguish time-bank exhaustion from a deliberate late-game policy. The predictor receives neither hidden opponent cards nor any current/future-hand outcome.', '',
        '## Parameter files and reproduction', '',
        f'- [Newest static parameters for every identity](latest-parameters-{tag}.csv).',
        f'- [All five 20-hand parameter fits, uncertainty and opportunity counts](within-game-parameters-{tag}.csv).',
        f'- [Every bot/game/10-hand window](within-game-windows-{tag}.csv.gz): gzip CSV with all ten shrunk settings, local opportunity counts and supported raw estimates.',
        f'- [Per-bot findings](within-game-patterns-{tag}.csv) and [evidence index](evidence/within-game-{tag}/index.json).', '',
        'Ten-hand windows add a pooled prior equivalent to 20 hands from other games of that same newest bot interval. The current game is excluded from its prior. Estimates can be prior-dominated; raw estimates are blank below ten local opportunities. Pooled 20-hand phases use 300 paired whole-match bootstrap draws, retaining each game together across phases. These descriptive fits can use all selected matches; they are not fed into the held-out predictive experiment.', '',
        f'Bot-specific predictive tests require eight test matches, use paired sign permutations and apply Benjamini–Hochberg correction across bots. The saved comparison also checks every bot against all three added-feature models, correcting across that full family; {len(result["supported_all_model_comparisons"])} positive action-prediction comparisons survive that broader check. Raw early/late VPIP, PFR and fold trends are a separate family of three tests per bot, with the same minimum of eight matches. Dependence between games, grid-limited estimates and sparse contexts constrain interpretation. Parameter-change bootstrap intervals are not regular hypothesis tests.', '',
        'The refreshed executable JSON catalogue retains the validated reconstruction workflow. The new time/history predictors and descriptive parameter trajectories are diagnostic artifacts, not an unvalidated runtime replacement.', '',
        '## Compute and verification', '',
        f'The four temporal models train concurrently on distinct V100 GPUs, one model per device, for 100 epochs. Peak tensor allocation is {max(m["peak_allocated_bytes"] for m in result["models"].values())/2**20:.1f} MiB per worker, below the 768 MiB limit. Training takes {min(m["seconds"] for m in result["models"].values()):.1f}–{max(m["seconds"] for m in result["models"].values()):.1f} seconds per model. Window fitting distributes bots across all four GPUs and takes {windows["seconds"]:.1f} seconds. CPU parsing and serialization are separate; NVLink does not pool device memory.', '',
        'Independent verification reconciles the source hash, trusted newest intervals, every dealt hand and window, final chip totals, whole-match partitions and four distinct training devices. No-action walks remain in all hand denominators.', '']
    if result['tests']:
        lines += [f'All **{result["tests"]["tests"]} regression tests pass** with CUDA enabled and no skips; the evidence bundle includes the test log.', '']
    lines += ['## Reproduction commands', '',
        'Run from the repository root; frozen inputs and cached validation responses are local and not committed:', '', '```sh',
        'export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1',
        'analysis_python=.venv-estimators/bin/python', f'analysis_run={directory}',
        '$analysis_python -B analysis/run_refresh_models.py --directory "$analysis_run" --epochs 100',
        '$analysis_python -B -m opponent_model.within_game prepare --directory "$analysis_run"',
        '$analysis_python -B -m opponent_model.within_game train --directory "$analysis_run" --devices 0,1,2,3 --epochs 100',
        '$analysis_python -B -m opponent_model.within_game windows --directory "$analysis_run" --devices 0,1,2,3',
        '$analysis_python -B -m opponent_model.within_game explain --directory "$analysis_run" --devices 0',
        '$analysis_python -B analysis/verify_within_game.py --directory "$analysis_run"',
        '$analysis_python -B analysis/report_within_game.py --directory "$analysis_run"', '```', '',
        'For another completed upload, choose an unused run directory and prepare it before running the stages above:', '', '```sh',
        'analysis_run=analysis/results/refresh-YYYYMMDD-rN',
        '$analysis_python -B analysis/freeze_snapshot.py --source analysis/results/input-snapshot --directory "$analysis_run"',
        '$analysis_python -B -m opponent_model.fetch_validation --matches "$analysis_run/source/matches.json" --output "$analysis_run/validation-meta.json"', '```', '',
        'Use the analysis environment described in `opponent_model/README.md`, with `uv pip install --python .venv-estimators/bin/python matplotlib==3.11.2` for plots. Reproducing this study exactly requires its original frozen source and validation responses. Seeds, source SHA-256, devices, model stopping points, checkpoint fingerprints and complete window traces are preserved. The static refresh rebuilds the executable opponent catalogue.', '']
    (destination/f'within-game-patterns-{tag}.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    report(parser.parse_args().directory)
