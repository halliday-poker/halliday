"""Expected-value action selection for postflop decisions.

Instead of comparing equity with fixed thresholds, every candidate action
(check or fold, call, and bets or raises at a few sizes plus all-in) is scored
in chips, counting the hand as going to showdown after this action:

    EV(check)  = R * equity * pot
    EV(call)   = R * equity * (pot + to_call) - to_call
    EV(bet A)  = P(all fold) * pot
                 + sum over who continues: P(them) * (R * equity vs their continuing
                   ranges * final pot - A)

R discounts equity when we act first (out of position). Each opponent keeps
playing (call or raise) with a likelihood that rises with its hand strength on
this board, shifted by bet size and our position. Across its tracked range
(ranges.py) that gives its fold chance and the range it continues with. The
fold chance is then pulled toward how often it has actually folded to our bets
this game. Equity comes from our hand against each combo the opponent may hold,
over sampled runouts; several opponents combine as a product (independence).

Opponents can also re-raise: each raises a share of the hands it continues
with, at its raise rate to bets this game (pulled toward a prior), to a
multiple of our bet. If raised, we call when our share of the bigger pot pays
for it, and otherwise give up our bet.

What this leaves out: later streets' betting and side pots. The margins
below absorb some of that optimism.
"""

from math import ceil
from random import Random
from time import perf_counter

import numpy as np

if __package__:
    from .engine import _evaluate, _parse_card
    from .opponents import fold_to_us, is_shover, profile_of
    from .preflop import in_position
    from .ranges import COMBO_IDS, COMBO_MASKS, N, _sig, board_strength
else:
    from engine import _evaluate, _parse_card
    from opponents import fold_to_us, is_shover, profile_of
    from preflop import in_position
    from ranges import COMBO_IDS, COMBO_MASKS, N, _sig, board_strength


def _select(weights, valid, cap, rng):
    """Up to `cap` combos carrying the opponent's range, with renormalised weights."""
    idx = np.flatnonzero(valid & (weights > 0))
    if len(idx) > cap:
        w = weights[idx]
        if w.max() <= w.min() * 1.0001:  # (near) uniform: an unbiased random sample
            idx = np.array(sorted(rng.sample(list(idx), cap)))
        else:
            idx = idx[np.argpartition(-w, cap - 1)[:cap]]
    w = weights[idx]
    return idx, w / w.sum()


def _matchups(hole, board, combos, runouts, deadline, min_runouts):
    """Our showdown share against each combo index, averaged over runouts.
    Returns {combo index: share}, or None if the deadline stopped it too early."""
    hole_ids = tuple(_parse_card(c) for c in hole)
    board_ids = tuple(_parse_card(c) for c in board)
    wins = dict.fromkeys(combos, 0.0)
    count = dict.fromkeys(combos, 0)
    done = 0
    for runout in runouts:
        if done >= min_runouts and perf_counter() >= deadline:
            break
        full = board_ids + runout
        mask = sum(1 << c for c in runout)
        ours = _evaluate(hole_ids + full)
        for i in combos:
            if COMBO_MASKS[i] & mask:
                continue
            theirs = _evaluate(COMBO_IDS[i] + full)
            wins[i] += 1.0 if ours > theirs else 0.5 if ours == theirs else 0.0
            count[i] += 1
        done += 1
    if done < min_runouts:
        return None
    return {i: wins[i] / count[i] if count[i] else 0.5 for i in combos}


def _runouts(hole, board, p, rng):
    known = {_parse_card(c) for c in list(hole) + list(board)}
    deck = [c for c in range(52) if c not in known]
    missing = 5 - len(board)
    if missing == 0:
        return [()]
    if missing == 1:
        rng.shuffle(deck)
        return [(c,) for c in deck]
    pairs = set()
    while len(pairs) < p["ev_flop_runouts"]:
        a, b = rng.sample(deck, 2)
        pairs.add((min(a, b), max(a, b)))
    return sorted(pairs, key=lambda _: rng.random())


