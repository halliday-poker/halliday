"""Publish a newest-segment rerun report, compact evidence and exact commands."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from opponent_model.data import load_cache


def read(path):
    return json.loads(path.read_text())


def ci(values):
    return f'{values[0]:+.3f} ± {values[1]:.3f}'


def publish(run, audit):
    tag = run.name.removeprefix('refresh-')
    reports = ROOT/'analysis/reports'
    evidence = reports/'evidence'/tag
    evidence.mkdir(parents=True, exist_ok=True)
    names = ['snapshot-manifest.json', 'baseline-manifest.json', 'latest-selection.json',
             'latest-predictive-comparison.json', 'behavior-comparison.json', 'benchmark-plan.json',
             'field-summary.json', 'fidelity-plan.json', 'fidelity-summary.json',
             'tournament-verification.json', 'main-resource-check.json']
    index = {}
    sources = [(name, run/name) for name in names] + [('halliday-summary.json', audit/'summary.json'),
        ('halliday-verification.json', audit/'verification.json'), ('halliday-gpu-run.json', audit/'compute-run.json')]
    for name, source in sources:
        raw = source.read_bytes()
        value = json.loads(raw)
        removed = []
        if 'table_metrics' in value:
            value.pop('table_metrics'); removed.append('table_metrics')
        if name == 'latest-predictive-comparison.json':
            for model in value['models'].values():
                for key in ('by_match', 'by_bot', 'calibration', 'streets'):
                    model.pop(key, None)
            removed.append('per-match/bot predictive metrics and calibration bins')
        target = evidence/name
        target.write_text(json.dumps(value, indent=2)+'\n')
        index[name] = dict(source=str(source), source_sha256=sha256(raw).hexdigest(), omitted=removed,
                           exported_sha256=sha256(target.read_bytes()).hexdigest())
    tournament_raw = (run/'tournament.json').read_bytes()
    tournament = json.loads(tournament_raw)
    compact = {key: value for key, value in tournament.items() if key not in ('games', 'events')}
    compact['games'] = len(tournament['games']); compact['events'] = len(tournament['events'])
    target = evidence/'tournament-summary.json'
    target.write_text(json.dumps(compact, indent=2)+'\n')
    index[target.name] = dict(source=str(run/'tournament.json'), source_sha256=sha256(tournament_raw).hexdigest(),
                              exported_sha256=sha256(target.read_bytes()).hexdigest(), omitted=['games', 'events'])
    for name in ('tests-cuda.log', 'latest-field-pool.txt', 'latest-halliday-matches.json',
                 'strict-latest-halliday-matches.json', 'latest-matched-tables.json'):
        raw = (run/name).read_bytes(); (evidence/name).write_bytes(raw)
        index[name] = dict(source=str(run/name), exported_sha256=sha256(raw).hexdigest())
    (evidence/'index.json').write_text(json.dumps(index, indent=2)+'\n')
    for source_name, label in [('blunders.csv', 'blunders'), ('match-reviews.csv', 'match-reviews')]:
        (reports/f'halliday-{label}-{tag}.csv').write_text((audit/source_name).read_text())

    snapshot, base, selected = (read(run/name) for name in ('snapshot-manifest.json', 'baseline-manifest.json', 'latest-selection.json'))
    prediction = read(run/'latest-predictive-comparison.json')
    summary = read(audit/'summary.json')
    field, fidelity = read(run/'field-summary.json'), read(run/'fidelity-summary.json')
    reviews = read(audit/'match-reviews.json')
    calls = summary['classifications'].get('probable_bad_terminal_call', 0)
    missed = summary['classifications'].get('probable_missed_terminal_call', 0)
    total_games = field['evidence'][0]['games'] + fidelity['evidence'][0]['games'] + len(tournament['games'])
    data = load_cache(run/'context-features.npz')
    chosen = set(read(run/'strict-latest-halliday-matches.json'))
    hand_counts = [values for i, values in data.hands['Halliday'].items() if data.matches[i]['id'] in chosen]
    real_vpip = sum(v[1] for v in hand_counts)/sum(v[0] for v in hand_counts)
    real_pfr = sum(v[2] for v in hand_counts)/sum(v[0] for v in hand_counts)
    resource = read(run/'main-resource-check.json')
    gpu_run = read(audit/'compute-run.json')
    classifications = read(audit/'classified-actions.json')
    terminal_calls = [r for r in classifications if r['classification'] == 'probable_bad_terminal_call']
    terminal_misses = [r for r in classifications if r['classification'] == 'probable_missed_terminal_call']
    won_flags = sum(r['hand_chips'] > 0 for r in terminal_calls)
    negative_hidden = sum(r['oracle']['call_ev'] < 0 for r in terminal_misses)
    savings = -sum(r['hand_chips'] + r['invested'] for r in terminal_calls)
    negative_flagged = sum(m['chips'] < 0 and m['flags'] > 0 for m in reviews)
    test_log = (run/'tests-cuda.log').read_text()
    tests = re.search(r'Ran (\d+) tests in ([\d.]+)s', test_log)
    assert tests and test_log.rstrip().endswith('OK'), 'Full test suite must pass before publication'
    assert resource['passed'] and not tournament['bad_games']
    assert all(e['failures'] == 0 for result in (field, fidelity) for e in result['evidence'])
    model_comparison = read(run/'behavior-comparison.json')
    gains_supported = all(p['three_comparison_adjusted_ci'][0] > 0 for p in prediction['paired_comparisons'])
    strict_count = selected['all_seats_latest_matches']
    max_rss = max(g['resources']['RESOURCE_USAGE']['max_rss_kib'] for g in resource['games'])
    max_clock = max(g['think_ms'] for g in resource['games']) / 1000
    current = read(ROOT/'sparring/competitors/from_data/profiles.json')
    modes = Counter(p['behavior']['status'] for p in current['profiles'].values())
    rows = [f'# Newest-segment analysis — {tag}', '',
        'The primary replay comparison includes only matches where Halliday **and every opponent** belong to their newest observed intervals. Simulations instantiate only newest trusted ladder intervals and use the exact freshly fetched `main` bot as their baseline.', '',
        f'Baseline commit: `{base["main_commit"]}`; snapshot `{base["baseline"]}`, harness hash `{field["summary"][0]["hash"]}`. Every file was copied directly from that Git tree. The previous merged-main research snapshot included the analysis branch’s GPU engine hook; the early fourteen strategy experiments used an older frozen baseline. They are not the baseline for this rerun.', '',
        'Successful validation marks an upload, not proof that it was selected as main. These data support newest **observed** intervals, not certified deployment versions. Display identities may also be aliases; no team/source hash is available to resolve every rename.', '',
        '## Input and selection', '',
        f'- Actions SHA-256: `{snapshot["files"]["actions.jsonl"]["sha256"]}`.',
        f'- {snapshot["rows"]:,} rows, {snapshot["matches_with_actions"]:,} replay matches and {snapshot["metadata_matches"]:,} metadata matches. {len(snapshot["metadata_without_actions"])} metadata matches have no replay rows and are excluded.',
        f'- {len(current["profiles"])} rebuilt identities: {modes["fitted_public_context_policy"]} learned policies and {modes["sparse_scaffold_fallback"]} sparse/validation fallbacks.',
        f'- Strict simulation field: {len(selected["included_opponents"])} external identities. Excludes Halliday, the house bot, validation-only evidence and identities without trusted play timestamps.',
        f'- Halliday newest interval: {selected["latest_halliday_matches"]} ladder matches; {selected["all_seats_latest_matches"]} have every seat in its newest interval and form the primary replay cohort.', '',
        f'[Exact selection and exclusions](evidence/{tag}/latest-selection.json) retain each interval, match ID and successful-upload boundary. The shared neural model learns from historical intervals with separate epoch features; older intervals are not instantiated as opponents in this field. The initial upload was incomplete and was not analysed. The final frozen copy passed NUL, JSON, metadata and collected-state checks.', '',
        '## Latest-cohort Halliday performance', '',
        '| Metric | Result |', '|---|---:|',
        f'| Matches / hands / decisions | {summary["matches"]} / {summary["hands"]:,} / {summary["actions"]:,} |',
        f'| Net chips / bb per 100 hands | {summary["chips"]:+,} / {summary["chips"]/2/summary["hands"]*100:+.3f} |',
        f'| Folds / fraction of hands | {summary["folds"]:,} / {summary["folds"]/summary["hands"]:.2%} |',
        f'| Preflop folds / fraction of hands | {summary["streets"]["preflop"].get("fold",0):,} / {summary["streets"]["preflop"].get("fold",0)/summary["hands"]:.2%} |',
        f'| Probable bad terminal calls / missed terminal calls | {calls} / {missed} |',
        f'| Auditable terminal folds / all folds | {summary["terminal_folds"]} / {summary["folds"]:,} |',
        f'| Losing games / those with terminal flags | {summary["losing_matches"]} / {sum(m["chips"]<0 and m["flags"]>0 for m in reviews)} |', '',
        f'{won_flags} of {calls} flagged terminal calls won their hands. Folding at the flagged calls changes recorded results by {savings:+,} chips. {negative_hidden} of {missed} model-supported missed calls had negative expectation against the actual hidden hands. These are sensitivity-model review candidates, not certain mistakes. Losing games with a terminal decision flag: {negative_flagged}/{summary["losing_matches"]}. Checks, raises and nonterminal choices are not exhaustively optimized.', '',
        f'Record decision-time ranges and equity for reviewing these contexts; the current replay lacks those diagnostics. Historical calling-leak counts should not automatically carry forward to this cohort. Only {summary["terminal_folds"]/summary["folds"]:.2%} of folds meet the terminal audit condition; the true unnecessary-fold rate remains unknown. Changes in table size, opponents and selection prevent treating differences from the earlier report as a causal code improvement.', '',
        f'[Detailed report and hand histories](halliday-performance-{tag}.md) · [Flagged actions](halliday-blunders-{tag}.csv) · [Every match review](halliday-match-reviews-{tag}.csv).', '',
        '## Predictive accuracy on newest intervals', '',
        f'The common test contains {prediction["actions"]:,} decisions from {prediction["matches"]} held-out matches, restricted to the newest trusted intervals of included identities and Halliday. Whole matches are held out together. Other seats need not be in their newest interval for this conditional action-prediction test. Selection and stopping use validation data, not these test scores.', '',
        '| Predictor | Action log loss ↓ | Accuracy ↑ | Brier ↓ | Raise-target MAE, chips ↓ |', '|---|---:|---:|---:|---:|']
    for mode, values in prediction['models'].items():
        rows.append(f'| {mode} | {values["nll"]:.4f} | {values["accuracy"]:.2%} | {values["brier"]:.4f} | {values["sizing_mae"]:.3f} |')
    rows += ['', f'The validation-selected model is **{model_comparison["selected"]}**. Upload-model gains over the scaffold, no-interval model and randomized-boundary control '+('all have positive' if gains_supported else 'do not all have positive')+' per-match bootstrap intervals after adjustment for three comparisons. Predictive support for upload intervals does not establish deployment at every validation event.', '',
             '## Exact-main simulations', '',
             f'The broad field used {field["evidence"][0]["tables"]} duplicate tables and {field["evidence"][0]["games"]:,} complete 100-hand games. Exact main earned **{ci(field["summary"][0]["metrics"]["mbb"]["mean_ci95"])} bb/100** and **{ci(field["summary"][0]["metrics"]["round_pts"]["mean_ci95"])} round points**. The field samples 4–6 seats, so its returns are not directly comparable with the observed cohort’s different table mix.', '',
             f'A separate composition-matched check uses the {strict_count} strict observed lineups and fresh duplicate decks. Both Halliday candidates face the same newest opponent replicas. This describes behavior of refitted models, not held-out closed-loop validation or reconstruction of the original deals.', '',
             '| Halliday source | bb/100, approximate 95% interval | Folded hands | VPIP | PFR |', '|---|---:|---:|---:|---:|',
             f'| Recorded newest interval, all seats newest | {ci([x/2 for x in summary["match_mean_ci"]])} | {summary["folds"]/summary["hands"]:.2%} | {real_vpip:.2%} | {real_pfr:.2%} |']
    for name, record in zip(('Exact main', 'Latest Halliday replica'), fidelity['summary']):
        b = record['behavior']
        rows.append(f'| {name} | {ci(record["metrics"]["mbb"]["mean_ci95"])} | {b["fold_rate"]:.2%} | {b["vpip"]:.2%} | {b["pfr"]:.2%} |')
    t = tournament['summary'][0]
    rows += ['', f'{t["repeats"]} four-round tournaments with {len(selected["included_opponents"])+1} entrants completed {len(tournament["games"]):,} games. Mean final rank: **{ci(t["mean_rank"])}**; cumulative round points: **{ci(t["placement"])}**; definite top-three finishes: **{t["strictly_top_three"]}/{t["repeats"]}**. The roster is an observed-identity surrogate; actual entrants, source versions and prize tie-breaks may differ.', '',
        f'Total this rerun: **{total_games:,} simulation games / {total_games*100:,} hands**, with no player failures. Complete rotations, chip conservation and tournament scoring/regrouping passed their audits. Intervals reflect sampled tables/events and exclude opponent-model error; this limited event sample cannot establish a stable tournament win probability.', '',
        '## GPU use, runtime limits and verification', '',
        f'Four V100s refit the estimators and trained four model ablations concurrently. {gpu_run["workers"]} GPU audit workers performed {gpu_run["ranked_hands"]:,} rankings across {gpu_run["matches"]} replay matches. Simulation selected {field["evidence"][0]["compute"]["workers"]} {field["evidence"][0]["compute"]["device"]} workers. Reason: {field["evidence"][0]["compute"].get("fallback_reason", "compatible GPU engine available")}. The tournament harness checks compatibility before choosing CUDA; merely creating GPU contexts does not accelerate an incompatible engine.', '',
        f'All **{tests[1]} tests passed with CUDA enabled**. Exact main also passed {len(resource["games"])} restricted CPU games: one core, 512 MiB address-space limit, read-only filesystem, fresh 64 MiB temporary storage, and actual 30 s + 0.1 s/hand clocks. Maximum RSS was {max_rss:,} KiB and cumulative action wait {max_clock:.3f} s. These are cooperative-code resource checks, not a complete replica of the judge sandbox.', '',
        f'[Reproduction commands](reproduce-latest-{tag}.md) · [Compact evidence index](evidence/{tag}/index.json). Raw inputs and full game logs remain local under the recorded run directory. Production bot strategy was not changed.', '']
    (reports/f'latest-analysis-{tag}.md').write_text('\n'.join(rows))
    commands = f'''# Reproduce newest-segment analysis — {tag}

Run from the repository root with Python 3.12, the vendored macpoker SDK,
NumPy and the validated PyTorch 2.10.0+cu128 environment. CUDA analysis needs
four V100 devices and the native harness CUDA toolkit described in its README.
The exact recorded baseline is `{base['main_commit']}` / `{field['summary'][0]['hash']}`.

These commands reproduce the completed study from its frozen inputs and cached
validation outcomes. They replace derived outputs in the run directories and
regenerate `sparring/competitors/from_data`; they do not change `bot/`.

```sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
analysis_python=.venv-estimators/bin/python
analysis_run={run}
analysis_audit={audit}

$analysis_python -B analysis/run_refresh_models.py --directory "$analysis_run" --epochs 100

$analysis_python -B analysis/halliday_performance.py extract --snapshot "$analysis_run/source" --match-ids "$analysis_run/strict-latest-halliday-matches.json" --directory "$analysis_audit"
$analysis_python -B analysis/halliday_performance.py prepare --directory "$analysis_audit"
$analysis_python -B analysis/halliday_performance.py compute --directory "$analysis_audit" --devices 0,1,2,3
$analysis_python -B analysis/halliday_report.py --directory "$analysis_audit"
$analysis_python -B analysis/verify_halliday_report.py --directory "$analysis_audit"
$analysis_python -B analysis/render_halliday_report.py --directory "$analysis_audit"

$analysis_python -B analysis/run_latest_benchmarks.py --directory "$analysis_run" --tables 400 --events 10 --workers 12
$analysis_python -B analysis/run_latest_fidelity.py --directory "$analysis_run" --workers 12
$analysis_python -B harness/resource_check.py {base['baseline']} --repeats 3 --output "$analysis_run/main-resource-check.json"
$analysis_python -B -m unittest discover -s tests -v > "$analysis_run/tests-cuda.log" 2>&1
$analysis_python -B analysis/export_latest_analysis.py --directory "$analysis_run" --audit "$analysis_audit"
```

The resource checker requires Linux permissions for its isolation setup.
Input SHA-256 is `{snapshot['files']['actions.jsonl']['sha256']}`. Cached
`source/` and `validation-meta.json` must be preserved alongside the code;
raw inputs are not committed. Seeds, selected match IDs, model hashes and
source manifests are in the evidence bundle. Wall-clock equity deadlines can
change completed sample counts under different host load, despite fixed seeds.

For another completed upload, create fresh directories and freeze current main:

```sh
git fetch origin main
analysis_python=.venv-estimators/bin/python
analysis_run=analysis/results/refresh-next
analysis_audit=analysis/results/halliday-performance-next
$analysis_python -B analysis/freeze_snapshot.py --source analysis/results/input-snapshot --directory "$analysis_run" --baseline-ref origin/main --baseline-output snapshots/main-next
$analysis_python -B -m opponent_model.fetch_validation --matches "$analysis_run/source/matches.json" --output "$analysis_run/validation-meta.json"
```

Then run the pipeline above with those new directory variables and use
`snapshots/main-next` for the resource check. New inputs imply new results;
the frozen current-run numbers are not asserted for future snapshots.
'''
    (reports/f'reproduce-latest-{tag}.md').write_text(commands)
    print(reports/f'latest-analysis-{tag}.md')
    print(reports/f'reproduce-latest-{tag}.md')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--audit', type=Path, required=True)
    args = parser.parse_args()
    publish(args.directory, args.audit)
