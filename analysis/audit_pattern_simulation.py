"""Strictly reconstruct simulation traces and audit public-information decisions.

All terminal calls/folds and heads-up postflop calls/folds receive the existing
tight/loose range audit, plus a wide-shover sensitivity where public history
supports main's shover classification. Other actions are classified from public
context and outcomes, without inventing uncomputed EVs. Hidden-card diagnostics
are explicitly retrospective. Each game is resumable with content fingerprints.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import gzip
from hashlib import sha256
import json
import multiprocessing as mp
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import halliday_performance as performance
from analysis.halliday_report import BLUNDERS, classify, classify_hand


def normalized_events(record, names, mid):
    seat_names = [names[i] for i in record['seat_map']]
    holes = {seat_names[int(i)]: cards for i, cards in record['holes'].items()}
    common = dict(match=mid, hand=record['hand'], holes=holes)
    board = []
    result = []
    for event in record['events']:
        kind = event['type']
        if kind == 'action':
            result.append(dict(common, **{k: v for k, v in event.items() if k not in ('type', 'hand')},
                               bot=seat_names[event['seat']], board=list(board)))
        elif kind == 'street':
            board = event['board']
            result.append(dict(common, event='board', board=board, street=event['street']))
        elif kind == 'hand_end':
            for pot in event['pots']:
                result.append(dict(common, event='pot', amount=pot['amount'],
                                   winners=[seat_names[i] for i in pot['winners']]))
            result.append(dict(common, event='hand_end', board=event['board'],
                               deltas_by_seat=event['deltas'], deltas_by_bot=record['deltas_by_bot'],
                               deltas_bot_names=names))
    return result


def reconstruct_trace(trace, mid, names):
    identity, result = trace['identity'], trace['result']
    assert all(v == 'OK' for v in result['verdicts']), (mid, result['verdicts'])
    assert sum(result['chips']) == 0
    assert len(trace['hands']) == identity['deals'] == 100
    assert [h['hand'] for h in trace['hands']] == list(range(100))
    meta = dict(id=mid, names=names, chips=result['chips'], kind='simulation', at=None)
    diagnostics = {(d['view']['hand'], len(d['view']['history']) + 1): d for d in trace['decisions']}
    rows, hands, shoves = [], [], Counter()
    for record in trace['hands']:
        actions, hand = performance.reconstruct(normalized_events(record, names, mid), meta)
        previous = record['hand']
        known = {name for name, count in shoves.items() if previous >= 8 and count / previous >= .8}
        for row in actions:
            row['known_shovers'] = [i for i in row['opponents'] if row['seats'][i] in known]
            row['prior_hands'] = previous
            row['prior_preflop_shoves'] = dict(shoves)
            diagnostic = diagnostics.pop((row['hand'], row['action_index']))
            view = diagnostic['view']
            assert view['hole'] == row['hole'] and view['board'] == row['board']
            assert view['pot'] == row['pot'] and view['to_call'] == row['call']
            row['diagnostic'] = {k: v for k, v in diagnostic.items() if k != 'view'}
            row['oracle'] = None
            row['public'] = {}
            row['hindsight_final_equity'] = None
            row['guaranteed_profitable_call'] = False
        shoves.update({a['bot'] for a in hand['log'] if a['street'] == 'preflop'
                       and a['action'] == 'raise' and a['amount'] == 200})
        rows.extend(actions)
        hands.append(hand)
    assert not diagnostics, 'Unmatched decision diagnostics'
    assert [sum(h['deltas_by_bot'][i] for h in trace['hands']) for i in range(len(names))] == result['chips']
    assert sum(h['chips'] for h in hands) == result['chips'][0]
    return rows, hands


def eligible(row):
    return row['action'] in ('call', 'fold') and (
        row['terminal_call'] or row['call'] == 0 or
        (row['street'] != 'preflop' and len(row['opponents']) == 1))


def broad_shovers(row):
    """Publicly frequent shovers under main's permissive classification rule.

    Main counts the current dealt hand and already observed current actions.
    This sensitivity is applied to every qualifying preflop terminal decision,
    independently of the action's result or the first two range-model scores.
    """
    if row['street'] != 'preflop' or not row['terminal_call']:
        return []
    hands = row['prior_hands'] + 1
    current = {a['bot'] for a in row['history'] if a['street'] == 'preflop'
               and a['action'] == 'raise' and a['amount'] == 200}
    return [seat for seat in row['opponents'] if hands >= 8 and row['seats'][seat] in current
            and (row['prior_preflop_shoves'].get(row['seats'][seat], 0)+1) >= max(3, .25*hands)]


def fingerprint():
    paths = [Path(__file__), ROOT/'analysis/halliday_performance.py', ROOT/'analysis/halliday_report.py',
             ROOT/'bot/ranges.py', ROOT/'bot/params.py', ROOT/'bot/engine.py',
             ROOT/'vendor/macpoker-src/macpoker/evaluator.py', ROOT/'harness/gpu_equity.py',
             ROOT/'harness/gpu_rank.cu', ROOT/'sparring/competitors/from_data_patterns/bots.json']
    return {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in paths}


def audit_one(job):
    started = time.monotonic()
    path, output, names_by_id, code_hashes = job
    encoded = path.read_bytes()
    identity = dict(trace_sha256=sha256(encoded).hexdigest(), code_sha256=code_hashes)
    target = output/path.name
    if target.exists():
        with gzip.open(target, 'rt') as f:
            saved = json.load(f)
        if saved['identity'] != identity:
            raise ValueError(f'Audit fingerprint changed: {target}; use a fresh audit directory')
        return saved['summary']
    trace = json.loads(gzip.decompress(encoded))
    names = ['Halliday'] + [names_by_id[spec.rsplit('@', 1)[1]] for spec in trace['identity']['opponents']]
    mid = path.name.removesuffix('.json.gz')
    rows, hands = reconstruct_trace(trace, mid, names)
    selected = [r for r in rows if eligible(r)]
    before = performance._GPU.metadata()
    scored, hands, gpu = performance.analyse_match((selected, hands))
    assert len(scored) == len(selected)
    for row in scored:
        broad = broad_shovers(row)
        if broad and row['call'] > 0:
            wider = dict(row, known_shovers=sorted(set(row['known_shovers']) | set(broad)))
            row['public']['wide_shover'] = performance.payoff_summary(performance.public_ranks(wider, 'loose'), row)
        row['broad_shovers'] = [row['seats'][seat] for seat in broad]
    gpu = performance._GPU.metadata()
    for key in ('batches', 'ranked_hands', 'gpu_seconds'):
        gpu[key] -= before[key]
    by_hand = defaultdict(list)
    hand_map = {h['hand']: h for h in hands}
    for row in rows:
        row.setdefault('broad_shovers', [])
        classify(row, hand_map[row['hand']])
        values = [row['public'].get(model) for model in ('tight', 'loose')]
        if row['public'].get('wide_shover') and all(values) and row['action'] == 'call':
            original_high = max(v['call_ev'] + 1.96*v['ev_se'] for v in values)
            if original_high < -2 and row['classification'] != 'probable_bad_terminal_call':
                row['classification'] = 'range_sensitive_shove_call_review'
                row['reason'] = ('Tight/loose selective ranges reject the call, but a public-history-supported '
                                 'wide-shover sensitivity does not. Decision quality depends on whether the shove range is selective.')
        row['ev_audited'] = eligible(row)
        by_hand[row['hand']].append(row)
    for hand in hands:
        hand['loss_category'] = classify_hand(hand, by_hand[hand['hand']])
    cats = defaultdict(lambda: dict(hands=0, chips=0))
    for hand in hands:
        cats[hand['loss_category']]['hands'] += 1
        cats[hand['loss_category']]['chips'] += hand['chips']
    flags = [r for r in rows if r['classification'] in BLUNDERS]
    runouts = [h['allin_runout'] for h in hands if h['allin_runout']]
    streets = {}
    phases = []
    for street in ('preflop', 'flop', 'turn', 'river'):
        group = [r for r in rows if r['street'] == street]
        streets[street] = dict(actions=len(group), faced_bet=sum(r['call'] > 0 for r in group),
            facing_folds=sum(r['action'] == 'fold' and r['call'] > 0 for r in group),
            terminal_folds=sum(r['action'] == 'fold' and r['terminal_call'] for r in group),
            terminal_calls=sum(r['action'] == 'call' and r['terminal_call'] for r in group),
            **dict(Counter(r['action'] for r in group)))
    for start in range(0, 100, 25):
        hs = hands[start:start+25]
        rs = [r for r in rows if start <= r['hand'] < start+25]
        phases.append(dict(hands=len(hs), chips=sum(h['chips'] for h in hs), actions=len(rs),
                           folds=sum(h['folded'] for h in hs), flags=sum(r['classification'] in BLUNDERS for r in rs)))
    result = trace['result']
    summary = dict(match=mid, table=result['table'], game=result['game'], opponents=names[1:],
        size=len(names), hands=len(hands), chips=result['chips'][0], folds=sum(h['folded'] for h in hands),
        actions=len(rows), facing_decisions=sum(r['call'] > 0 for r in rows),
        flags=len(flags), bad_calls=sum(r['classification'] == 'probable_bad_terminal_call' for r in flags),
        missed_calls=sum(r['classification'] == 'probable_missed_terminal_call' for r in flags),
        certain_folds=sum(r['classification'] == 'certain_avoidable_fold' for r in flags),
        public_scored=sum(bool(r['public']) for r in rows), ev_audited=len(scored),
        classifications=dict(Counter(r['classification'] for r in rows)),
        loss_categories=dict(cats), streets=streets, phases=phases,
        allin_count=len(runouts), allin_luck=sum(x['luck'] for x in runouts),
        allin_expected=sum(x['expected_chips'] for x in runouts), allin_actual=sum(x['realized_chips'] for x in runouts),
        flagged_actions=[r['id'] for r in flags],
        worst_hands=[dict(hand=h['hand'], chips=h['chips'], hole=h['hole'], board=h['board'],
                          loss_category=h['loss_category']) for h in sorted(hands, key=lambda h: h['chips'])[:5]],
        vpip_hands=result['behavior'][0]['vpip_hands'], pfr_hands=result['behavior'][0]['pfr_hands'],
        think_ms=result['think_ms'][0], max_ms=result['max_ms'][0], gpu=gpu,
        audit_seconds=time.monotonic()-started)
    row_keys = ('id', 'hand', 'action_index', 'street', 'action', 'amount', 'seat', 'hole', 'board',
        'pot', 'call', 'pot_odds', 'terminal_call', 'invested', 'hand_chips', 'match_chips', 'made_category',
        'top_pair', 'draw', 'oracle', 'public', 'hindsight_final_equity', 'guaranteed_profitable_call',
        'classification', 'tags', 'reason', 'public_ev_lower', 'public_ev_upper', 'ev_audited', 'diagnostic',
        'broad_shovers', 'prior_hands', 'prior_preflop_shoves')
    hand_keys = ('hand', 'seat', 'hole', 'board', 'chips', 'folded', 'invested', 'showdown', 'loss_category', 'allin_runout')
    payload = dict(identity=identity, summary=summary, decisions=[{k: r[k] for k in row_keys} for r in rows],
                   hands=[{k: h[k] for k in hand_keys} for h in hands])
    temporary = target.with_suffix('.tmp')
    with gzip.open(temporary, 'wt', compresslevel=1) as f:
        json.dump(payload, f, separators=(',', ':'), allow_nan=False)
    os.replace(temporary, target)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, default=Path('analysis/results/simulation-20261004-r4'))
    p.add_argument('--devices', default='0,1,2,3')
    p.add_argument('--workers', type=int, default=12)
    p.add_argument('--trace-subdir', default='traces')
    p.add_argument('--output-subdir', default='audit')
    p.add_argument('--limit', type=int)
    args = p.parse_args()
    run = args.directory
    paths = sorted((run/args.trace_subdir).glob('*.json.gz'))
    if args.limit:
        paths = paths[:args.limit]
    else:
        expected = 60 if args.trace_subdir == 'pilot-traces' else json.loads((run/'simulation-plan.json').read_text())['games']
        assert len(paths) == expected, (len(paths), expected)
    assert paths
    output = run/args.output_subdir
    output.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((ROOT/'sparring/competitors/from_data_patterns/bots.json').read_text())
    names_by_id = {key: b['name'] for key, b in catalog['bots'].items()}
    devices = [int(x) for x in args.devices.split(',')]
    ctx = mp.get_context('spawn')
    queue = ctx.Queue()
    for i in range(args.workers):
        queue.put(devices[i % len(devices)])
    started = time.monotonic()
    hashes = fingerprint()
    summaries = []
    with ProcessPoolExecutor(args.workers, mp_context=ctx, initializer=performance.worker_init,
                             initargs=(queue,)) as pool:
        jobs = ((path, output, names_by_id, hashes) for path in paths)
        for i, summary in enumerate(pool.map(audit_one, jobs, chunksize=1), 1):
            summaries.append(summary)
            if i % 100 == 0 or i == len(paths):
                print(f'{i}/{len(paths)} audited in {time.monotonic()-started:.1f}s', flush=True)
    (run/(args.output_subdir+'-summary.json')).write_text(json.dumps(dict(games=summaries,
        code_sha256=hashes, elapsed_seconds=time.monotonic()-started, devices=devices, workers=args.workers),
        separators=(',', ':'), allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