class Opponent:
    """One live opponent: its range, our share against it, and how it responds."""

    def __init__(self, seat, idx, weights, shares, strength, stack, street_bet,
                 profile, call_shift, oop, p):
        self.seat, self.idx, self.w = seat, idx, weights
        self.e = np.array([shares[i] for i in idx])
        self.s = strength[idx]
        self.stack, self.street_bet = stack, street_bet
        self.profile, self.call_shift, self.oop, self.p = profile, call_shift, oop, p

    def equity(self):
        return float(self.w @ self.e)

    def raise_rate(self):
        """Share of its continuing hands it re-raises with: this game's raises to
        bets, pulled toward a prior. Raising hands are taken as a cross-section of
        its continuing range (maniacs raise with anything)."""
        p = self.p
        raises = self.profile["raise"] if self.profile else 0
        continues = (self.profile["raise"] + self.profile["call"]) if self.profile else 0
        k = p["ev_fold_evidence"]
        return (raises + p["ev_raise_prior"] * k) / (continues + k)

    def respond(self, size, over_bet):
        """(chance it continues, our share against its continuing range) for a bet
        or raise of `size` x pot. over_bet: our action raises a bet already made."""
        p = self.p
        if self.stack <= 0:  # all in: it cannot fold
            return 1.0, self.equity()
        # Bigger bets need stronger hands to continue, without limit, but the
        # top of a range always continues; junk calls shrink once a bet
        # exceeds the pot (nobody calls a 10x pot shove with air 20% of the time).
        cut = min(p["ev_continue_cut_max"],
                  p["ev_continue_cut"] + self.call_shift
                  + p["range_size_slope"] * (size - 0.5)
                  + (p["range_raise_shift"] if over_bet else 0.0)
                  - (p["ev_oop_continue_shift"] if self.oop else 0.0))
        floor = p["ev_continue_floor"] / max(1.0, size)
        ceiling = p["ev_continue_ceiling"]
        q = floor + (ceiling - floor) * _sig((self.s - cut) / p["ev_continue_softness"])
        model_fold = float(self.w @ (1 - q))
        # This game's folds to our bets pull the modelled rate toward what it really does.
        faced = self.profile["faced_us"] if self.profile else 0
        folds = self.profile["fold_us"] if self.profile else 0
        k = p["ev_fold_evidence"]
        fold = (folds + model_fold * k) / (faced + k)
        cont = self.w * q
        share = float(cont @ self.e / cont.sum()) if cont.sum() > 0 else self.equity()
        return 1.0 - fold, share


def _bet_value(state, target, opps, realize, p):
    """EV of raising our street total to `target`: every opponent folds, calls or
    re-raises; we enumerate the combinations."""
    pot = state.pot
    ours = target - state.street_bets[state.seat]
    my_left = state.my_stack - ours
    responses = []
    for o in opps:
        size = (target - max(state.street_bets)) / max(1, state.pot + state.to_call)
        cont, share = o.respond(size, over_bet=max(state.street_bets) > 0)
        reraise = 0.0 if o.stack <= min(target - o.street_bet, o.stack) else cont * o.raise_rate()
        # A re-raise to a multiple of our bet costs us `extra` more to call.
        raise_to = min(o.street_bet + o.stack, p["ev_reraise_multiple"] * target)
        extra = max(0, min(raise_to - target, my_left))
        responses.append((cont - reraise, reraise, share, min(target - o.street_bet, o.stack),
                          raise_to - o.street_bet, extra))

    total = 0.0

    def walk(i, prob, share, added, callers, raised_extra):
        nonlocal total
        if prob == 0:
            return
        if i == len(responses):
            if callers == 0:
                total += prob * pot  # everyone folds: we win what is in the pot
            elif raised_extra:
                # Facing a re-raise: call when our share of the bigger pot pays, else give up our bet.
                call = realize * share * (pot + ours + raised_extra + added) - ours - raised_extra
                total += prob * max(-ours, call)
            else:
                total += prob * (realize * share * (pot + ours + added) - ours)
            return
        call_p, raise_p, eq, add, raise_add, extra = responses[i]
        walk(i + 1, prob * call_p, share * eq, added + add, callers + 1, raised_extra)
        walk(i + 1, prob * raise_p, share * eq, added + raise_add, callers + 1,
             max(raised_extra, extra))
        walk(i + 1, prob * (1 - call_p - raise_p), share, added, callers, raised_extra)

    walk(0, 1.0, 1.0, 0, 0, 0)
    return total


