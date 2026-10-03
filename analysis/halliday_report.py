"""Classify the replay audit without treating hidden cards as playable information."""
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
DIR = ROOT / 'analysis/results/halliday-performance-20261004'
BLUNDERS = {'certain_avoidable_fold', 'probable_missed_terminal_call', 'probable_bad_terminal_call'}


def timestamp_ms(value):
    return value if value > 1e11 else value * 1000


def classify(row, hand):
    from analysis.halliday_performance import has_any_draw
    if 'hole' in row and 'board' in row:
        row['draw'] = has_any_draw(row['hole'], row['board'])
    tags = []
    kind = row['action']
    oracle = row['oracle']
    oracle_low = oracle['call_ev'] - 1.96 * oracle['ev_se']
    oracle_high = oracle['call_ev'] + 1.96 * oracle['ev_se']
    public = list(row['public'].values())
    low = min((v['call_ev'] - 1.96*v['ev_se'] for v in public), default=-math.inf)
    high = max((v['call_ev'] + 1.96*v['ev_se'] for v in public), default=math.inf)
    if kind == 'fold' and oracle_low > 0:
        tags.append('positive_hidden_card_checkdown_ev')
    if kind == 'fold' and row['terminal_call'] and oracle_low > 0:
        tags.append('hindsight_profitable_terminal_call')
    if kind == 'fold' and row['hindsight_final_equity'] and row['hindsight_final_equity'] > 0:
        tags.append('would_share_recorded_final_board_against_then_live_hands')
    if kind == 'call' and row['terminal_call'] and oracle_high < 0:
        tags.append('hindsight_negative_terminal_call')
    if kind == 'raise' and row['street'] != 'preflop':
        response = []
        for action in hand['log'][row['action_index']:]:
            if action['street'] != row['street']:
                break
            if action['seat'] != row['seat']:
                response.append(action['action'])
        answered = any(a in ('call', 'raise') for a in response)
        if not row['own_pair'] and row['made_category'] == 'high card':
            tags.append('semibluff' if row['draw'] else 'air_bet')
            if answered:
                tags.append('bluff_answered')
            if answered and row['hand_chips'] < 0:
                tags.append('failed_semibluff' if row['draw'] else 'failed_air_bet')
        later = [a for a in hand['log'][row['action_index']:] if a['seat'] == row['seat']]
        if any(a['action'] == 'fold' for a in later):
            tags.append('bet_then_fold')
    reason = 'No error established by this audit; this is not a certificate of optimal play.'
    label = kind + '_not_flagged'
    if kind == 'fold' and (row['call'] == 0 or row['guaranteed_profitable_call']):
        label, reason = 'certain_avoidable_fold', 'A free check or guaranteed profitable terminal call was available.'
    elif kind == 'fold' and row['terminal_call'] and low > 2:
        label, reason = 'probable_missed_terminal_call', 'Both public-range models give call EV above +2 chips after their 95% Monte Carlo margin; no future betting is required.'
    elif kind == 'call' and row['terminal_call'] and high < -2:
        label, reason = 'probable_bad_terminal_call', 'Both public-range models give call EV below -2 chips after their 95% Monte Carlo margin; folding would end further investment.'
    elif kind == 'fold' and not row['terminal_call'] and low > max(2, .1 * row['pot']):
        label, reason = 'possible_nonterminal_overfold', 'Both public-range models favor a checkdown call by a substantial margin, but future betting is not modeled.'
    elif kind == 'call' and not row['terminal_call'] and high < -max(2, .1 * row['call']):
        label, reason = 'possible_nonterminal_bad_call', 'Both public-range models give negative checkdown call EV; implied odds and future actions could change this.'
    elif 'failed_air_bet' in tags:
        label, reason = 'failed_air_bet', 'A bet with no made pair or draw was answered and the hand lost chips. A failed bluff is not automatically a mistake.'
    elif 'failed_semibluff' in tags:
        label, reason = 'failed_semibluff', 'A draw was bet, the bet was answered, and the hand lost chips; this can be a sound play with a bad result.'
    elif 'hindsight_profitable_terminal_call' in tags:
        label, reason = 'hindsight_missed_call_only', 'Calling was profitable against the actual hidden cards, but the public-range checks do not establish an error.'
    elif 'hindsight_negative_terminal_call' in tags:
        label, reason = 'hindsight_losing_call_only', 'Calling lost expectation against actual hidden cards, but the public-range checks do not establish an error.'
    row.update(classification=label, tags=tags, reason=reason,
               public_ev_lower=low if public else None, public_ev_upper=high if public else None)


