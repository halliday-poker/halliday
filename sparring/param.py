"""Sparring opponent with an adjustable style, so the harness can field many
different opponents instead of a few fixed stereotypes. Never submitted.

A style is a dict of numbers:

    vpip        share of starting hands it plays (by preflop rank)
    pfr         share it opens with a raise (<= vpip)
    threebet    share it re-raises with when facing a raise (<= pfr)
    limp        chance it limps a hand it would otherwise open-raise
    aggression  willingness to bet and raise made hands
    cbet        chance of a flop continuation bet as preflop raiser
    bluff       chance of betting or raising with nothing
    stickiness  how far down it calls (0 folds easily, 1 calling station)
    size        bet size as a fraction of the pot
    adaptive    1 = loosens up against aggression, bluffs more against folders

The harness builds these from specs: `param:lag` is the archetype centre,
`param:lag@<seed>` is that archetype with every number jittered by +-20%
from the seed. Run directly (e.g. `macpoker play bot/main.py
sparring/param.py`) it plays the TAG centre.
"""

import random

from macpoker import Bot
from macpoker.cards import parse_cards
from macpoker.evaluator import evaluate

RANKS = "23456789TJQKA"

ARCHETYPES = {
    "nit":      dict(vpip=.13, pfr=.10, threebet=.03, limp=.10, aggression=.45, cbet=.50,
                     bluff=.05, stickiness=.30, size=.60, adaptive=0),
    "tag":      dict(vpip=.22, pfr=.18, threebet=.07, limp=.05, aggression=.60, cbet=.65,
                     bluff=.15, stickiness=.45, size=.66, adaptive=0),
    "lag":      dict(vpip=.35, pfr=.28, threebet=.12, limp=.05, aggression=.75, cbet=.75,
                     bluff=.30, stickiness=.50, size=.75, adaptive=0),
    "station":  dict(vpip=.55, pfr=.07, threebet=.02, limp=.70, aggression=.20, cbet=.30,
                     bluff=.05, stickiness=.85, size=.50, adaptive=0),
    "maniac":   dict(vpip=.60, pfr=.45, threebet=.25, limp=.10, aggression=.90, cbet=.90,
                     bluff=.50, stickiness=.60, size=1.0, adaptive=0),
    "adaptive": dict(vpip=.25, pfr=.20, threebet=.08, limp=.05, aggression=.60, cbet=.65,
                     bluff=.20, stickiness=.50, size=.70, adaptive=1),
}


def _clamp_style(s):
    for k in s:
        if k == "size":
            s[k] = min(max(s[k], 0.25), 1.5)
        elif k != "adaptive":
            s[k] = min(max(s[k], 0.0), 1.0)
    s["pfr"] = min(s["pfr"], s["vpip"])
    s["threebet"] = min(s["threebet"], s["pfr"])
    return s


def sample_style(archetype, rng, jitter=0.2):
    """The archetype's centre with every number scaled by a random +-jitter."""
    centre = ARCHETYPES[archetype]
    s = {k: v if k == "adaptive" else v * rng.uniform(1 - jitter, 1 + jitter)
         for k, v in centre.items()}
    return _clamp_style(s)


def style_for(tail):
    """`lag` -> the lag centre; `lag@seed` -> lag jittered from that seed."""
    archetype, _, seed = tail.partition("@")
    if archetype not in ARCHETYPES:
        raise ValueError(f"unknown archetype {archetype!r}; known: {', '.join(ARCHETYPES)}")
    if not seed:
        return dict(ARCHETYPES[archetype])
    return sample_style(archetype, random.Random(seed))


# --- preflop: rank all 169 starting hands, as a percentile of the 1326 combos ---

def _chen(hi, lo, suited):
    pts = {12: 10, 11: 8, 10: 7, 9: 6}.get(hi, (hi + 2) / 2)
    if hi == lo:
        # Chen undervalues small pairs; floor them near their equity rank
        return max(pts * 2, 6 + hi * 0.5)
    if suited:
        pts += 2
    gap = hi - lo - 1
    pts -= [0, 1, 2, 4][gap] if gap < 4 else 5
    if gap <= 1 and hi < 10:
        pts += 1
    return pts