def _targets(state, p):
    """Distinct legal raise-to totals: pot fractions of the after-call pot, plus all in."""
    if not state.can_raise:
        return []
    sizes = p["ev_raise_sizes"] if state.to_call else p["ev_bet_sizes"]
    base = state.street_bets[state.seat] + state.to_call
    out = set()
    for f in sizes:
        t = base + f * (state.pot + state.to_call)
        out.add(min(state.max_raise_to, max(state.min_raise_to, int(ceil(t)))))
    if state.my_stack - state.to_call <= p["ev_allin_spr"] * (state.pot + state.to_call):
        out.add(state.max_raise_to)
    return sorted(out)


def best_size(table, tolerance_chips):
    """The smallest bet/raise target whose EV is within tolerance of the best one."""
    sizes = [k for k in table if isinstance(k, int)]
    if not sizes:
        return None
    top = max(table[k] for k in sizes)
    return min(k for k in sizes if table[k] >= top - tolerance_chips)


def choose(state, tracker, profiles, params, seed, extra_targets=()):
    """The EV-best postflop action and a table of every candidate's EV, or (None, None)
    when this spot is out of scope (too many opponents, too little time).
    extra_targets: more raise-to totals to score (the rule chain's own size)."""
    p = params
    opponents = [s for s, f in enumerate(state.folded) if s != state.seat and not f]
    if not opponents or len(opponents) > p["ev_max_opponents"]:
        return None, None
    started = perf_counter()
    rng = Random(seed)
    known = sum(1 << _parse_card(c) for c in list(state.hole) + list(state.board))
    valid = np.array([not (COMBO_MASKS[i] & known) for i in range(N)])
    strength, draws = board_strength(state.board)
    strength = np.minimum(1.0, np.nan_to_num(strength, nan=0.5) + p["range_draw_bonus"] * draws)

    picks = []
    for seat in opponents:
        profile = profile_of(state, seat, profiles)
        weights = None if is_shover(profile, p) else tracker.weights_for(seat, state.hole, state.board)
        if weights is None:
            weights = valid.astype(float)
        idx, w = _select(weights, valid, p["ev_max_combos"], rng)
        if not len(idx):
            return None, None
        picks.append((seat, idx, w, profile))
    combos = sorted({int(i) for _, idx, _, _ in picks for i in idx})
    deadline = started + p["ev_time_budget_ms"] / 1000
    runouts = _runouts(state.hole, state.board, p, rng)
    shares = _matchups(state.hole, state.board, combos, runouts, deadline,
                       min(p["ev_min_runouts"], len(runouts)))
    if shares is None:
        return None, None

    opps = []
    for seat, idx, w, profile in picks:
        shift = tracker.learned_for(seat)[1] - p["range_call_cut"]  # showdown-learned looseness
        opps.append(Opponent(seat, idx, w, shares, strength, state.stacks[seat],
                             state.street_bets[seat], profile, shift,
                             not in_position(state, seat), p))
    oop = any(o.oop for o in opps)
    realize = p["ev_realize_oop"] if oop else 1.0
    equity = float(np.prod([o.equity() for o in opps]))

    table = {}
    if state.to_call:
        table["fold"] = 0.0
        table["call"] = realize * equity * (state.pot + state.to_call) - state.to_call
    else:
        table["check"] = realize * equity * state.pot
    for target in sorted(set(_targets(state, p)) | set(extra_targets)):
        table[target] = _bet_value(state, target, opps, realize, p)

    passive = "call" if state.to_call and table["call"] > p["ev_call_margin"] * state.pot else (
        "fold" if state.to_call else "check")
    best = best_size(table, p["ev_size_tolerance"] * state.pot)
    if best is not None and table[best] > table[passive] + p["ev_bet_margin"] * state.pot:
        action = state.raise_to(best)
    elif passive == "call":
        action = state.call()
    elif passive == "check":
        action = state.check()
    else:
        action = state.fold()
    return action, {"table": table, "equity": equity, "realize": realize,
                    "ms": (perf_counter() - started) * 1000}
