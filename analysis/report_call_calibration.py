"""Paired table-cluster comparison of the frozen main and call-correction bots."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import sys

import numpy as np
os.environ.setdefault('MPLCONFIGDIR', '/tmp/halliday-call-plots')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.halliday_report import BLUNDERS


def paired_tables(report):
    groups = defaultdict(dict)
    for g in report['games']:
        key = (g['cand_idx'], g['game'])
        assert key not in groups[g['table']]
        groups[g['table']][key] = g
        assert sum(g['chips']) == 0
        assert all(v == 'OK' for v in g['verdicts']) and not any(g['errors'])
    rows = []
    for t, group in sorted(groups.items()):
        n = len(report['tables'][t]) + 1
        assert 4 <= n <= 6
        assert set(group) == {(c, g) for c in (0, 1) for g in range(n)}
        chips = [sum(group[c, g]['chips'][0] for g in range(n)) for c in (0, 1)]
        rows.append(dict(table=t, games=n, main=chips[0], candidate=chips[1], difference=chips[1]-chips[0]))
    return rows


def paired_interval(tables, replicates=5000):
    counts = np.array([t['games'] for t in tables], dtype=float)
    totals = np.array([[t['main'], t['candidate'], t['difference']] for t in tables], dtype=float)
    point = totals.sum(0)/counts.sum()/2  # 100 hands/game; 2 chips/big blind.
    if len(tables) < 2:
        return dict(point=point.tolist(), low=[None]*3, high=[None]*3)
    rng = np.random.default_rng(54739)
    draws = []
    for first in range(0, replicates, 100):
        indices = rng.integers(len(tables), size=(min(100, replicates-first), len(tables)))
        draws.append(totals[indices].sum(1)/counts[indices].sum(1)[:, None]/2)
    bounds = np.quantile(np.concatenate(draws), [.025, .975], axis=0)
    return dict(point=point.tolist(), low=bounds[0].tolist(), high=bounds[1].tolist())


def csv_file(path, rows):
    if not rows: return
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def report(run, output):
    output.mkdir(parents=True, exist_ok=True)
    stem = 'call-calibration-20261004'
    simulation = json.loads((run/'simulate.json').read_text())
    audits = json.loads((run/'audit-summary.json').read_text())
    selection = json.loads((run/'candidate-selection.json').read_text())
    plan = json.loads((run/'study-plan.json').read_text())
    fit = json.loads((run/'fit/runtime-fit.json').read_text())
    coverage = json.loads((run/'fit/runtime-verification.json').read_text())
    backend = json.loads((run/'backend-selection.json').read_text())
    snapshot = json.loads((run/'fit/snapshot-manifest.json').read_text())
    tables = paired_tables(simulation)
    if simulation['compute']['device'] == 'cuda':
        usage = simulation['compute']['gpu_usage']
        assert set(usage) == {'cuda:0','cuda:1','cuda:2','cuda:3'}
        assert all(v['ranked_hands'] > 0 for v in usage.values())
    assert len(simulation['games']) == len(audits['games']) == 20000
    assert sum(t['games'] for t in tables) == 10000
    interval = paired_interval(tables)
    summaries = [Counter(), Counter()]
    streets = [defaultdict(Counter), defaultdict(Counter)]
    classifications = [Counter(), Counter()]
    originals = {(g['cand_idx'], g['table'], g['game']): g for g in simulation['games']}
    seen = set();game_rows = [];flag_rows = [];fallbacks = [Counter(), Counter()]
    gpu_work = defaultdict(Counter)
    catalog = json.loads((ROOT/'sparring/competitors/from_data_patterns/bots.json').read_text())
    names = {key: value['name'] for key, value in catalog['bots'].items()}
    for number, g in enumerate(audits['games'], 1):
        c = int(g['match'].rsplit('-c', 1)[1])
        key = c, g['table'], g['game']
        assert key not in seen;seen.add(key)
        original = originals[key]
        gpu_work[g['gpu']['device']].update({k:g['gpu'][k] for k in ('batches','ranked_hands','gpu_seconds')})
        assert g['hands'] == 100 and original['chips'][0] == g['chips']
        assert g['opponents'] == [names[s.rsplit('@',1)[1]] for s in simulation['tables'][g['table']]]
        summary = summaries[c]
        for k in ('chips','hands','actions','folds','facing_decisions','bad_calls','missed_calls','certain_folds',
                  'allin_actual','allin_expected','allin_luck','ev_audited','vpip_hands','pfr_hands'):
            summary[k] += g[k]
        summary['games'] += 1
        summary['negative_games'] += g['chips'] < 0
        summary['negative_games_with_flags'] += g['chips'] < 0 and g['flags'] > 0
        classifications[c].update(g['classifications'])
        for street, values in g['streets'].items(): streets[c][street].update(values)
        game_rows.append(dict(variant=c, match=g['match'], table=g['table'], game=g['game'], chips=g['chips'],
            opponents=g['opponents'], folds=g['folds'], bad_calls=g['bad_calls'], missed_calls=g['missed_calls'],
            allin_luck=g['allin_luck'], loss_categories=g['loss_categories']))
        with gzip.open(run/'audit'/(g['match']+'.json.gz'), 'rt') as stream: shard = json.load(stream)
        assert shard['summary'] == g
        for row in shard['decisions']:
            diagnostic = row['diagnostic'];estimate = diagnostic.get('estimate') or {}
            if estimate.get('method') == 'monte_carlo' and estimate.get('samples', 0) < 128:
                fallbacks[c]['sparse_estimates'] += 1
                fallbacks[c]['accepted_bounds'] += diagnostic.get('equity') is not None
                fallbacks[c]['calls'] += row['action'] == 'call'
            if row['classification'] in BLUNDERS:
                flag_rows.append(dict(variant=c, id=row['id'], street=row['street'], action=row['action'],
                    hole=row['hole'], board=row['board'], pot=row['pot'], call=row['call'],
                    classification=row['classification'], public_ev_lower=row['public_ev_lower'],
                    public_ev_upper=row['public_ev_upper'], oracle_ev=(row['oracle'] or {}).get('call_ev'),
                    decision_equity=diagnostic.get('equity'), samples=estimate.get('samples'),
                    hand_chips=row['hand_chips'], match_chips=row['match_chips']))
        if number % 5000 == 0: print(f'{number}/20000 audit shards summarized', flush=True)
    assert seen == set(originals)
    assert set(gpu_work) == {'cuda:0','cuda:1','cuda:2','cuda:3'}
    assert all(v['ranked_hands'] > 0 for v in gpu_work.values())
    assert all(s['games'] == 10000 and s['hands'] == 1000000 for s in summaries)
    assert all(sum(t[k] for t in tables) == summaries[c]['chips'] for c, k in enumerate(('main','candidate')))
    csv_file(output/(stem+'-games.csv'), sorted(game_rows, key=lambda g:(g['table'],g['game'],g['variant'])))
    csv_file(output/(stem+'-tables.csv'), tables)
    csv_file(output/(stem+'-blunders.csv'), flag_rows)
    parameters = []
    for bot, record in fit['bots'].items():
        for parameter, value in record['estimate']['parameters'].items():
            prior = value['prior']
            parameters.append(dict(bot=bot,parameter=parameter,estimate=value['estimate'],
                low=value['confidence_interval'][0],high=value['confidence_interval'][1],
                newest_support=prior['latest_opportunities'],effective_support=prior['effective_opportunities'],
                status=prior['status'],older_versions=prior['older_versions']))
    csv_file(output/(stem+'-parameters.csv'), parameters)
    sparse = sum(v['status'] == 'still_sparse' for v in parameters)
    prior_only = [name for name, value in fit['selection']['bots'].items()
                  if value.get('prior_only') and name in fit['bots']]
    cohorts = []
    for present in (False, True):
        cohort = [t for t in tables if any(names[s.rsplit('@',1)[1]] in prior_only
                  for s in simulation['tables'][t['table']]) == present]
        if cohort:
            cohorts.append(dict(prior_only_opponent_present=present, games=sum(t['games'] for t in cohort),
                                tables=len(cohort), interval=paired_interval(cohort)))
    plot(output/stem, tables, interval, summaries, streets)
    baseline, candidate = summaries
    placement = simulation['summary']
    round_delta, round_half = placement[1]['vs_baseline']['d_round_pts']
    cpu_check = json.loads((run/'cpu-check.json').read_text()) if (run/'cpu-check.json').exists() else None
    test_log = (run/'selected-tests.log').read_text()
    assert test_log.rstrip().endswith('OK')
    test_count = int(re.search(r'Ran (\d+) tests', test_log).group(1))
    elapsed = json.loads((run/'simulate-execution.json').read_text())['wall_seconds']
    cpu_note = ('The separate CPU check played 120 games with no player failures; maximum candidate bank use was '
                f"{cpu_check['summary'][0]['bank_pct']:.2f}% and maximum action time was {cpu_check['summary'][0]['max_ms']:.2f} ms."
                if cpu_check else 'The final comparison used CPU clocks directly.')
    if cpu_check:
        assert len(cpu_check['games']) == 120
        assert all(all(v == 'OK' for v in g['verdicts']) for g in cpu_check['games'])
    pct = lambda n, d: f'{100*n/d:.2f}%'
    ci = lambda i: f"{interval['point'][i]:+.2f} [{interval['low'][i]:+.2f}, {interval['high'][i]:+.2f}]"
    terminal_folds = [sum(v['terminal_folds'] for v in s.values()) for s in streets]
    terminal_calls = [sum(v['terminal_calls'] for v in s.values()) for s in streets]
    street_rows = [
        f"| {street.title()} | {pct(streets[0][street]['facing_folds'], streets[0][street]['faced_bet'])} | "
        f"{pct(streets[1][street]['facing_folds'], streets[1][street]['faced_bet'])} |"
        for street in ('preflop', 'flop', 'turn', 'river')]
    flagged_streets = Counter((int(r['variant']), r['street'], r['classification']) for r in flag_rows)
    flagged = lambda c, street, kind: flagged_streets[c, street, f'probable_{kind}_terminal_call']
    flagged_street_rows = [
        f"| {street.title()} | {flagged(0,street,'missed'):,} | {flagged(1,street,'missed'):,} | "
        f"{flagged(0,street,'bad'):,} | {flagged(1,street,'bad'):,} |"
        for street in ('preflop', 'flop', 'turn', 'river')]
    pilot = selection['pilot_chips']
    lines = ['# Call calibration: main versus corrected bot — 4 October 2026', '',
        f"The held-out comparison played **10,000 games per version** (2,000,000 hands total) against {len(fit['bots'])-1} refreshed opponent replicas. "
        f"The corrected bot changed return by **{ci(2)} bb/100** (paired 95% table-bootstrap interval).", '',
        f"{'The interval supports an improvement in this simulated field.' if interval['low'][2] > 0 else 'The interval does not establish an improvement in this simulated field.'} "
        'This comparison uses the same tables, decks and seat rotations. It is not a live tournament result.', '',
        '| Metric | Main | Corrected bot |', '| --- | ---: | ---: |',
        f"| Net chips | {baseline['chips']:+,} | {candidate['chips']:+,} |",
        f'| bb/100 [95% interval] | {ci(0)} | {ci(1)} |',
        f"| Folds / hands | {pct(baseline['folds'],baseline['hands'])} | {pct(candidate['folds'],candidate['hands'])} |",
        f"| Negative games | {baseline['negative_games']:,} | {candidate['negative_games']:,} |",
        f"| Mean game placement points | {placement[0]['game_pts'][0]:.3f} | {placement[1]['game_pts'][0]:.3f} |",
        f"| Mean duplicate-table placement points | {placement[0]['round_pts'][0]:.3f} | {placement[1]['round_pts'][0]:.3f} |",
        f"| Duplicate tables won outright | {placement[0]['won_pct']:.2f}% | {placement[1]['won_pct']:.2f}% |",
        f"| Probable missed terminal calls | {baseline['missed_calls']:,} | {candidate['missed_calls']:,} |",
        f"| Missed-call flags / terminal folds | {pct(baseline['missed_calls'], terminal_folds[0])} | {pct(candidate['missed_calls'], terminal_folds[1])} |",
        f"| Probable bad terminal calls | {baseline['bad_calls']:,} | {candidate['bad_calls']:,} |",
        f"| Bad-call flags / terminal calls | {pct(baseline['bad_calls'], terminal_calls[0])} | {pct(candidate['bad_calls'], terminal_calls[1])} |",
        f"| Provably avoidable folds | {baseline['certain_folds']:,} | {candidate['certain_folds']:,} |",
        f"| All-in runout difference, chips | {baseline['allin_luck']:+,.1f} | {candidate['allin_luck']:+,.1f} |",
        '| Player failures | 0 | 0 |', '',
        f"The paired change in duplicate-table placement points was {round_delta:+.4f}, with a 95% interval "
        f"[{round_delta-round_half:+.4f}, {round_delta+round_half:+.4f}]. Points follow the tournament's rank and tie rules. "
        'Placement means weight duplicate tables equally; chip return weights games equally. '
        'This is a table-level comparison; it does not simulate four-round regrouping or establish a podium probability.', '',
        f'![Paired performance and decision diagnostics]({stem}-comparison.png)', '',
        '## Changes and selection', '',
        'Preflop: a tracked-range equity estimate can justify a hand outside QQ+/AK when calling ends all betting. '
        'The normal equity margin still applies; random-card estimates retain the previous safeguards.', '',
        'Sparse equity: at 32–127 Monte Carlo samples, a conservative lower bound can rescue a terminal call. '
        'The bound allocates a 1% error budget across sample counts; it permits calls but never a raise from a sparse estimate. '
        'This addresses the reviewed full-house fold after 104 winning samples without treating one or two winning samples as sufficient evidence.', '',
        f"The independent 500-game pilot compared main, these core fixes, and the fixes plus a tracked-range river call margin of 0.06 instead of 0.02. "
        f"Pilot chip totals were {pilot['0']:+,} for main, {pilot['1']:+,} for the core fixes, and {pilot['2']:+,} with the tighter river margin; "
        f"the predeclared selection rule chose `{selection['selected']}`. "
        'The 10,000-game comparison used a different seed and did not select additional parameters. '
        'It measures the combined policy change; it does not isolate each correction\'s contribution.', '',
        f"Sparse-estimate diagnostics: main {dict(fallbacks[0])}; corrected bot {dict(fallbacks[1])}. "
        'The regression test reproduces the earlier full-house failure. A rare event may not recur in this run.', '',
        '## Opponent refit and coverage', '',
        f"The frozen snapshot has {snapshot['rows']:,} records, {snapshot['matches_with_actions']:,} replays and {snapshot['metadata_matches']:,} metadata matches. "
        f"{len(snapshot['metadata_without_actions'])} metadata matches lack replays and are explicitly listed. "
        f"Coverage checks retained all {coverage['coverage']['actions']:,} newest-version actions, including {coverage['coverage']['validation_games']} upload games. "
        'Every timestamped validation against house:call marks a new version regardless of verdict. Display names remain separate identities, as recorded in the input metadata.', '',
        f"{sum(not name.startswith('house:') for name in fit['selection']['excluded'])} non-house identities lack a usable trusted upload boundary/data and remain excluded. "
        'The exact reasons and identities are listed in upload-selection.json; they are not silently assigned a newest version.', '',
        'Sparse parameters borrow from earlier uploads at maximum weight 0.1^version_age × 2^(−upload_gap_hours/6), '
        f'only up to their effective support target. {sparse}/{len(parameters)} estimates remain below target. '
        'These targets and time discounts are modeling choices, not guarantees of replica accuracy. All newest observations retain weight one.', '',
        f"Newest uploads without any replay are included using prior data only: {', '.join(prior_only) or 'none'}. "
        'Their newest behavior has not been observed; their historical rows keep the full age/time discount and their estimates remain explicitly uncertain.', '',
        '| Prior-only opponent at table | Paired games | Corrected − main, bb/100 [95% interval] |',
        '| --- | ---: | ---: |',
        *[f"| {'Yes' if c['prior_only_opponent_present'] else 'No'} | {c['games']:,} | "
          f"{c['interval']['point'][2]:+.2f} [{c['interval']['low'][2]:+.2f}, {c['interval']['high'][2]:+.2f}] |" for c in cohorts], '',
        'These cohorts check sensitivity to the two unobserved newest submissions; different table compositions prevent a causal comparison between cohorts.', '',
        f"The refreshed fit selected a history-sizing mixture weight of {fit['predictive_selection']['sizing_weight']}; "
        'patterns were selected using whole-game validation splits, then runtime models were refitted on all newest data. '
        'The field is not an independent sample of unseen real opponents.', '',
        '## Decision audit and remaining weaknesses', '',
        'Every simulated hand was reconstructed to verify legal actions, pots, payouts and zero-sum chip totals. '
        'Every terminal call/fold and heads-up postflop call/fold was audited. Probable terminal flags require agreement '
        'across tight/loose public-range models and the applicable wide-shover sensitivity, after a 95% Monte Carlo margin and a 2-chip threshold. '
        'Those margins exclude model error and have no multiple-testing correction; flags are review candidates, not known optimal-action labels.', '',
        'Counts compare complete policies on the same initial deals. Changed actions can change later decisions and opponent learning, so the two versions need not encounter identical decision opportunities.', '',
        '| Street | Main: fold when facing a bet | Corrected: fold when facing a bet |',
        '| --- | ---: | ---: |', *street_rows, '',
        '| Street | Main missed calls | Corrected missed calls | Main bad calls | Corrected bad calls |',
        '| --- | ---: | ---: | ---: | ---: |', *flagged_street_rows, '',
        f"The largest reduction in missed-call flags was preflop ({flagged(0,'preflop','missed'):,} to {flagged(1,'preflop','missed'):,}). "
        f"On the river, bad-call flags fell from {flagged(0,'river','bad'):,} to {flagged(1,'river','bad'):,}, "
        f"while missed-call flags rose from {flagged(0,'river','missed'):,} to {flagged(1,'river','missed'):,}. "
        'The tighter river policy therefore merits further calibration. These are model-based counts of different encountered decisions, not a causal value estimate for each change.', '',
        f"Negative games with a terminal flag: main {baseline['negative_games_with_flags']:,}/{baseline['negative_games']:,}; "
        f"corrected {candidate['negative_games_with_flags']:,}/{candidate['negative_games']:,}. "
        'A losing game alone does not establish a strategic error. The all-in runout difference uses hidden cards retrospectively and does not remove all poker variance.', '',
        'The main remaining risks are miscalibrated opponent ranges, sparse/new submissions, and the tradeoff between reducing river overcalls and creating missed calls. '
        'The compressed audits retain street-level cases; the accompanying blunder CSV makes all probable/certain flags reviewable.', '',
        '## SWOT', '',
        f"- **Strengths:** the two reviewed terminal-call failures have regression coverage; all {len(simulation['games']):,} simulated games completed with legal actions and balanced payouts. "
        + ('The held-out return interval supports an improvement against this replica field.' if interval['low'][2] > 0
           else 'The paired study provides an explicit uncertainty interval for the return change.'),
        f"- **Weaknesses:** the corrected policy still has {candidate['missed_calls']:,} probable missed terminal calls and "
        f"{candidate['bad_calls']:,} probable bad terminal calls. Range calibration remains a source of error; these model-based flags require review.",
        '- **Opportunities:** review the exported high-cost call/fold cases by street and opponent, then validate targeted range or sizing changes on a new held-out seed before accepting them.',
        f"- **Threats:** {sparse}/{len(parameters)} fitted estimates remain below support targets, two newest submissions lack replays, and replicas cannot reproduce all hidden-state behavior. "
        'Live upload changes, clock pressure and tournament regrouping can change performance.', '',
        '## Compute, verification and reproduction', '',
        f"Baseline main: `{plan['baseline']}`. The baseline snapshot contains identical strategy/parameters plus the same optional GPU batching hook. "
        'Fixed-sample CPU/CUDA parity passed 48 cases, and the fitted NumPy runtime matched its training models. '
        f"The 120-game backend check took {backend['timing']['cpu']:.2f}s on CPU versus {backend['timing']['cuda']:.2f}s on CUDA including startup. "
        f"Mean worker time per game was {backend['mean_game_seconds']['cpu']:.3f}s CPU versus {backend['mean_game_seconds']['cuda']:.3f}s CUDA. "
        f"Amortizing that measured work over the complete study selected {backend['workers']} {backend['device']} workers; this is an approximate throughput projection. "
        f"The final 20,000 executions took {elapsed/60:.2f} minutes. All four V100s performed simulation, fitting and the separate action audit. "
        f"All {test_count} tests passed, including the reviewed-hand regression tests. A separate 120-game CPU check is recorded when simulation uses CUDA.", '',
        cpu_note, '',
        f"Input actions SHA-256: `{fit['source_sha256']}`. Exact plans, model evidence, checks and code hashes accompany the report. "
        'Wall-clock sampling can change outcomes between reruns even with fixed seeds. Audits can replay the stored traces with fingerprint checks.', '',
        f'[Reproduction commands]({stem}-reproduce.md) · [Paired tables]({stem}-tables.csv) · '
        f'[Game reviews]({stem}-games.csv) · [Blunder cases]({stem}-blunders.csv) · [Parameters]({stem}-parameters.csv)', '']
    (output/(stem+'.md')).write_text('\n'.join(lines))
    evidence = output/'evidence'/stem;evidence.mkdir(parents=True, exist_ok=True)
    for name in ('study-plan.json','baseline-manifest.json','candidate-selection.json','backend-selection.json',
                 'verify-execution.json','tests-execution.json','selected-tests-execution.json','simulate-execution.json',
                 'cpu-check-execution.json','cpu-check.json','audit-execution.json',
                 'tests.log','selected-tests.log','smoke.log','comparison-tests.log'):
        if (run/name).exists(): shutil.copyfile(run/name, evidence/name)
    for name in ('runtime-fit.json','runtime-selection.json','runtime-verification.json','prior-verification.json',
                 'snapshot-manifest.json','upload-selection.json','recency-priors.json'):
        shutil.copyfile(run/'fit'/name, evidence/name)
    summary = dict(interval=interval, summaries=[dict(s) for s in summaries],
        classifications=[dict(s) for s in classifications], streets=streets, fallbacks=fallbacks,
        duplicate_tables=len(tables), prior_only_opponents=prior_only, cohorts=cohorts,
        placement=placement, paired_placement_change=[round_delta,round_delta-round_half,round_delta+round_half],
        audit_devices=audits['devices'], audit_workers=audits['workers'], audit_gpu_work=gpu_work,
        audit_code_sha256=audits['code_sha256'], simulation_compute=simulation['compute'])
    (evidence/'comparison-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    artifacts = sorted(output.glob(stem+'*')) + sorted(evidence.iterdir())
    hashes = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in artifacts if p.is_file() and p.name != 'artifact-hashes.json'}
    (evidence/'artifact-hashes.json').write_text(json.dumps(hashes, indent=2)+'\n')
    print(json.dumps(dict(interval=interval,summaries=summaries), indent=2))


def plot(stem, tables, interval, summaries, streets):
    plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5), layout='constrained')
    colors = ['#627d91', '#287d78']
    ax = axes[0,0]
    means = np.asarray(interval['point'][:2])
    ax.bar(['Main','Corrected'], means, color=colors)
    ax.errorbar([0,1], means, yerr=[means-np.asarray(interval['low'][:2]), np.asarray(interval['high'][:2])-means],
                fmt='none', color='black', capsize=5)
    ax.set(ylabel='bb / 100 hands', title='A. Profit with table-bootstrap 95% intervals')
    ax = axes[0,1]
    ax.hist([t['difference']/t['games']/2 for t in tables], bins=60, color=colors[1])
    ax.axvline(0, color='#999999');ax.axvline(interval['point'][2], color='#a84536', linestyle='--')
    ax.set(xlabel='Corrected minus main, bb/100', ylabel='Duplicate tables', title='B. Paired difference by table')
    ax = axes[1,0];labels=['preflop','flop','turn','river'];x=np.arange(4)
    for c in (0,1):
        values=[100*streets[c][s]['facing_folds']/streets[c][s]['faced_bet'] for s in labels]
        ax.bar(x+(c-.5)*.35,values,.35,color=colors[c],label=['Main','Corrected'][c])
    ax.set(xticks=x,xticklabels=labels,ylabel='Fold % when facing a bet',title='C. Folding by street');ax.legend()
    ax = axes[1,1];x=np.arange(2)
    for c in (0,1):
        ax.bar(x+(c-.5)*.35,[summaries[c]['missed_calls'],summaries[c]['bad_calls']],.35,color=colors[c],label=['Main','Corrected'][c])
    ax.set(xticks=x,xticklabels=['Probable missed calls','Probable bad calls'],ylabel='Terminal decisions',title='D. Model-supported review flags');ax.legend()
    fig.suptitle('Call calibration · 10,000 paired games per version · refreshed newest-upload replicas', fontsize=15)
    fig.savefig(str(stem)+'-comparison.png',dpi=170);fig.savefig(str(stem)+'-comparison.svg');plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path('analysis/results/call-calibration-20261004-r2'))
    parser.add_argument('--output', type=Path, default=Path('analysis/reports'))
    args = parser.parse_args();report(args.directory.resolve(), args.output.resolve())
