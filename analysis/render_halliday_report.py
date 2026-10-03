"""Render fingerprinted replay findings without carrying over snapshot-specific prose."""
from collections import Counter, defaultdict
from datetime import datetime
import html
import json
from pathlib import Path
import re
import shlex
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.halliday_report import BLUNDERS, DIR, timestamp_ms

OUT = ROOT / 'analysis/reports'
TITLES = {
    'non_losing_hand': 'Winning / break-even hands',
    'blind_only_fold': 'Blind-only folds',
    'preflop_invest_then_fold': 'Preflop investment, then fold',
    'postflop_invest_then_fold': 'Postflop investment, then fold',
    'probable_bad_terminal_call': 'Probable bad terminal call',
    'probable_missed_terminal_call': 'Probable missed terminal call',
    'profitable_allin_lost_runout': 'Positive-EV all-in, lost runout',
    'other_losing_allin': 'Other all-in losses; decision quality unresolved',
    'other_showdown_loss': 'Other showdown losses; decision quality unresolved',
    'failed_air_bet_hand': 'Failed high-card bluff hands',
    'failed_semibluff_hand': 'Failed semibluff hands',
}


def pct(n, d):
    return f'{100*n/d:.2f}%' if d else 'N/A'


def stamp(value):
    return datetime.fromtimestamp(timestamp_ms(value)/1000, ZoneInfo('Australia/Melbourne')).strftime('%d %b %H:%M:%S')