def _build_percentiles():
    classes = []
    for hi in range(13):
        for lo in range(hi + 1):
            if hi == lo:
                classes.append(((hi, lo, False), 6))
            else:
                classes.append(((hi, lo, True), 4))
                classes.append(((hi, lo, False), 12))
    classes.sort(key=lambda c: -(_chen(*c[0]) + c[0][0] * 0.01 + c[0][1] * 0.001))
    pct, cum = {}, 0
    for key, combos in classes:
        pct[key] = (cum + combos / 2) / 1326
        cum += combos
    return pct


PERCENTILE = _build_percentiles()


def hand_percentile(hole):
    """0 = best starting hand (AA), 1 = worst."""
    r = sorted((RANKS.index(c[0]) for c in hole), reverse=True)
    return PERCENTILE[(r[0], r[1], hole[0][1] == hole[1][1] and r[0] != r[1])]


# --- postflop: fast made-hand + draw heuristic ---

def _board_category(board):
    if len(board) == 5:
        return evaluate(parse_cards(board))[0]
    counts = sorted((sum(c[0] == r for c in board) for r in {c[0] for c in board}), reverse=True)
    if counts[0] >= 3:
        return 3
    if counts[0] == 2:
        return 2 if len(counts) > 1 and counts[1] == 2 else 1
    return 0


def strength(hole, board):
    """(0-1 strength, holding a draw) from the made hand that uses our cards."""
    hr = [RANKS.index(c[0]) for c in hole]
    br = [RANKS.index(c[0]) for c in board]
    cat = evaluate(parse_cards(hole + board))[0]
    board_cat = _board_category(board)

    if cat <= board_cat:
        s = 0.10 + 0.05 * sum(r > max(br) for r in hr)
    elif cat - board_cat == 1 and cat <= 2:
        # exactly one pair of our own
        if hr[0] == hr[1]:
            s = 0.70 if hr[0] > max(br) else 0.35
        else:
            p = max((r for r in hr if r in br), default=-1)
            ranked = sorted(set(br), reverse=True)
            if p == ranked[0]:
                s = 0.60 + (0.05 if max(r for r in hr) >= 10 and hr[0] != hr[1] else 0)
            elif len(ranked) > 1 and p == ranked[1]:
                s = 0.45
            else:
                s = 0.35
    else:
        s = {2: .75, 3: .82, 4: .88, 5: .90, 6: .95, 7: .99, 8: .99}[cat]

    draw = False
    if len(board) < 5 and cat < 4:
        cards = hole + board
        for suit in "cdhs":
            if sum(c[1] == suit for c in cards) == 4 and any(c[1] == suit for c in hole):
                s += 0.15
                draw = True
                break
        ranks = set(hr + br)
        if 12 in ranks:
            ranks.add(-1)  # ace plays low
        windows = [w for w in range(-1, 9)
                   if sum(r in ranks for r in range(w, w + 5)) == 4
                   and any(w <= r < w + 5 for r in hr)]
        if windows:
            s += 0.12 if len(windows) >= 2 else 0.05
            draw = True
    return min(s, 0.99), draw


