"""Opponent hand ranges for this hand, and what this game's showdowns teach.

Every opponent starts each hand holding any of the 1,326 two-card combos with
equal weight. Each public action multiplies every combo's weight by how likely
that action is with that combo (a likelihood), so the range narrows toward the
hands that act that way. The likelihoods are soft cutoffs on hand strength:

    preflop   strength = rank of the combo's class by equity vs random hands
    postflop  strength = share of all combos the made hand beats on this board,
                         plus a bonus for flush and straight draws

Cutoffs come from this game's counters (opponents.py) pulled toward field
priors, and postflop from showdowns: each revealed hand shows how strong that
player really was when they bet or called, weighted by how biased that sample
is. Bluffs that worked are never shown, so only showdowns where someone called
the player's last bet count fully.

Hooks only record events. All computing happens lazily inside act(), where the
clock is measured in the tournament (the harness does not time hooks).
Nothing is kept between games; learning is keyed by this game's player ids.
"""

from collections import defaultdict
from itertools import combinations

import numpy as np

if __package__:
    from .engine import _evaluate, _parse_card
    from .hand_ranks import EQUITY
    from .opponents import shrunk_rate
else:
    from engine import _evaluate, _parse_card
    from hand_ranks import EQUITY
    from opponents import shrunk_rate

RANKS = "23456789TJQKA"
CARDS = [r + s for s in "cdhs" for r in RANKS]
COMBOS = list(combinations(CARDS, 2))
COMBO_IDS = [(_parse_card(a), _parse_card(b)) for a, b in COMBOS]
COMBO_MASKS = [(1 << a) | (1 << b) for a, b in COMBO_IDS]
COMBO_A = np.array([a for a, _ in COMBO_IDS])
COMBO_B = np.array([b for _, b in COMBO_IDS])
N = len(COMBOS)


def _class_of(a, b):
    ra, rb = sorted((a[0], b[0]), key=RANKS.index, reverse=True)
    if ra == rb:
        return ra + rb
    return ra + rb + ("s" if a[1] == b[1] else "o")


def _percentiles(column):
    """0 = best combo, 1 = worst, by the class's equity (combo-weighted)."""
    classes = [_class_of(a, b) for a, b in COMBOS]
    order = sorted(range(N), key=lambda i: -EQUITY[classes[i]][column])
    pct = np.empty(N)
    for position, i in enumerate(order):
        pct[i] = (position + 0.5) / N
    return pct


PREFLOP_PCT = (_percentiles(0), _percentiles(1))  # (heads-up, multiway) rankings


def _sig(x):
    """Logistic ramp; works on numbers and on arrays of all combos at once."""
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40, 40)))


# --- postflop strength of every combo on a board ---------------------------

_strength_cache: dict = {}


def _encode(value):
    code = 0
    for i in range(6):
        code = code * 16 + (value[i] if i < len(value) else 0)
    return code


def _straight_draw_ranks(board_ranks):
    """For every hole-rank pair, whether it makes an open-ended or double-gutshot draw."""
    out = {}
    for hi in range(13):
        for lo in range(hi + 1):
            ranks = set(board_ranks) | {hi, lo}
            own = {hi, lo}
            if 12 in ranks:
                ranks.add(-1)
            if 12 in own:
                own.add(-1)
            missing = set()
            for start in range(-1, 9):
                run = set(range(start, start + 5))
                gaps = run - ranks
                if len(gaps) == 1 and run & own:
                    missing |= gaps
            out[(hi, lo)] = len(missing) >= 2
    return out