def render(directory=DIR, out=OUT):
    def read(name):
        return json.loads((directory / name).read_text())
    s = read('summary.json')
    all_a, all_h, all_m = read('classified-actions.json'), read('classified-hands.json'), read('match-reviews.json')
    extraction, audit, gpu = read('extraction.json'), read('reconstruction-audit.json'), read('gpu-work.json')
    run = read('compute-run.json') if (directory/'compute-run.json').exists() else {}
    verification = read('verification.json') if (directory/'verification.json').exists() else {}
    metadata = read('matches-snapshot.json')
    matches = sorted((x for x in all_m if x['kind']=='ladder'), key=lambda x: (timestamp_ms(x['at']), x['match']))
    ids = {x['match'] for x in matches}
    actions = [x for x in all_a if x['match'] in ids]
    hands = [x for x in all_h if x['match'] in ids]
    by_hand, by_match = defaultdict(list), defaultdict(list)
    for row in actions:
        by_hand[(row['match'], row['hand'])].append(row)
        by_match[row['match']].append(row)
    hand_map = {(x['match'], x['hand']): x for x in hands}
    calls = [r for r in actions if r['classification']=='probable_bad_terminal_call']
    missed = [r for r in actions if r['classification']=='probable_missed_terminal_call']
    folds = [r for r in actions if r['action']=='fold']
    terminal_folds = [r for r in folds if r['terminal_call']]
    oracle_folds = [r for r in terminal_folds if 'hindsight_profitable_terminal_call' in r['tags']]
    both_folds = [r for r in missed if 'hindsight_profitable_terminal_call' in r['tags']]
    rivers = [r for r in calls if r['street']=='river']
    runouts = [h['allin_runout'] for h in hands if h['allin_runout']]
    gain = -sum(r['hand_chips']+r['invested'] for r in calls)
    river_gain = -sum(r['hand_chips']+r['invested'] for r in rivers)
    negative = sorted((m for m in matches if m['chips']<0), key=lambda m:m['chips'])
    certain = [r for r in actions if r['classification']=='certain_avoidable_fold']
    last = s['latest_20']
    last_flags = sum(last['classifications'].get(k, 0) for k in BLUNDERS)
    blocks = []
    def p(value): blocks.append(('p', value))
    def head(value): blocks.append(('h2', value))
    def sub(value): blocks.append(('h3', value))
    def table(headers, rows): blocks.append(('table', (headers, list(rows))))
    def card_text(cards): return ' '.join(cards) or '(preflop)'
    date_part = directory.name.removeprefix('halliday-performance-')
    try:
        date_label = datetime.strptime(date_part, '%Y%m%d').strftime('%d %B %Y')
    except ValueError:
        date_label = directory.name
    blocks.append(('h1', f'Halliday performance and decision audit — {date_label}'))
    p(f"Source: `{extraction['source']}`, SHA-256 `{extraction['sha256']}`. The recorded name is `Halliday`. "
      f"Main results cover {s['matches']} ladder matches, {s['hands']:,} hands, and {s['actions']:,} decisions. "
      f"These are eight-seat, 200-chip-per-hand games with a two-chip big blind. Recorded match times span "
      f"{stamp(matches[0]['at'])}–{stamp(matches[-1]['at'])}, Australia/Melbourne. Hand numbers are zero-based.")
    head('Main findings')
    p(f"Halliday lost {abs(s['chips']):,} chips overall ({s['chips']/2/s['hands']*100:+.2f} big blinds per 100 hands). "
      f"It folded {s['folds']:,} times ({pct(s['folds'],s['hands'])} of hands). "
      f"The strongest decision-review finding is expensive calling: {len(calls)} terminal calls were negative under both public-information range models, including {len(rivers)} on the river. "
      f"Folding instead at those selected decisions would have improved the recorded outcomes by {gain:,} chips. This is a retrospective comparison within the same hands, not a predicted gain on new games.")
    p(f"There were {len(missed)} model-supported missed-call flags ({pct(len(missed),len(folds))} of folds), of which {len(both_folds)} also had positive call expectation against the actual hidden hands. "
      f"The audit found {len(certain)} provably avoidable folds. Most folds leave future betting unresolved, so these figures do not establish the true unnecessary-fold rate. They do not support indiscriminately widening the bot's range.")
    p(f"Losses also reflect unlucky runouts: {len(runouts)} auditable all-in hands returned {sum(x['realized_chips'] for x in runouts):+,.0f} chips against "
      f"{sum(x['expected_chips'] for x in runouts):+,.1f} expected with the recorded hands, a {sum(x['luck'] for x in runouts):+,.1f}-chip difference. "
      "This isolates cards dealt after betting ended. It does not certify the earlier decisions or provide a complete skill-adjusted win rate.")
    p(f"Recency matters: the latest {last['matches']} ladder games returned {last['chips']:+,} chips over {last['hands']:,} hands and contain {last_flags} terminal call/fold flags under this method. "
      "The strongest calling-leak examples therefore describe earlier observed play. Changes in opponents, cards and possible same-name bot replacements prevent attributing that difference to a specific code update.")
    table(['Metric', 'Ladder result'], [
        ['Matches / hands / actions', f"{s['matches']} / {s['hands']:,} / {s['actions']:,}"],
        ['Net chips / bb per 100 hands', f"{s['chips']:+,} / {s['chips']/2/s['hands']*100:+.2f}"],
        ['Positive / negative games', f"{s['winning_matches']} / {s['losing_matches']}"],
        ['Mean chips/game, approximate 95% interval', f"{s['match_mean_ci'][0]:+.2f} ± {s['match_mean_ci'][1]:.2f}"],
        ['Latest 20 games: net chips / bb per 100 hands', f"{last['chips']:+,} / {last['chips']/2/last['hands']*100:+.2f}"],
    ])
    p('The interval treats matches as independent observations. Shared opponents, related deals and bot changes weaken that assumption. No version hash or decision-time equity/range/clock trace is recorded, so these findings cannot be attributed to the current source branch.')

    head('How often does it fold?')
    pre = s['streets']['preflop'].get('fold', 0)
    facing_folds = sum(r['call']>0 for r in folds)
    p(f"Halliday folded in {s['folds']:,}/{s['hands']:,} hands ({pct(s['folds'],s['hands'])}): {pre:,} preflop ({pct(pre,s['hands'])} of all hands), and {s['folds']-pre:,} postflop. "
      f"Folds were {pct(s['folds'],s['actions'])} of all actions and {pct(facing_folds,s['facing_decisions'])} of decisions facing a positive call price. A hand can have several decisions but at most one Halliday fold.")
    table(['Street', 'Folds', 'Decisions facing a bet', 'Fold rate facing a bet', 'Calls', 'Raises / opening bets'], [
        [street.title(), f"{v.get('fold',0):,}", f"{v['faced_bet']:,}",
         pct(sum(r['street']==street and r['call']>0 for r in folds), v['faced_bet']), f"{v.get('call',0):,}", f"{v.get('raise',0):,}"]
        for street, v in s['streets'].items()
    ])
    aa_folds = sum(r['street']=='preflop' and all(c[0]=='A' for c in r['hole']) for r in folds)
    deciles = []
    for start in range(0,100,10):
        group = [h for h in hands if start<=h['hand']<start+10]
        deciles.append((f'{start}–{start+9}',len(group),sum(h['folded'] for h in group)))
    rates = [n/d for _,d,n in deciles if d]
    p(f"There were {aa_folds} preflop folds of pocket aces. Across ten-hand blocks within games, all-street fold rates ranged from {100*min(rates):.2f}% to {100*max(rates):.2f}%. "
      "There is no obvious late-game jump to universal folding in these aggregate counts. Timing and verdict records would be needed to diagnose a time-bank fallback.")

    head('How often were folds unnecessary?')
    p('A terminal call closes the river betting, or closes betting with at most one live player retaining chips. These opportunities allow a direct call-versus-fold comparison without assuming later betting behavior. Side pots, dead money, stack caps and sunk investments are included.')
    table(['Evidence', 'Count', 'Meaning'], [
        ['Provably avoidable fold', len(certain), 'A free check or a guaranteed profitable terminal call was available.'],
        ['Probable missed terminal call under both public-range models', len(missed), f"{pct(len(missed),len(folds))} of all folds; {pct(len(missed),len(terminal_folds))} of the {len(terminal_folds)} terminal folds."],
        ['Public-model flag also positive against recorded hidden hands', len(both_folds), f"{pct(len(both_folds),len(folds))} of all folds; useful review candidates, still model-dependent."],
        ['Profitable call against actual hands, with no later betting', len(oracle_folds), f"{pct(len(oracle_folds),len(terminal_folds))} of terminal folds; hindsight only."],
        ['Of those, river calls that would win or share', sum(r['street']=='river' for r in oracle_folds), 'Finished-board hindsight; opponent cards were not visible at the decision.'],
    ])
    p(f"Only {len(terminal_folds)}/{len(folds):,} folds ({pct(len(terminal_folds),len(folds))}) meet the terminal condition. Their street counts are "
      + ', '.join(f"{street}: {s['terminal_folds_by_street'].get(street,0)}" for street in ('preflop','flop','turn','river')) + '. '
      'This limited coverage is why the report gives flagged cases rather than a single supposedly exact unnecessary-fold percentage.')
    p(f"Among the {len(missed)} public-model flags, {len(missed)-len(both_folds)} were not favorable against the actual hidden cards. The combined actual-hand call expectation of all {len(missed)} flags is {sum(r['oracle']['call_ev'] for r in missed):+.1f} chips. "
      'This is a warning about model uncertainty, not a reason to judge a decision by the hidden cards alone.')
    p(f"The data also contains {s['fold_tags'].get('positive_hidden_card_checkdown_ev',0):,} positive hidden-card checkdown estimates and "
      f"{s['fold_tags'].get('would_share_recorded_final_board_against_then_live_hands',0):,} folds that would share the recorded final board. Only {sum(r['hindsight_final_equity'] is not None for r in folds):,} folded hands have a five-card board recorded. "
      'These figures assume hidden cards, a selected future board, or unresolved opponents checking down; they are not blunder counts.')
    sub('Missed-call cases supported by both models and actual-hand expectation')
    table(['Match / hand', 'Holding / street', 'Call / pot before call', 'Public EV: tight / loose', 'Actual-hand call EV'], [
        [f"`{r['match']}` / h{r['hand']}", f"{card_text(r['hole'])} / {r['street']}", f"{r['call']} / {r['pot']}",
         f"{r['public']['tight']['call_ev']:+.1f} / {r['public']['loose']['call_ev']:+.1f}", f"{r['oracle']['call_ev']:+.1f}"]
        for r in sorted(both_folds, key=lambda r:-r['oracle']['call_ev'])
    ])
    shove_cases = [r for r in both_folds if r['known_shovers']]
    if shove_cases:
        r = max(shove_cases, key=lambda r:r['oracle']['call_ev'])
        names = ', '.join(r['seats'][i] for i in r['known_shovers'])
        p(f"In `{r['match']}`, hand {r['hand']}, {card_text(r['hole'])} folded facing {r['call']} into {r['pot']}. "
          f"The prior {r['prior_hands']} hands already identified shove-heavy player(s) {names}; the call price was {100*r['pot_odds']:.1f}% of the resulting pot. "
          'The audit broadens only publicly demonstrated near-always shovers, after at least eight prior hands and an 80% shove rate. Other players calling those shoves retain separate ranges.')

    head('Weaknesses and action classifications')
    sub('1. Expensive river calls with weak showdown value')
    river_calls = sum(r['action']=='call' and r['street']=='river' for r in actions)
    p(f"Both models flag {len(rivers)}/{river_calls} river calls ({pct(len(rivers),river_calls)}). Folding at those decisions changes the recorded results by {river_gain:+,} chips, excluding earlier sunk investments. "
      f"The {len(calls)} total bad-terminal-call flags span {len({r['match'] for r in calls})} games; {sum(r['hand_chips']>0 for r in calls)} occurred in hands that won chips. "
      'Thus the label is based on decision expectation, not simply losing the hand. Weak pairs and ace-high after sustained aggression are the clearest review targets.')
    table(['Match / hand', 'Hole cards', 'Board', 'Call / pot', 'Public EV: tight / loose', 'Hand chips'], [
        [f"`{r['match']}` / h{r['hand']}", card_text(r['hole']), card_text(r['board']), f"{r['call']} / {r['pot']}",
         f"{r['public']['tight']['call_ev']:+.1f} / {r['public']['loose']['call_ev']:+.1f}", r['hand_chips']]
        for r in sorted(rivers, key=lambda r:r['public_ev_upper'])[:8]
    ])
    sub('2. Turn calls that lead into costly river decisions')
    reviews = [r for r in actions if r['classification']=='possible_nonterminal_bad_call']
    p(f"There are {len(reviews)} additional call-review flags, {sum(r['street']=='turn' for r in reviews)} on the turn. Both models give negative checkdown expectation, "
      'but implied odds, future folds and future bets prevent a firm blunder diagnosis. Turn and river costs from the same hand must not be added as independent savings.')
    sequences = []
    for r in rivers:
        earlier = [x for x in by_hand[(r['match'],r['hand'])] if x['action_index']<r['action_index'] and x['classification']=='possible_nonterminal_bad_call']
        if earlier:
            sequences.append((r, earlier[-1]))
    if sequences:
        river, turn = max(sequences,key=lambda pair:pair[0]['call']+pair[1]['call'])
        h = hand_map[(river['match'],river['hand'])]
        p(f"Example: `{river['match']}`, hand {river['hand']}, holding {card_text(river['hole'])}. "
          f"On {card_text(turn['board'])}, Halliday called {turn['call']} into {turn['pot']} "
          f"(model EV {turn['public']['tight']['call_ev']:+.1f}/{turn['public']['loose']['call_ev']:+.1f}). "
          f"It then called {river['call']} on {card_text(river['board'])} and finished {river['hand_chips']:+} chips. "
          f"Folding the earlier decision would limit the loss to {turn['invested']} chips; folding the river would limit it to {river['invested']}. These are alternative stopping points.")
        table(['Action #', 'Street / board', 'Player', 'Action', 'Amount'], [
            [i+1, x['street']+' / '+card_text(x['board']), x['bot'], x['action'], x['amount']]
            for i,x in enumerate(h['log'])
        ])
        p('For raises, amount is the total street bet target; for calls, it is the additional chips paid. This trace reproduces observed actions, not a simulation of an alternative strategy.')
    sub('3. Adaptation and range calibration')
    p('A very high preflop fold rate can coexist with overly optimistic river calls: the two decisions face different opponent selection. Prioritize stronger responses to repeated postflop aggression and selective widening against demonstrated shove-heavy players. Do not assign a shove caller the same loose range as the shover. One-pair stack commitments need review, but a cooler is not automatically a mistake.')
    sub('4. Bluff outcomes are review labels, not automatic blunders')
    p(f"The audit labels {s['classifications'].get('failed_air_bet',0)} failed high-card/no-draw bets and {s['classifications'].get('failed_semibluff',0)} failed semibluff actions. "
      'A profitable bluff strategy loses some called bets. The replay does not reveal how opponents would react to different bet sizes, so this audit cannot establish optimal bluff frequency or missed value bets.')
    table(['Action classification', 'Ladder actions', 'Evidence level'], [
        ['certain_avoidable_fold', len(certain), 'Provable dominance in the audited context'],
        ['probable_bad_terminal_call', len(calls), 'Both public models below −2 chips, including sampling margin'],
        ['probable_missed_terminal_call', len(missed), 'Both public models above +2 chips, including sampling margin'],
        ['possible_nonterminal_bad_call', len(reviews), 'Review candidate; future betting omitted'],
        ['possible_nonterminal_overfold', s['classifications'].get('possible_nonterminal_overfold',0), 'Review candidate; future betting omitted'],
        ['hindsight_losing_call_only', s['classifications'].get('hindsight_losing_call_only',0), 'Hidden-card evidence only'],
        ['hindsight_missed_call_only', s['classifications'].get('hindsight_missed_call_only',0), 'Hidden-card evidence only'],
        ['failed_air_bet / failed_semibluff', f"{s['classifications'].get('failed_air_bet',0)} / {s['classifications'].get('failed_semibluff',0)}", 'Outcome labels'],
        ['All remaining actions', sum(v for k,v in s['classifications'].items() if k.endswith('_not_flagged')), 'No error established; alternatives may be unassessed'],
    ])

    head('What happened in negative-chip matches?')
    p(f"The {len(negative)} negative ladder games total {s['negative_match_net']:+,} chips. "
      f"{sum(m['flags']>0 for m in negative)} contain a probable terminal call/fold flag; {sum(m['flags']==0 for m in negative)} have no such flag. "
      'A negative result alone is insufficient to conclude that the bot played badly. The following exclusive hand categories reconcile to the negative-game total; the amounts include full hand results, not the marginal cost of a flagged action.')
    table(['Hand category inside negative games', 'Hands', 'Actual chips'], [
        [TITLES[k], f"{v['hands']:,}", f"{v['chips']:+,}"]
        for k,v in sorted(s['losses_in_negative_matches'].items(),key=lambda pair:pair[1]['chips'])
    ])
    sub('Worst five games: decision flags versus all-in runouts')
    for m in negative[:5]:
        rr = [r for r in by_match[m['match']] if r['classification'] in BLUNDERS]
        p(f"`{m['match']}`: {m['chips']:+} chips, {m['bad_calls']} bad-call flags and {m['missed_calls']} missed-call flags. "
          f"Its {m['allin_count']} auditable all-in hands returned {m['allin_actual']:+,.0f} chips versus {m['allin_expected']:+,.1f} expected against the recorded hands "
          f"({m['allin_luck']:+,.1f} runout difference). "
          + (f"Flagged hand numbers: {', '.join(str(r['hand']) for r in sorted(rr,key=lambda r:r['hand']))}. " if rr else 'No terminal decision blunder is established by the tested range models. ')
          + 'The runout estimate addresses the cards after betting ended, not the quality of every earlier action.')
    sub('Every losing game')
    p('Call/fold flags are model-dependent. The largest loss category is descriptive and may include sound decisions. “Fold-at-call saving” changes only flagged terminal calls, includes flagged calls that won, and does not include missed-call estimates. It must not be added to the all-in runout difference because the same hands can appear in both.')
    loss_rows=[]
    for m in negative:
        cats={k:v for k,v in m['loss_categories'].items() if v['chips']<0}
        primary=min(cats,key=lambda k:cats[k]['chips'])
        rr=[r for r in by_match[m['match']] if r['classification'] in BLUNDERS]
        example=', '.join(f"h{r['hand']} {r['action']}" for r in sorted(rr,key=lambda r:r['hand'])) or f"h{m['worst_hands'][0]['hand']} largest loss; unflagged"
        loss_rows.append([f"`{m['match']}`",m['chips'],f"{m['bad_calls']} / {m['missed_calls']}",
                          f"{m['terminal_call_fold_saving']:+}", f"{m['allin_luck']:+.0f}",
                          f"{TITLES[primary]} ({cats[primary]['chips']:+,})",example])
    table(['Match','Chips','Call / fold flags','Fold-at-call saving','All-in runout difference','Largest loss category','Hands to review'],loss_rows)

    head('Chronology and limits on current-version conclusions')
    table(['Time quarter, Melbourne','Games','Chips','Folds / hands','Terminal flags'],[
        [stamp(x['from_at'])+' – '+stamp(x['to_at']), x['matches'], f"{x['chips']:+,}", f"{x['folds']:,}/{x['hands']:,}",x['blunders']]
        for x in s['periods']
    ])
    p(f"The latest {last['matches']} games contain {last['classifications'].get('probable_bad_terminal_call',0)} bad-terminal-call flags and "
      f"{last['classifications'].get('probable_missed_terminal_call',0)} missed-terminal-call flags, with {last['folds']:,} folds ({pct(last['folds'],last['hands'])} of hands). "
      'No flag is not a certificate of correct play: this method does not solve all preflop, raise-sizing, bluff and future-street decisions. Timestamp units are normalized for ordering. The report does not infer deployment boundaries from a name or a validation game.')

    head('All probable blunders: action-level review list')
    p('The full CSV includes every action. This shorter list contains only provable or probable terminal decision flags. “Actual EV” uses hidden cards and must not be substituted for the public-information decision models. Positive hand chips do not remove a decision flag.')
    table(['Match / hand / action #','Class','Cards / board','Call / pot','Public call EV: tight / loose','Actual call EV','Hand chips'],[
        [f"`{r['match']}` / {r['hand']} / {r['action_index']}",r['classification'].removeprefix('probable_'),
         card_text(r['hole'])+' / '+card_text(r['board']),f"{r['call']} / {r['pot']}",
         f"{r['public'].get('tight',{}).get('call_ev',0):+.1f} / {r['public'].get('loose',{}).get('call_ev',0):+.1f}",f"{r['oracle']['call_ev']:+.1f}",r['hand_chips']]
        for r in sorted((r for r in actions if r['classification'] in BLUNDERS),key=lambda r:(timestamp_ms(r['at']),r['match'],r['hand'],r['action_index']))
    ])

    head('Method, verification and limitations')
    validation=[m for m in all_m if m['kind']=='validation']
    replay_ids={m['match'] for m in all_m}
    absent=[m['id'] for m in metadata if 'Halliday' in m['names'] and m['id'] not in replay_ids]
    p(f"The source contains {extraction['rows']:,} rows from {extraction['all_matches']:,} matches. "
      f"Metadata lists {extraction['metadata_target_matches']} Halliday matches; {len(all_m)} have replay actions ({len(absent)} missing). "
      f"The {len(validation)} validation games contribute {sum(m['hands'] for m in validation)} hands and {sum(m['chips'] for m in validation):+,} chips and are excluded from ladder rates. "
      f"All replays combined: {len(all_h):,} hands, {len(all_a):,} actions, {sum(h['chips'] for h in all_h):+,} chips.")
    if absent:
        p('Metadata matches without action rows: '+', '.join(f'`{x}`' for x in absent)+'.')
    p(f"Every recorded pot, legal action amount, seat/name mapping, hole-card consistency check, final seat/bot delta, odd-chip allocation and pot winner was checked. "
      f"All {len(audit['matches'])} match totals reconcile; hands are contiguous, and {len(audit['errors'])} target hands failed reconstruction. "
      f"The independent SDK evaluated {audit['showdown_pots']:,} contested pot layers.")
    p('Call EV is expected hero-eligible gross payout minus the additional call. Already invested chips are sunk. For terminal decisions, no additional future betting is required. Nonterminal estimates assume all currently live players match the current bet, within stack caps, then check down. They omit future raises, folds, implied odds and value bets.')
    p('The actual-hand calculation conditions on all recorded hole cards, including folded cards, and only the board visible at the decision. Flop/turn runouts are enumerated exactly; preflop uses 4,096 seeded runouts. Future board cards do not choose the sampled runouts. Fractional tied payouts are used for EV, while actual settlement separately checks integer odd chips.')
    p('Public models see only Halliday’s hole cards, the visible board and preceding public actions. They do not see hidden opponent cards or future outcomes. Tight preflop VPIP/PFR/3-bet widths are 22%/12%/5%; loose widths are 45%/30%/14%. Postflop bet/call cutoffs and bluff floors are 0.75/0.50/0.10 versus 0.55/0.30/0.30. An opponent publicly observed to shove in at least 80% of eight or more prior hands receives an any-two preflop prior when shoving. Other players retain their own likelihood updates. Hole cards are sampled jointly with collision rejection.')
    p(f"Both models scored {s['public_scored']:,} facing-bet contexts: every terminal opportunity and heads-up postflop opportunities. Terminal estimates use 8,192 samples per model; others use 4,096. "
      'A probable flag requires both models to disagree with the action by more than two chips after a 1.96-standard-error sampling margin. That margin covers Monte Carlo noise, not range-model error or the many decisions screened. Both models share the repository’s action-likelihood functions, so they are sensitivity checks, not independent empirical validation or a poker solver. Preflop raise size is not fully modeled as a range signal.')
    p('All actions receive a classification, but checks and raises are not exhaustively optimized. A not-flagged action may have unassessed alternatives. The total error rate cannot be inferred from the fraction of labels marked probable. Neither lost chips nor a hidden-card winner alone proves a blunder.')
    table(['GPU worker','Games scored','Seven-card rankings','Device buffers'],[
        [device,sum(x['device']==device for x in gpu),f"{sum(x['ranked_hands'] for x in gpu if x['device']==device):,}",f"{max(x['device_buffer_bytes'] for x in gpu if x['device']==device):,} bytes"]
        for device in sorted({x['device'] for x in gpu})
    ])
    p(f"{len({x['device'] for x in gpu})} V100 workers ran in parallel and executed {sum(x['ranked_hands'] for x in gpu):,} actual CUDA seven-card rankings. "
      + (f"The computation stage took {run['wall_seconds']:.1f} seconds, including worker startup and result serialization. " if run else '')
      + 'Each worker also needs a CUDA context beyond the listed buffers. Packed GPU rankings are checked against CPU evaluation at startup. Extraction, reconstruction, verification and rendering are separate stages.')
    if verification:
        p('Final verification: '+verification['description'])
    else:
        p('See reconstruction-audit.json and gpu-work.json for completed checks; no separate final verification artifact is present.')

    head('Prioritized improvements to test')
    table(['Priority','Change to investigate','Validation'],[
        [1,'Calibrate large river calls after repeated aggression, particularly ace-high and weak pairs.','Replay flagged contexts and test on untouched matches; preserve profitable calls.'],
        [2,'Review marginal turn calls and the planned response to a blank river.','Measure complete hand outcomes; avoid double-counting alternative fold points.'],
        [3,'Distinguish known frequent shovers from selective callers of their shoves.','Use earlier public actions only; test different field compositions.'],
        [4,'Audit range updates and one-pair stack commitments after reraises.','Log equity/ranges/timing and compare predictions with held-out evidence.'],
        [5,'Record version hashes, verdicts and decision diagnostics.','Separate historical leaks, current behavior, range errors and clock fallback.'],
    ])
    head('Files and reproduction')
    base='../results/'+directory.name
    p(f"[Every action and classification]({base}/action-classifications.csv) · [Probable blunders]({base}/blunders.csv) · "
      f"[Every match review]({base}/match-reviews.csv) · [Every hand outcome]({base}/hand-outcomes.csv) · [Summary JSON]({base}/summary.json).")
    p(f"[Detailed actions with full prior histories]({base}/classified-actions.json), [reconstruction audit]({base}/reconstruction-audit.json), "
      f"[input fingerprints]({base}/extraction.json), [GPU work]({base}/gpu-work.json), and [final verification]({base}/verification.json) retain the evidence. "
      'Large result files are local and Git-ignored. Preserve the result directory when collecting a newer snapshot.')
    path=shlex.quote(str(directory))
    source=shlex.quote(str(Path(extraction['source']).parent))
    prefix='OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-estimators/bin/python -B '
    commands=[prefix+f'analysis/halliday_performance.py extract --snapshot {source} --directory {path}',
              prefix+f'analysis/halliday_performance.py prepare --directory {path}',
              prefix+f'analysis/halliday_performance.py compute --devices 0,1,2,3 --directory {path}',
              prefix+f'analysis/halliday_report.py --directory {path}',
              prefix+f'analysis/verify_halliday_report.py --directory {path}',
              prefix+f'analysis/render_halliday_report.py --directory {path}']
    blocks.append(('code','\n'.join(commands)))
    out.mkdir(parents=True,exist_ok=True)
    md,ht=[],[]
    def inline(value):
        value=html.escape(str(value))
        value=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',value)
        return re.sub(r'`([^`]+)`',r'<code>\1</code>',value)
    for kind,value in blocks:
        if kind.startswith('h'):
            md.append('#'*int(kind[1])+' '+value)
            ht.append(f'<{kind}>{inline(value)}</{kind}>')
        elif kind=='p':
            md.append(value);ht.append('<p>'+inline(value)+'</p>')
        elif kind=='code':
            md.append('```sh\n'+value+'\n```');ht.append('<pre><code>'+html.escape(value)+'</code></pre>')
        else:
            headers,body=value
            md.append('\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join('---' for _ in headers)+'|']+
                                ['| '+' | '.join(str(x).replace('|','\\|') for x in row)+' |' for row in body]))
            ht.append('<div class="table"><table><thead><tr>'+''.join('<th>'+inline(c)+'</th>' for c in headers)+
                      '</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(c)+'</td>' for c in row)+'</tr>' for row in body)+'</tbody></table></div>')
    stem='halliday-performance-'+date_part
    (out/(stem+'.md')).write_text('\n\n'.join(md)+'\n')
    style='body{max-width:1240px;margin:40px auto;padding:0 24px;font:16px/1.6 system-ui;color:#18212e;background:#fafbfc}h1{font-size:32px;line-height:1.2}h2{margin-top:44px;border-bottom:2px solid #cdd9e8;padding-bottom:8px}h3{margin-top:28px}p{max-width:1050px}a{color:#165b99}code{font-size:.88em;background:#eef2f6;padding:2px 4px;overflow-wrap:anywhere}pre{background:#eef2f6;padding:18px;overflow:auto}.table{overflow-x:auto;margin:20px 0}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;vertical-align:top;padding:9px 12px;border-bottom:1px solid #dce3eb}th{background:#eaf0f7}tr:nth-child(even){background:#f1f5f9}@media print{body{margin:0;max-width:none}table{font-size:10px}h2{break-after:avoid}tr{break-inside:avoid}}'
    (out/(stem+'.html')).write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Halliday performance audit</title><style>'+style+'</style></head><body><main>'+''.join(ht)+'</main></body></html>')
    print(out/(stem+'.md'));print(out/(stem+'.html'))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,default=DIR)
    parser.add_argument('--output',type=Path,default=OUT)
    args=parser.parse_args()
    render(args.directory,args.output)
