"""Reproducible replay audit of Halliday; see the generated report for scope.

Input extraction is kept separate from computation so later collector updates
cannot change a running analysis. Source hashes accompany every output.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from hashlib import sha256
from itertools import combinations
import json
import math
import multiprocessing as mp
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "vendor/macpoker-src"))
import numpy as np
from bot.engine import _evaluate, _parse_card
from macpoker.evaluator import evaluate as sdk_evaluate

TARGET = "Halliday"
STREET = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}
CATEGORIES = ("high card", "pair", "two pair", "trips", "straight", "flush", "full house", "quads", "straight flush")


def has_any_draw(hole, board):
    if not board or len(board) >= 5:
        return False
    cards = hole + board
    suits = Counter(c[1] for c in cards)
    if any(count == 4 and any(c[1] == suit for c in hole) for suit, count in suits.items()):
        return True
    rank = {c: i + 2 for i, c in enumerate('23456789TJQKA')}
    own = {rank[c[0]] for c in hole}
    public = {rank[c[0]] for c in board}
    if 14 in own:
        own.add(1)
    if 14 in public:
        public.add(1)
    for start in range(1, 11):
        run = set(range(start, start + 5))
        if len(run - (own | public)) == 1 and (run - public) & own:
            return True
    return False


def code(value):
    return (value[0] << 20) + sum(rank << (16 - i * 4) for i, rank in enumerate(value[1:]))


def pots(contributions, live, hero):
    """Hero-eligible side pots, including dead chips and uncalled returns."""
    result, previous = [], 0
    for level in sorted(set(contributions) - {0}):
        contributors = [i for i, amount in enumerate(contributions) if amount >= level]
        eligible = [i for i in contributors if i in live]
        amount = (level - previous) * len(contributors)
        if hero in eligible:
            result.append((amount, eligible))
        previous = level
    return result


def payout(rankings, contributions, live, hero):
    """Expected gross return for hero, per sampled final board; fractional ties."""
    result = np.zeros(len(rankings))
    for amount, eligible in pots(contributions, live, hero):
        values = rankings[:, eligible]
        best = values.max(axis=1)
        tied = (values == best[:, None]).sum(axis=1)
        result += (rankings[:, hero] == best) * amount / tied
    return result


def reconstruct(events, meta):
    end = events[-1]
    assert end.get("event") == "hand_end", "incomplete hand"
    actions = [e for e in events if "action" in e]
    names = meta["names"]
    n = len(names)
    assert end["deltas_bot_names"] == names, "bot order differs from metadata"
    shift = (actions[0]["seat"] - names.index(actions[0]["bot"])) % n
    seats = [names[(i - shift) % n] for i in range(n)]
    hero = seats.index(TARGET)
    holes = end["holes"]
    known = [card for cards in holes.values() for card in cards] + end["board"]
    assert len(known) == len(set(known)), "duplicate hole/board cards"
    assert set(holes) == set(names), "missing hole cards"
    stacks, bets, contributions = [200] * n, [0] * n, [0] * n
    for seat, blind in ((0 if n == 2 else 1, 1), (1 if n == 2 else 2, 2)):
        stacks[seat] -= blind
        bets[seat] = contributions[seat] = blind
    folded, acted = set(), set()
    street, board, current, increment, total = "preflop", [], 2, 2, 3
    history, rows, pre_raises, action_index = [], [], 0, 0
    for event in events:
        if event.get("event") == "board":
            street, board = event["street"], event["board"]
            assert len(board) == {"flop": 3, "turn": 4, "river": 5}[street]
            bets, current, increment, acted = [0] * n, 0, 2, set()
            continue
        if "action" not in event:
            continue
        action_index += 1
        seat, kind, amount = event["seat"], event["action"], event["amount"]
        assert seats[seat] == event["bot"]
        assert event["holes"] == holes, "hole cards change within hand"
        assert street == event["street"] and seat not in folded and stacks[seat] > 0
        call = min(stacks[seat], current - bets[seat])
        maximum = bets[seat] + stacks[seat]
        minimum = min(maximum, current + increment if current else 2)
        if kind == "call":
            assert amount == call and call > 0
        elif kind == "check":
            assert call == 0 and amount == 0
        elif kind == "fold":
            assert amount == 0
        elif kind == "raise":
            assert minimum <= amount <= maximum and amount > current
        else:
            raise ValueError(f"unknown action {kind}")
        if seat == hero:
            live = [i for i in range(n) if i not in folded]
            opponents = [i for i in live if i != hero]
            closes = all(stacks[i] == 0 or (bets[i] == current and i in acted) for i in opponents)
            remaining_bettors = sum(stacks[i] > (call if i == hero else 0) for i in live)
            terminal = closes and (street == "river" or remaining_bettors <= 1)
            ids = tuple(_parse_card(c) for c in holes[TARGET] + board)
            made = _evaluate(ids) if board else None
            rank = "23456789TJQKA"
            own_pair = holes[TARGET][0][0] == holes[TARGET][1][0] or any(c[0] == b[0] for c in holes[TARGET] for b in board)
            top_pair = bool(board) and any(c[0] == max((b[0] for b in board), key=rank.index) for c in holes[TARGET])
            row = dict(id=f"{meta['id']}:{end['hand']}:{action_index}", match=meta["id"], hand=end["hand"],
                       action_index=action_index, street=street, action=kind, amount=amount,
                       seat=hero, seats=seats, n=n, hole=holes[TARGET], board=list(board), all_holes=holes,
                       pot=total, call=call, pot_odds=call / (total + call) if call else 0,
                       bets=list(bets), contributions=list(contributions), stacks=list(stacks),
                       live=live, opponents=opponents, closes_betting=closes, terminal_call=terminal,
                       pre_raises=pre_raises, history=list(history), invested=contributions[hero],
                       made_category=CATEGORIES[made[0]] if made else "preflop", own_pair=own_pair,
                       top_pair=top_pair, draw=has_any_draw(holes[TARGET], board),
                       hand_chips=end["deltas_by_seat"][hero], match_chips=meta["chips"][names.index(TARGET)],
                       at=meta.get("at"), collected_at=meta.get("collected_at"))
            rows.append(row)
        paid = 0
        raises_before = sum(a["street"] == street and a["action"] == "raise" for a in history)
        size = (amount - current) / max(1, total + call) if kind == "raise" else call / max(1, total - call)
        history.append(dict(street=street, seat=seat, bot=seats[seat], action=kind, amount=amount,
                            board=list(board), pot=total, call=call, size=size,
                            raises_before=raises_before, facing_raise=raises_before > 0))
        acted.add(seat)
        if kind == "fold":
            folded.add(seat)
        elif kind == "call":
            paid = call
        elif kind == "raise":
            paid = amount - bets[seat]
            if amount - current >= increment:
                increment, acted = amount - current, {seat}
            current = amount
            pre_raises += street == "preflop"
        bets[seat] += paid
        stacks[seat] -= paid
        contributions[seat] += paid
        total += paid
        assert total == event["pot"], "pot reconstruction mismatch"
    assert sum(end["deltas_by_seat"]) == 0
    assert all(end["deltas_by_seat"][i] == end["deltas_by_bot"][names.index(name)] for i, name in enumerate(seats))
    # Independently check every showdown pot's winners and final chip returns.
    live = [i for i in range(n) if i not in folded]
    ranks = {i: sdk_evaluate([_parse_card(c) for c in holes[seats[i]] + end["board"]])
             for i in live} if len(live) > 1 else {}
    settled = list(contributions)
    refunds = [0] * n
    largest = max(settled)
    holders = [i for i, amount in enumerate(settled) if amount == largest]
    if len(holders) == 1:
        i = holders[0]
        refunds[i] = largest - max(amount for j, amount in enumerate(settled) if j != i)
        settled[i] -= refunds[i]
    winnings = list(refunds)
    previous, showdown_pots = 0, 0
    expected_pots = []
    levels = sorted(set(settled) - {0}) if len(live) > 1 else [max(settled)]
    for level in levels:
        contributors = [i for i, x in enumerate(settled) if x >= level]
        eligible = [i for i in contributors if i in live]
        value = (level - previous) * len(contributors) if len(live) > 1 else sum(settled)
        if len(live) == 1:
            eligible = live
        previous = level
        assert eligible
        winners = eligible if len(eligible) == 1 else [i for i in eligible if ranks[i] == max(ranks[j] for j in eligible)]
        winners.sort(key=lambda i: (i - 1) % n)
        share, odd = divmod(value, len(winners))
        for j, i in enumerate(winners):
            winnings[i] += share + (j < odd)
        expected_pots.append(dict(amount=value, winners=[seats[i] for i in winners]))
        showdown_pots += len(eligible) > 1
    assert all(winnings[i] - contributions[i] == end['deltas_by_seat'][i] for i in range(n)), 'showdown payout/card mapping mismatch'
    observed_pots = [dict(amount=e['amount'], winners=e['winners']) for e in events if e.get('event') == 'pot']
    assert expected_pots == observed_pots, 'pot winner mismatch'
    hand = dict(match=meta["id"], hand=end["hand"], n=n, seat=hero, hole=holes[TARGET],
                board=end["board"], chips=end["deltas_by_seat"][hero], folded=hero in folded,
                invested=contributions[hero], actions=[r["id"] for r in rows],
                showdown=hero not in folded and len(live) > 1, showdown_pots=showdown_pots,
                at=meta.get("at"), match_chips=meta["chips"][names.index(TARGET)],
                kind=meta["kind"], seats=seats, all_holes=holes, contributions=contributions,
                live=live, log=history)
    return rows, hand


def extract(snapshot, directory, match_ids=None):
    directory.mkdir(parents=True, exist_ok=True)
    metadata_bytes = (snapshot / 'matches.json').read_bytes()
    state_bytes = (snapshot / 'state.json').read_bytes()
    metadata = json.loads(metadata_bytes)
    input_metadata_sha256 = sha256(metadata_bytes).hexdigest()
    selected = None if match_ids is None else set(match_ids)
    if selected is not None:
        eligible = {m['id'] for m in metadata if TARGET in m['names']}
        if not selected or not selected <= eligible:
            raise ValueError('Match selection must contain known Halliday matches')
        metadata = [m for m in metadata if m['id'] in selected]
    target = {m['id'] for m in metadata if TARGET in m['names']}
    metadata_ids = {m['id'] for m in metadata}
    source = snapshot / 'actions.jsonl'
    before = source.stat()
    digest, kinds, all_ids, examples = sha256(), Counter(), set(), {}
    rows = 0
    with source.open('rb') as input_file, (directory / 'halliday-events.jsonl').open('w') as output:
        for line in input_file:
            digest.update(line)
            if not line.strip():
                continue
            event = json.loads(line)
            rows += 1
            mid = event['match']
            all_ids.add(mid)
            if selected is None and TARGET in event.get('holes', {}):
                target.add(mid)
            if mid in target:
                output.write(json.dumps(event, separators=(',', ':')) + '\n')
                kind = event.get('event', 'action')
                kinds[kind] += 1
                examples.setdefault(kind, event)
    after = source.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'source changed during extraction'
    assert metadata_bytes == (snapshot / 'matches.json').read_bytes(), 'metadata changed during extraction'
    assert state_bytes == (snapshot / 'state.json').read_bytes(), 'state changed during extraction'
    copied_metadata = metadata_bytes if selected is None else (json.dumps(metadata, indent=2)+'\n').encode()
    audit = dict(source=str(source), sha256=digest.hexdigest(), size=before.st_size, mtime_ns=before.st_mtime_ns,
                 rows=rows, all_matches=len(all_ids), metadata_target_matches=sum(TARGET in m['names'] for m in metadata),
                 target_matches=len(target & all_ids), missing_target_metadata=sorted((target & all_ids)-metadata_ids),
                 events=dict(kinds), examples=examples, matches_sha256=sha256(copied_metadata).hexdigest(),
                 input_matches_sha256=input_metadata_sha256,
                 state_sha256=sha256(state_bytes).hexdigest(),
                 selection='all observed Halliday matches' if selected is None else 'explicit match IDs',
                 selected_match_ids=None if selected is None else sorted(selected))
    (directory / 'extraction.json').write_text(json.dumps(audit, indent=2))
    (directory / 'matches-snapshot.json').write_bytes(copied_metadata)
    (directory / 'state-snapshot.json').write_bytes(state_bytes)


def prepare(directory):
    meta = {m["id"]: m for m in json.loads((directory / "matches-snapshot.json").read_text())}
    groups = defaultdict(list)
    with (directory / "halliday-events.jsonl").open() as source:
        for line in source:
            event = json.loads(line)
            groups[(event["match"], event["hand"])].append(event)
    rows, hands, errors = [], [], []
    for (mid, hand), events in groups.items():
        try:
            result, summary = reconstruct(events, meta[mid])
            rows.extend(result)
            hands.append(summary)
        except (AssertionError, KeyError, ValueError) as exc:
            errors.append(dict(match=mid, hand=hand, error=str(exc)))
    per_match = defaultdict(list)
    for hand in hands:
        per_match[hand["match"]].append(hand)
    decisions_by_hand = defaultdict(list)
    for row in rows:
        decisions_by_hand[(row['match'], row['hand'])].append(row)
    for mid, group in per_match.items():
        previous_hands = 0
        shoves = Counter()
        for hand in sorted(group, key=lambda h: h['hand']):
            known = {name for name, count in shoves.items() if previous_hands >= 8 and count / previous_hands >= .8}
            for row in decisions_by_hand[(mid, hand['hand'])]:
                row['known_shovers'] = [i for i in row['opponents'] if row['seats'][i] in known]
                row['prior_hands'] = previous_hands
                row['prior_preflop_shoves'] = dict(shoves)
            shoves.update({a['bot'] for a in hand['log'] if a['street'] == 'preflop' and a['action'] == 'raise' and a['amount'] == 200})
            previous_hands += 1
    match_checks = []
    for mid, group in per_match.items():
        observed = sum(h["chips"] for h in group)
        expected = meta[mid]["chips"][meta[mid]["names"].index(TARGET)]
        match_checks.append(dict(match=mid, hands=len(group), reconstructed_chips=observed,
                                 metadata_chips=expected, matches=observed == expected,
                                 contiguous=sorted(h["hand"] for h in group) == list(range(len(group)))))
    audit = dict(hands=len(hands), actions=len(rows), errors=errors,
                 showdown_pots=sum(h["showdown_pots"] for h in hands), matches=match_checks,
                 action_counts=dict(Counter(r["action"] for r in rows)),
                 street_counts=dict(Counter(r["street"] for r in rows)))
    (directory / "decisions.json").write_text(json.dumps(rows))
    (directory / "hands.json").write_text(json.dumps(hands))
    (directory / "reconstruction-audit.json").write_text(json.dumps(audit, indent=2))
    print(json.dumps({k: v for k, v in audit.items() if k != "matches"}, indent=2))
    print("Match discrepancies:", [m for m in match_checks if not m["matches"] or not m["contiguous"]])

# GPU evaluation uses the tested harness kernel with packed ranks, avoiding
# Python tuple conversion for the tens of millions of offline samples.
_GPU = None
_INIT_ERROR = None

def rank_codes(hands):
    import ctypes as C
    gpu = _GPU
    output = np.empty(len(hands), dtype=np.int32)
    for start in range(0, len(hands), gpu.capacity):
        chunk = np.ascontiguousarray(hands[start:start + gpu.capacity], dtype=np.int32)
        assert chunk.shape == (len(chunk), 7) and chunk.min() >= 0 and chunk.max() < 52
        count = C.c_int(len(chunk))
        began = time.perf_counter()
        gpu.driver.call('cuMemcpyHtoD_v2', gpu.cards, chunk.ctypes.data, chunk.nbytes)
        args = (C.c_void_p * 3)(C.addressof(gpu.cards), C.addressof(gpu.ranks), C.addressof(count))
        gpu.driver.call('cuLaunchKernel', gpu.function, (count.value + 127) // 128, 1, 1,
                        128, 1, 1, 0, None, args, None)
        gpu.driver.call('cuMemcpyDtoH_v2', gpu.host_ranks.ctypes.data, gpu.ranks, count.value * 4)
        output[start:start + count.value] = gpu.host_ranks[:count.value]
        gpu.hands += count.value
        gpu.batches += 1
        gpu.seconds += time.perf_counter() - began
    return output


def worker_init(devices):
    global _GPU, _INIT_ERROR
    try:
        from harness.gpu_equity import CudaEvaluator
        _GPU = CudaEvaluator(devices.get(timeout=10), 4096)
        rng = np.random.default_rng(876)
        hands = np.array([rng.choice(52, 7, replace=False) for _ in range(128)], dtype=np.int32)
        assert list(rank_codes(hands)) == [code(_evaluate(tuple(map(int, h)))) for h in hands]
    except Exception as exc:
        _INIT_ERROR = f'{type(exc).__name__}: {exc}'


def rng_for(identifier):
    return np.random.default_rng(int.from_bytes(sha256(identifier.encode()).digest()[:8], 'big'))


def rank_deals(holes, boards, live, n):
    # holes has axes [sample, live player, hole card].
    seven = np.concatenate((holes, np.broadcast_to(boards[:, None, :], (len(boards), len(live), 5))), axis=2)
    result = np.zeros((len(boards), n), dtype=np.int32)
    result[:, live] = rank_codes(seven.reshape(-1, 7)).reshape(len(boards), len(live))
    return result


def oracle_ranks(row, cache):
    key = (tuple(row['board']), tuple(row['live']))
    if key in cache:
        return cache[key]
    board = [_parse_card(c) for c in row['board']]
    holes = [[_parse_card(c) for c in row['all_holes'][name]] for name in row['seats']]
    known = {c for h in holes for c in h} | set(board)
    deck = np.array([i for i in range(52) if i not in known], dtype=np.int32)
    missing = 5 - len(board)
    if missing <= 2:
        runouts = np.array(list(combinations(deck, missing)), dtype=np.int32).reshape(-1, missing) if missing else np.empty((1, 0), dtype=np.int32)
        exact = True
    else:
        rng = rng_for(row['id'] + ':oracle')
        keys = rng.random((4096, len(deck)))
        runouts = deck[np.argpartition(keys, missing - 1, axis=1)[:, :missing]]
        exact = False
    boards = np.concatenate((np.broadcast_to(board, (len(runouts), len(board))), runouts), axis=1)
    live_holes = np.array([holes[i] for i in row['live']], dtype=np.int32)
    rankings = rank_deals(np.broadcast_to(live_holes, (len(boards), len(live_holes), 2)), boards, row['live'], row['n'])
    cache[key] = (rankings, exact)
    return rankings, exact


def projected_contributions(row):
    # Diagnostic assumption: all currently live players match the current bet
    # if able, then check down. Exact for a terminal call, a proxy otherwise.
    contributions = list(row['contributions'])
    current = max(row['bets'])
    for i in row['live']:
        contributions[i] += min(row['stacks'][i], current - row['bets'][i])
    return contributions


def payoff_summary(rankings, row, exact=False):
    contribution = projected_contributions(row)
    returns = payout(rankings, contribution, row['live'], row['seat'])
    values = rankings[:, row['live']]
    best = values.max(axis=1)
    shares = (rankings[:, row['seat']] == best) / (values == best[:, None]).sum(axis=1)
    ev = returns - row['call']
    se = float(np.std(ev, ddof=1) / math.sqrt(len(ev))) if not exact and len(ev) > 1 else 0.0
    return dict(equity=float(np.mean(shares)), call_ev=float(np.mean(ev)), ev_se=se,
                samples=len(ev), exact=exact, eligible_pot=sum(a for a, _ in pots(contribution, row['live'], row['seat'])))


def public_ranks(row, model):
    from bot.ranges import (N, COMBO_IDS, COMBO_MASKS, PREFLOP_PCT, preflop_likelihood,
                            postflop_likelihood, board_strength)
    from bot.params import DEFAULT_PARAMS
    p = dict(DEFAULT_PARAMS)
    # Two explicit sensitivity models; no hidden cards, future actions,
    # future boards, or fits to this same sample enter either range.
    widths = (.22, .12, .05) if model == 'tight' else (.45, .30, .14)
    learned = (.75, .50, .10) if model == 'tight' else (.55, .30, .30)
    board = [_parse_card(c) for c in row['board']]
    hero = [_parse_card(c) for c in row['hole']]
    fixed = board + hero
    fixed_mask = sum(1 << c for c in fixed)
    masks = np.asarray(COMBO_MASKS, dtype=np.uint64)
    combos = np.asarray(COMBO_IDS, dtype=np.int32)
    probabilities = {}
    for seat in row['opponents']:
        weights = np.ones(N)
        proven_shove = seat in row.get('known_shovers', []) and any(a['seat'] == seat and a['street'] == 'preflop' and a['action'] == 'raise' and a['amount'] == 200 for a in row['history'])
        for action in row['history']:
            if proven_shove and action['street'] == 'preflop':
                continue  # Public prior: this player shoved at least 80% of 8+ previous hands.

            if action['seat'] != seat or action['action'] == 'fold':
                continue
            if action['street'] == 'preflop':
                likelihood = preflop_likelihood(action['action'], PREFLOP_PCT[0 if row['n'] <= 3 else 1], action['raises_before'], widths, p)
            else:
                made, draws = board_strength(action['board'])
                strength = np.minimum(1, np.nan_to_num(made, nan=.5) + p['range_draw_bonus'] * draws)
                likelihood = postflop_likelihood(action['action'], strength, action['size'], action['facing_raise'], learned, p)
            weights *= np.asarray(likelihood) ** p['range_temper']
        weights[(masks & fixed_mask) != 0] = 0
        probabilities[seat] = weights / weights.sum()
    rng = rng_for(row['id'] + ':' + model)
    total = 8192 if row['terminal_call'] else 4096
    collected, count, attempts = [], 0, 0
    while count < total:
        size = min(8192, max(512, (total - count) * 2))
        used = np.full(size, fixed_mask, dtype=np.uint64)
        valid = np.ones(size, dtype=bool)
        chosen = {}
        for seat in row['opponents']:
            indices = rng.choice(N, size, p=probabilities[seat])
            bits = masks[indices]
            valid &= (used & bits) == 0
            used |= bits
            chosen[seat] = combos[indices]
        accepted = np.flatnonzero(valid)[:total-count]
        hands = np.empty((len(accepted), len(row['live']), 2), dtype=np.int32)
        for j, seat in enumerate(row['live']):
            hands[:, j] = hero if seat == row['seat'] else chosen[seat][accepted]
        if len(hands):
            collected.append(hands)
            count += len(hands)
        attempts += size
        if attempts > total * 1000:
            raise RuntimeError('public range rejection limit exceeded')
    hands = np.concatenate(collected)
    missing = 5 - len(board)
    if missing:
        keys = rng.random((total, 52))
        keys[:, board] = np.inf
        for j in range(len(row['live'])):
            keys[np.arange(total), hands[:, j, 0]] = np.inf
            keys[np.arange(total), hands[:, j, 1]] = np.inf
        runouts = np.argpartition(keys, missing-1, axis=1)[:, :missing]
    else:
        runouts = np.empty((total, 0), dtype=np.int32)
    boards = np.concatenate((np.broadcast_to(board, (total, len(board))), runouts), axis=1)
    return rank_deals(hands, boards, row['live'], row['n'])


def analyse_match(job):
    if _INIT_ERROR:
        raise RuntimeError(_INIT_ERROR)
    rows, hands = job
    before = _GPU.metadata()
    caches = defaultdict(dict)
    by_hand = {h['hand']: h for h in hands}
    results = []
    for row in rows:
        if len(caches) > 1:
            caches = defaultdict(dict, {row['hand']: caches[row['hand']]})
        rankings, exact = oracle_ranks(row, caches[row['hand']])
        row['oracle'] = payoff_summary(rankings, row, exact)
        row['public'] = {}
        if row['call'] > 0 and (row['terminal_call'] or (row['street'] != 'preflop' and len(row['opponents']) == 1)):
            for model in ('tight', 'loose'):
                row['public'][model] = payoff_summary(public_ranks(row, model), row)
        final = by_hand[row['hand']]['board']
        row['hindsight_final_equity'] = None
        if len(final) == 5:
            values = {i: _evaluate(tuple(_parse_card(c) for c in row['all_holes'][row['seats'][i]] + final)) for i in row['live']}
            best = max(values.values())
            row['hindsight_final_equity'] = (values[row['seat']] == best) / sum(v == best for v in values.values())
        row['guaranteed_profitable_call'] = False
        if row['street'] == 'river' and row['terminal_call'] and row['call']:
            blocked = {_parse_card(c) for c in row['hole'] + row['board']}
            board_ids = tuple(_parse_card(c) for c in row['board'])
            all_combos = [h for h in combinations((i for i in range(52) if i not in blocked), 2)]
            all_ranks = rank_codes(np.array([h + board_ids for h in all_combos], dtype=np.int32))
            hero_rank = code(_evaluate(tuple(_parse_card(c) for c in row['hole']) + board_ids))
            if hero_rank >= max(all_ranks):
                worst = payout(np.ones((1, row['n'])), projected_contributions(row), row['live'], row['seat'])[0] - row['call']
                row['guaranteed_profitable_call'] = bool(worst > 0)
        results.append(row)
    # All-in runouts: after the last action, betting is over with cards still
    # to come. Compare realized hand chips with full-information runout EV.
    for hand in hands:
        hand['allin_runout'] = None
        if hand['showdown'] and len(hand['log'][-1]['board']) < 5:
            checkpoint = dict(id=f"{hand['match']}:{hand['hand']}:settlement", board=hand['log'][-1]['board'],
                              live=hand['live'], all_holes=hand['all_holes'], seats=hand['seats'], n=hand['n'])
            ranks, exact = oracle_ranks(checkpoint, {})
            returns = payout(ranks, hand['contributions'], hand['live'], hand['seat'])
            expected = float(returns.mean()) - hand['contributions'][hand['seat']]
            ev_se = float(returns.std(ddof=1)/math.sqrt(len(returns))) if not exact and len(returns)>1 else 0.0
            values = ranks[:, hand['live']]
            best = values.max(axis=1)
            share = (ranks[:, hand['seat']] == best) / (values == best[:, None]).sum(axis=1)
            hand['allin_runout'] = dict(expected_chips=expected, realized_chips=hand['chips'],
                                      luck=hand['chips']-expected, equity=float(share.mean()),
                                      board=checkpoint['board'], samples=len(ranks), exact=exact, ev_se=ev_se)
    after = _GPU.metadata()
    for key in ('batches', 'ranked_hands', 'gpu_seconds'):
        after[key] -= before[key]
    return results, hands, after


def compute(directory, devices):
    audit = json.loads((directory / 'reconstruction-audit.json').read_text())
    if audit['errors'] or any(not m['matches'] or not m['contiguous'] for m in audit['matches']):
        raise ValueError('Replay reconstruction failed; inspect reconstruction-audit.json before scoring')
    if not devices or len(devices) != len(set(devices)):
        raise ValueError('Choose one distinct CUDA device per worker')
    rows = json.loads((directory / 'decisions.json').read_text())
    hands = json.loads((directory / 'hands.json').read_text())
    by_match, hands_by_match = defaultdict(list), defaultdict(list)
    for row in rows:
        by_match[row['match']].append(row)
    for hand in hands:
        hands_by_match[hand['match']].append(hand)
    context = mp.get_context('spawn')
    queue = context.Queue()
    for device in devices:
        queue.put(device)
    output_rows, output_hands, usage = [], [], []
    began = time.monotonic()
    with context.Pool(len(devices), initializer=worker_init, initargs=(queue,)) as pool:
        jobs = [(group, hands_by_match[mid]) for mid, group in by_match.items()]
        for i, (group, result_hands, gpu) in enumerate(pool.imap_unordered(analyse_match, jobs), 1):
            output_rows.extend(group)
            output_hands.extend(result_hands)
            usage.append(gpu)
            print(f'{i}/{len(jobs)} matches; {len(output_rows)} decisions; {time.monotonic()-began:.1f}s', flush=True)
    queue.close()
    (directory / 'scored-decisions.json').write_text(json.dumps(output_rows))
    (directory / 'scored-hands.json').write_text(json.dumps(output_hands))
    (directory / 'gpu-work.json').write_text(json.dumps(usage, indent=2))
    (directory / 'compute-run.json').write_text(json.dumps(dict(
        devices=devices, workers=len(devices), wall_seconds=time.monotonic()-began,
        matches=len(jobs), decisions=len(output_rows), hands=len(output_hands),
        ranked_hands=sum(x['ranked_hands'] for x in usage),
    ), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('step', choices=['extract', 'prepare', 'compute'])
    parser.add_argument('--directory', type=Path, default=ROOT / 'analysis/results/halliday-performance-20261004')
    parser.add_argument('--devices', default='0,1,2,3')
    parser.add_argument('--snapshot', type=Path, default=ROOT / 'analysis/results/input-snapshot')
    parser.add_argument('--match-ids', type=Path, help='JSON list of Halliday matches, e.g. its newest observed segment')
    args = parser.parse_args()
    if args.step == 'extract':
        extract(args.snapshot, args.directory,
                json.loads(args.match_ids.read_text()) if args.match_ids else None)
    elif args.step == 'prepare':
        prepare(args.directory)
    else:
        compute(args.directory, [int(d) for d in args.devices.split(',')])