def board_strength(board):
    """(strength, draws) arrays per combo index; strength is NaN for combos the board blocks.

    Strength is the share of unblocked combos this combo's made hand beats
    (ties count half), so 1.0 is the nuts. Draws are flush or open-ended /
    double-gutshot straight draws using a hole card, on the flop and turn only.
    """
    key = tuple(board)
    if key in _strength_cache:
        return _strength_cache[key]
    ids = tuple(_parse_card(c) for c in board)
    blocked = sum(1 << c for c in ids)
    suits = [0] * 4
    for c in ids:
        suits[c // 13] += 1
    straight = _straight_draw_ranks([c % 13 for c in ids]) if len(board) < 5 else {}
    codes, draws = [None] * N, [False] * N
    for i, (a, b) in enumerate(COMBO_IDS):
        if COMBO_MASKS[i] & blocked:
            continue
        value = _evaluate((a, b) + ids)
        codes[i] = _encode(value)
        if straight and value[0] < 4:
            sa, sb = a // 13, b // 13
            flush_draw = (suits[sa] + 1 + (sb == sa) == 4) or (suits[sb] + 1 + (sa == sb) == 4)
            ra, rb = a % 13, b % 13
            draws[i] = flush_draw or straight[(max(ra, rb), min(ra, rb))]
    valid = np.array([c is not None for c in codes])
    values = np.array([c if c is not None else -1 for c in codes], dtype=np.int64)
    ordered = np.sort(values[valid])
    below = np.searchsorted(ordered, values, "left")
    ties = np.searchsorted(ordered, values, "right") - below - 1
    strength = np.where(valid, (below + 0.5 * ties) / (len(ordered) - 1), np.nan)
    result = (strength, np.array(draws))
    if len(_strength_cache) >= 24:  # a few hands' boards: this hand's, plus the last showdown's
        _strength_cache.clear()
    _strength_cache[key] = result
    return result


# --- likelihood of each action given strength ------------------------------

def preflop_likelihood(kind, pct, raises_before, widths, p):
    """Relative chance of this preflop action with a combo at percentile pct (0 = best).

    widths: this player's (vpip, pfr, threebet) estimates. Raises open with the
    top pfr, re-raise with the top threebet (shrinking by range_4bet_ratio per
    extra raise); calls and limps play the top vpip, minus some of the hands
    that would have raised; a free check keeps some strong hands (traps).
    """
    vpip, pfr, threebet = widths
    floor = p["range_floor"]

    def ramp(cut):
        # The ramp scales with the range, so tight and loose ranges are equally sharp.
        return _sig((cut - pct) / max(1e-3, p["range_preflop_softness"] * cut))

    if kind == "raise":
        cut = pfr if raises_before == 0 else threebet * p["range_4bet_ratio"] ** (raises_before - 1)
        return floor + (1 - floor) * ramp(cut)
    if kind == "call":
        play = vpip if raises_before <= 1 else threebet * p["range_4bet_ratio"] ** (raises_before - 2)
        stronger = pfr if raises_before == 0 else threebet * p["range_4bet_ratio"] ** (raises_before - 1)
        keep = 1 - (1 - p["range_slowplay"]) * ramp(stronger)
        return floor + (1 - floor) * ramp(play) * keep
    if kind == "check":
        return 1 - (1 - p["range_slowplay"]) * ramp(pfr)
    return 1.0


def postflop_likelihood(kind, s, size, facing_raise, learned, p):
    """Relative chance of this postflop action with a combo of strength s (1 = nuts).

    size: bet as a fraction of the pot before it (for a call, the size faced).
    Bigger bets and raises over a bet need stronger hands. Weak hands still
    bet at the player's bluff floor; strong hands still check or call at the
    slow-play share.
    """
    soft = p["range_postflop_softness"]
    bet_cut, call_cut, bluff_floor = learned
    shift = p["range_size_slope"] * (min(size, 2.0) - 0.5)  # overbets beyond 2x pot read as 2x
    raise_cut = bet_cut + p["range_raise_shift"]
    if kind == "raise":
        cut = min(0.98, (raise_cut if facing_raise else bet_cut) + shift)
        # Small bets are bluffs far more often than big ones.
        floor = min(1.0, bluff_floor * next(m for hi, m in p["range_bluff_size_mult"] if size <= hi))
        return floor + (1 - floor) * _sig((s - cut) / soft)
    if kind == "call":
        floor = p["range_floor"]
        keep = 1 - (1 - p["range_slowplay"]) * _sig((s - raise_cut) / soft)
        return floor + (1 - floor) * _sig((s - min(0.95, call_cut + shift)) / soft) * keep
    if kind == "check":
        return 1 - (1 - p["range_slowplay"]) * _sig((s - bet_cut) / soft)
    return 1.0


# --- per-game learning from showdowns --------------------------------------

class ShowdownStats:
    """Bias-weighted samples of a player's shown strength when betting and calling."""

    def __init__(self):
        self.bet_weight = 0.0      # weighted shown postflop bets/raises
        self.bluff_weight = 0.0    # ...of which below their betting cutoff without a draw
        self.value_weight = 0.0    # ...of which above it
        self.value_cut_sum = 0.0   # sum of weight x (2s - 1): cutoff implied by a value bet
        self.call_weight = 0.0
        self.call_cut_sum = 0.0

    def learned(self, p):
        """(bet_cut, call_cut, bluff_floor) for this player: priors moved by evidence."""
        k = p["range_showdown_prior"]
        bet_cut = (self.value_cut_sum + p["range_bet_cut"] * k) / (self.value_weight + k)
        call_cut = (self.call_cut_sum + p["range_call_cut"] * k) / (self.call_weight + k)
        bet_cut = min(0.95, max(0.2, bet_cut))
        call_cut = min(0.9, max(0.05, call_cut))
        # The bluff floor is how likely a hand below the cutoff bets relative
        # to one above it; what showdowns measure is the share of bets below
        # the cutoff. With strengths spread evenly, share = f*cut / (f*cut +
        # 1 - cut). Convert the prior floor to a share, update, convert back.
        prior_floor = p["range_bluff_floor"]
        prior_share = prior_floor * bet_cut / (prior_floor * bet_cut + (1 - bet_cut))
        share = (self.bluff_weight + prior_share * k) / (self.bet_weight + k)
        share = min(0.95, max(0.001, share))
        floor = share / (1 - share) * (1 - bet_cut) / bet_cut
        return bet_cut, call_cut, min(1.0, max(p["range_floor"], floor))


# --- the tracker -------------------------------------------------------------

class RangeTracker:
    def __init__(self, profiles, params):
        self.profiles = profiles          # OpponentTracker.profiles (shared)
        self.p = params
        self.showdowns = defaultdict(ShowdownStats)
        self._pending = []                # finished hands with revealed cards
        self._reset()

    def _reset(self):
        self.players, self.me, self.button = [], None, 0
        self.log, self.boards = [], {"preflop": []}
        self.weights, self.cursor, self.replay = {}, 0, None

    # Hooks: record only.
    def on_hand_start(self, info):
        try:
            self._reset()
            self.players = list(info["players"])
            self.me = info["seat"]
            self.button = info["button"]
        except (KeyError, TypeError):
            pass

    def on_street(self, event):
        try:
            self.boards[event["street"]] = list(event["board"])
        except (KeyError, TypeError):
            pass

    def on_action(self, event):
        try:
            self.log.append((event["street"], event["seat"], event["action"], event["amount"]))
        except (KeyError, TypeError):
            pass

    def on_hand_end(self, info):
        try:
            revealed = {int(s): cards for s, cards in info.get("revealed", {}).items()
                        if int(s) != self.me}
            if revealed and self.p["range_learn_showdowns"]:
                self._pending.append((list(self.log), dict(self.boards), list(self.players),
                                      self.button, revealed))
        except (AttributeError, KeyError, TypeError, ValueError):
            pass

    # Computing, from act() only.
    def widths(self, player):
        """(vpip, pfr, threebet) for a player, shrunk toward the field priors."""
        prof, p = self.profiles.get(player), self.p
        w = p["range_prior_hands"]
        if not prof:
            return p["range_prior_vpip"], p["range_prior_pfr"], p["range_prior_threebet"]
        hands = prof["hands"]
        return (shrunk_rate(prof["vpip"], hands, p["range_prior_vpip"], w),
                shrunk_rate(prof["pfr"], hands, p["range_prior_pfr"], w),
                shrunk_rate(prof["threebets"], prof["threebet_chances"], p["range_prior_threebet"], w))

    @staticmethod
    def _actions(log, n, button):
        """Replay a hand's log: yield (index, seat, street, kind, raises_before, size, facing_raise).

        size is a bet's or raise's increase over the bet in front as a fraction
        of the pot after calling, and for a call the bet faced as a fraction of
        the pot before that bet. Blinds are not in the log, so they are posted here.
        """
        sb, bb = (button, (button + 1) % n) if n == 2 else ((button + 1) % n, (button + 2) % n)
        bets = [0] * n
        bets[sb], bets[bb] = 1, 2
        pot, street, raises = 3, "preflop", 0
        for i, (st, seat, kind, amount) in enumerate(log):
            if st != street:
                street, raises = st, 0
                bets = [0] * n
            facing = max(bets) - bets[seat]
            if kind == "raise":
                added = amount - bets[seat]
                size = (amount - max(bets)) / max(1, pot + facing)
            elif kind == "call":
                added = amount
                size = facing / max(1, pot - facing)
            else:
                added, size = 0, 0.0
            yield i, seat, street, kind, raises, size, raises > 0 and kind == "raise"
            bets[seat] += added
            pot += added
            if kind == "raise":
                raises += 1

    def _update(self, weights, seat, street, kind, raises, size, facing_raise, boards, learned_for):
        p = self.p
        if street == "preflop":
            pct = PREFLOP_PCT[0 if len(self.players) <= 3 else 1]
            widths = self.widths(self.players[seat])
            weights *= preflop_likelihood(kind, pct, raises, widths, p) ** p["range_temper"]
            return
        strength, draws = board_strength(boards[street])
        # Board-blocked combos are excluded later; give them a neutral strength.
        s = np.minimum(1.0, np.nan_to_num(strength, nan=0.5) + p["range_draw_bonus"] * draws)
        weights *= postflop_likelihood(kind, s, size, facing_raise, learned_for(seat), p) ** p["range_temper"]

    def _learned(self, seat):
        return self.showdowns[self.players[seat]].learned(self.p)

    def _catch_up(self):
        """Apply logged actions not yet folded into the opponents' weights."""
        if self.replay is None:
            self.replay = self._actions(self.log, len(self.players), self.button)
        while self.cursor < len(self.log):
            _, seat, street, kind, raises, size, facing_raise = next(self.replay)
            self.cursor += 1
            if seat == self.me or kind == "fold":
                continue
            weights = self.weights.setdefault(seat, np.ones(N))
            self._update(weights, seat, street, kind, raises, size, facing_raise,
                         self.boards, self._learned)

    def learn_pending(self):
        """Fold finished hands' showdowns into each player's ShowdownStats."""
        p = self.p
        for log, boards, players, button, revealed in self._pending:
            last_aggression = {}
            for i, (st, seat, kind, _) in enumerate(log):
                if kind == "raise":
                    last_aggression[seat] = i
            for i, seat, street, kind, raises, size, facing_raise in self._actions(log, len(players), button):
                if seat not in revealed or street == "preflop" or kind in ("fold", "check"):
                    continue
                cards = tuple(revealed[seat])
                idx = _combo_index(cards)
                strength, draws = board_strength(boards[street])
                if idx is None or np.isnan(strength[idx]):
                    continue
                s = strength[idx]
                stats = self.showdowns[players[seat]]
                if kind == "raise":
                    # Their last bet was called (the hand reached showdown), so
                    # that bet is a fair sample; earlier bets survived later
                    # streets that could have ended the hand, so count less.
                    w = 1.0 if last_aggression.get(seat) == i else p["range_showdown_weight_indirect"]
                    stats.bet_weight += w
                    if s < stats.learned(p)[0] and not draws[idx]:
                        stats.bluff_weight += w
                    else:
                        stats.value_weight += w
                        stats.value_cut_sum += w * (2 * s - 1)
                else:  # call: they chose to continue, and later play decided whether we saw it
                    w = p["range_showdown_weight_passive"]
                    stats.call_weight += w
                    stats.call_cut_sum += w * (2 * s - 1)
        self._pending.clear()

    def ranges_for(self, seats, hole, board):
        """Engine-ready ranges for these opponent seats: a {combo: weight} dict, or None
        when the tracked range is still close to uniform (cheaper, same answer)."""
        p = self.p
        self.learn_pending()
        self._catch_up()
        known = [_parse_card(c) for c in list(hole) + list(board)]
        blocked = np.isin(COMBO_A, known) | np.isin(COMBO_B, known)
        out = []
        for seat in seats:
            weights = self.weights.get(seat)
            if weights is None:
                out.append(None)
                continue
            w = np.where(blocked, 0.0, weights)
            live = int(np.count_nonzero(w))
            total = w.sum()
            if not live or total <= 0:
                out.append(None)
                continue
            # Effective share of combos still in play (1 = uniform).
            if total * total / (w * w).sum() / live >= p["range_uniform_skip"]:
                out.append(None)
                continue
            keep = min(p["range_max_combos"], live)
            top = np.argpartition(-w, keep - 1)[:keep]
            out.append({COMBOS[i]: float(w[i] / total) for i in top if w[i] > 0})
        return out


_COMBO_INDEX = {frozenset(c): i for i, c in enumerate(COMBOS)}


def _combo_index(cards):
    return _COMBO_INDEX.get(frozenset(cards))