def classify_hand(hand, rows):
    if hand['chips'] >= 0:
        return 'non_losing_hand'
    if any(r['classification'] == 'probable_bad_terminal_call' for r in rows):
        return 'probable_bad_terminal_call'
    if any(r['classification'] in ('certain_avoidable_fold','probable_missed_terminal_call') for r in rows):
        return 'probable_missed_terminal_call'
    if hand['allin_runout'] and hand['allin_runout']['expected_chips'] > 0:
        return 'profitable_allin_lost_runout'
    if any('failed_air_bet' in r['tags'] for r in rows):
        return 'failed_air_bet_hand'
    if any('failed_semibluff' in r['tags'] for r in rows):
        return 'failed_semibluff_hand'
    if hand['folded']:
        last = rows[-1]
        if last['street'] == 'preflop':
            return 'blind_only_fold' if hand['invested'] <= 2 else 'preflop_invest_then_fold'
        return 'postflop_invest_then_fold'
    if hand['allin_runout']:
        return 'other_losing_allin'
    return 'other_showdown_loss'


def write_csv(path, fields, rows):
    with path.open('w', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(row[k], separators=(',', ':')) if isinstance(row.get(k),(list,dict)) else row.get(k) for k in fields})


def build(directory=DIR):
    rows = json.loads((directory/'scored-decisions.json').read_text())
    hands = json.loads((directory/'scored-hands.json').read_text())
    meta = {m['id']:m for m in json.loads((directory/'matches-snapshot.json').read_text())}
    hands_by_id = {(h['match'],h['hand']):h for h in hands}
    for row in rows:
        classify(row, hands_by_id[(row['match'],row['hand'])])
    by_hand, by_match, actions_by_match = defaultdict(list),defaultdict(list),defaultdict(list)
    for row in rows:
        by_hand[(row['match'],row['hand'])].append(row)
        actions_by_match[row['match']].append(row)
    for hand in hands:
        group = sorted(by_hand[(hand['match'],hand['hand'])],key=lambda r:r['action_index'])
        hand['loss_category'] = classify_hand(hand,group)
        by_match[hand['match']].append(hand)
    matches=[]
    for mid, group in by_match.items():
        actions=actions_by_match[mid]
        cats=defaultdict(lambda:dict(hands=0,chips=0))
        for h in group:
            cats[h['loss_category']]['hands']+=1
            cats[h['loss_category']]['chips']+=h['chips']
        flags=[r for r in actions if r['classification'] in BLUNDERS]
        bad_calls=[r for r in flags if r['classification']=='probable_bad_terminal_call']
        runouts=[h['allin_runout'] for h in group if h['allin_runout']]
        matches.append(dict(match=mid,at=meta[mid]['at'],kind=meta[mid]['kind'],opponents=[n for n in meta[mid]['names'] if n!='Halliday'],
                            hands=len(group),chips=sum(h['chips'] for h in group),folds=sum(h['folded'] for h in group),
                            flags=len(flags),flagged_actions=[r['id'] for r in flags],loss_categories=dict(cats),
                            bad_calls=len(bad_calls),missed_calls=sum(r['classification']=='probable_missed_terminal_call' for r in flags),
                            terminal_call_fold_saving=-sum(r['hand_chips']+r['invested'] for r in bad_calls),
                            allin_count=len(runouts),allin_luck=sum(x['luck'] for x in runouts),
                            allin_expected=sum(x['expected_chips'] for x in runouts),allin_actual=sum(x['realized_chips'] for x in runouts),
                            worst_hands=[dict(hand=h['hand'],chips=h['chips'],hole=h['hole'],board=h['board'],loss_category=h['loss_category']) for h in sorted(group,key=lambda h:h['chips'])[:5]]))
    ladder_ids={m['match'] for m in matches if m['kind']=='ladder'}
    ladder_h=[h for h in hands if h['match'] in ladder_ids]
    ladder_a=[r for r in rows if r['match'] in ladder_ids]
    ladder_m=[m for m in matches if m['kind']=='ladder']
    folds=[r for r in ladder_a if r['action']=='fold']
    calls=[r for r in ladder_a if r['action']=='call']
    loss_ids={m['match'] for m in ladder_m if m['chips']<0}
    loss_h=[h for h in ladder_h if h['match'] in loss_ids]
    per_street={}
    for street in ('preflop','flop','turn','river'):
        group=[r for r in ladder_a if r['street']==street]
        per_street[street]=dict(actions=len(group),faced_bet=sum(r['call']>0 for r in group),**dict(Counter(r['action'] for r in group)))
    losses=defaultdict(lambda:dict(hands=0,chips=0))
    for h in loss_h:
        losses[h['loss_category']]['hands']+=1
        losses[h['loss_category']]['chips']+=h['chips']
    estimates=[m['chips'] for m in ladder_m]
    timing=sorted(ladder_m,key=lambda m:(timestamp_ms(m['at']),m['match']))
    periods=[]
    for indices in np_array_split(list(range(len(timing))),4):
        group=[timing[i] for i in indices]
        if not group:
            continue
        group_ids={m['match'] for m in group}
        act=[r for r in ladder_a if r['match'] in group_ids]
        periods.append(dict(matches=len(group),hands=sum(m['hands'] for m in group),chips=sum(m['chips'] for m in group),
                            from_at=group[0]['at'],to_at=group[-1]['at'],folds=sum(r['action']=='fold' for r in act),
                            blunders=sum(r['classification'] in BLUNDERS for r in act)))
    last_20={m['match'] for m in timing[-20:]}
    summary=dict(matches=len(ladder_m),hands=len(ladder_h),actions=len(ladder_a),chips=sum(estimates),
                 losing_matches=len(loss_ids),winning_matches=sum(v>0 for v in estimates),
                 match_mean_ci=[statistics.mean(estimates),1.96*statistics.stdev(estimates)/math.sqrt(len(estimates))],
                 folds=len(folds),facing_decisions=sum(r['call']>0 for r in ladder_a),streets=per_street,
                 classifications=dict(Counter(r['classification'] for r in ladder_a)),
                 fold_tags=dict(Counter(t for r in folds for t in r['tags'])),
                 terminal_folds=sum(r['terminal_call'] for r in folds),terminal_calls=sum(r['terminal_call'] for r in calls),
                 terminal_folds_by_street=dict(Counter(r['street'] for r in folds if r['terminal_call'])),
                 public_scored=sum(bool(r['public']) for r in ladder_a),
                 losses_in_negative_matches=dict(losses),negative_match_net=sum(m['chips'] for m in ladder_m if m['chips']<0),
                 allin_runouts=[h['allin_runout'] for h in ladder_h if h['allin_runout']],periods=periods,
                 latest_20=dict(matches=len(last_20),hands=sum(m['hands'] for m in timing[-20:]),chips=sum(m['chips'] for m in timing[-20:]),folds=sum(r['action']=='fold' for r in ladder_a if r['match'] in last_20),
                                classifications=dict(Counter(r['classification'] for r in ladder_a if r['match'] in last_20))))
    (directory/'summary.json').write_text(json.dumps(summary,indent=2))
    (directory/'classified-actions.json').write_text(json.dumps(rows))
    (directory/'classified-hands.json').write_text(json.dumps(hands))
    (directory/'match-reviews.json').write_text(json.dumps(sorted(matches,key=lambda m:m['chips']),indent=2))
    flat=[]
    for r in sorted(rows,key=lambda r:(timestamp_ms(r['at']),r['match'],r['hand'],r['action_index'])):
        flat.append(dict(id=r['id'],match=r['match'],hand=r['hand'],street=r['street'],action=r['action'],amount=r['amount'],hole=' '.join(r['hole']),board=' '.join(r['board']),
                         pot=r['pot'],call=r['call'],pot_odds=r['pot_odds'],terminal_call=r['terminal_call'],
                         oracle_equity=r['oracle']['equity'],oracle_call_ev=r['oracle']['call_ev'],oracle_ev_se=r['oracle']['ev_se'],
                         tight_call_ev=r['public'].get('tight',{}).get('call_ev'),loose_call_ev=r['public'].get('loose',{}).get('call_ev'),
                         public_ev_lower=r['public_ev_lower'],public_ev_upper=r['public_ev_upper'],
                         retrospective_fold_saving=-(r['hand_chips']+r['invested']) if r['action']=='call' and r['terminal_call'] else None,
                         hand_chips=r['hand_chips'],match_chips=r['match_chips'],classification=r['classification'],tags=r['tags'],reason=r['reason']))
    write_csv(directory/'action-classifications.csv',list(flat[0]),flat)
    write_csv(directory/'blunders.csv',list(flat[0]),[r for r in flat if r['classification'] in BLUNDERS])
    write_csv(directory/'match-reviews.csv',['match','kind','hands','chips','folds','flags','bad_calls','missed_calls','terminal_call_fold_saving','allin_count','allin_luck','allin_expected','allin_actual','flagged_actions','loss_categories','worst_hands'],sorted(matches,key=lambda m:m['chips']))
    write_csv(directory/'hand-outcomes.csv',['match','hand','kind','chips','hole','board','folded','showdown','invested','loss_category','allin_runout'],hands)
    print(json.dumps({k:v for k,v in summary.items() if k!='allin_runouts'},indent=2))
    flags=[r for r in ladder_a if r['classification'] in BLUNDERS]
    print('FLAGGED DECISIONS',json.dumps([{k:r[k] for k in ('id','street','action','hole','board','pot','call','oracle','public','hand_chips','classification')} for r in flags],indent=2))


def np_array_split(values,n):
    size,extra=divmod(len(values),n)
    at=0
    for i in range(n):
        length=size+(i<extra)
        yield values[at:at+length]
        at+=length


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,default=DIR)
    args=parser.parse_args()
    build(args.directory)