class ParamBot(Bot):
    def __init__(self, style=None, seed=None):
        self.base = dict(style or ARCHETYPES["tag"])
        self.rng = random.Random(seed)
        self.me = None
        self.stats = {}  # player id -> [actions, raises, folds, facing-a-bet actions]

    # --- adaptive archetype: track everyone else ---
    def on_action(self, event):
        who = event["players"][event["seat"]]
        if who == self.me:
            return
        st = self.stats.setdefault(who, [0, 0, 0, 0])
        kind = event["action"]
        st[0] += 1
        st[1] += kind == "raise"
        st[2] += kind == "fold"
        st[3] += kind in ("fold", "call", "raise")

    def style(self, state):
        s = dict(self.base)
        if not s.get("adaptive"):
            return s
        live = [state.player_at(i) for i, f in enumerate(state.folded) if not f and i != state.seat]
        seen = [self.stats[p] for p in live if p in self.stats and self.stats[p][0] >= 10]
        if seen:
            agg = sum(x[1] / x[0] for x in seen) / len(seen)
            folds = sum(x[2] / max(x[3], 1) for x in seen) / len(seen)
            if agg > 0.3:
                s["stickiness"] += 0.15
                s["bluff"] -= 0.05
            if folds > 0.5:
                s["bluff"] += 0.15
                s["cbet"] += 0.15
            elif folds < 0.25:
                s["bluff"] *= 0.3
        return _clamp_style(s)

    # --- actions ---
    def bet(self, state, raise_to):
        if not state.can_raise:
            return state.call() if state.to_call else state.check()
        return state.raise_to(int(min(max(raise_to, state.min_raise_to), state.max_raise_to)))

    def passive(self, state, call):
        if state.to_call == 0:
            return state.check()
        return state.call() if call else state.fold()

    def act(self, state):
        self.me = state.player
        s = self.style(state)
        if state.street == "preflop":
            return self.preflop(state, s)
        return self.postflop(state, s)

    def preflop(self, state, s):
        pre = [h for h in state.history if h[0] == "preflop"]
        raises = [h for h in pre if h[2] == "raise"]
        pct = hand_percentile(state.hole)
        if not raises:
            limpers = sum(h[2] == "call" for h in pre)
            if pct < s["vpip"]:
                if pct < s["pfr"] and self.rng.random() >= s["limp"]:
                    return self.bet(state, 5 + 2 * limpers)
                return self.passive(state, True)
            return self.passive(state, False)
        last = raises[-1][3]
        if len(raises) == 1:
            if pct < s["threebet"]:
                return self.bet(state, 3 * last)
            defend = s["vpip"] * (0.3 + 0.5 * s["stickiness"])
            return self.passive(state, pct < defend and state.to_call <= 0.3 * state.my_stack)
        if pct < s["threebet"] * 0.35:
            return self.bet(state, state.max_raise_to if last > 60 else 2.3 * last)
        return self.passive(state, pct < s["threebet"] * (0.6 + s["stickiness"]))

    def postflop(self, state, s):
        st, draw = strength(state.hole, state.board)
        rng = self.rng
        bet_size = state.pot * s["size"] * rng.uniform(0.85, 1.15)
        street_raises = [h for h in state.history if h[0] == state.street and h[2] == "raise"]
        pre_raises = [h for h in state.history if h[0] == "preflop" and h[2] == "raise"]
        aggressor = bool(pre_raises) and pre_raises[-1][1] == state.seat

        if state.to_call == 0:
            if st >= 0.8 - 0.3 * s["aggression"]:
                return self.bet(state, bet_size)
            if aggressor and state.street == "flop" and not street_raises and rng.random() < s["cbet"]:
                return self.bet(state, bet_size * 0.8)
            if draw and rng.random() < s["aggression"] * 0.6:
                return self.bet(state, bet_size)
            if rng.random() < s["bluff"] * 0.5:
                return self.bet(state, bet_size)
            return state.check()

        top = max(state.street_bets)
        if st >= 0.92 - 0.12 * s["aggression"] and rng.random() < 0.4 + 0.6 * s["aggression"]:
            return self.bet(state, 3 * top)
        if state.street != "river" and rng.random() < s["bluff"] * 0.15:
            return self.bet(state, 3 * top)
        pot_odds = state.to_call / (state.pot + state.to_call)
        need = pot_odds + 0.3 * (1 - s["stickiness"]) - 0.1
        bonus = 0.1 if draw and state.street != "river" else 0
        return self.passive(state, st + bonus >= need)
