"""The value-oriented baseline plus narrow field exploits (FIELD_EXPLOITS.md)."""

from collections import Counter
from hashlib import blake2b
import json
from math import ceil, isfinite

if __package__:
    from .engine import evaluate_hand
    from .opponents import fold_to_any, fold_to_us, is_station, profile_of, shrunk_rate
    from .params import DEFAULT_PARAMS, margin as pick
    from .preflop import in_position, pot_odds, preflop_plan
    from .standings import points_price
else:
    from engine import evaluate_hand
    from opponents import fold_to_any, fold_to_us, is_station, profile_of, shrunk_rate
    from params import DEFAULT_PARAMS, margin as pick
    from preflop import in_position, pot_odds, preflop_plan
    from standings import points_price


def mixed(state, frequency):
    """A repeatable coin flip from the visible spot, without global randomness."""
    if frequency >= 1:
        return True
    spot = json.dumps((sorted(state.hole), state.board, state.history))
    draw = int.from_bytes(blake2b(spot.encode(), digest_size=8).digest(), "big")
    return draw / 2 ** 64 < frequency


def safe_action(state):
    return state.check() if state.to_call == 0 else state.fold()


def legal_raise(state, target):
    """Raise-to is a street total; respect reopening and short all-in limits."""
    if not state.can_raise:
        return state.check() if state.to_call == 0 else state.call()
    target = min(state.max_raise_to, max(state.min_raise_to, int(ceil(target))))
    return state.raise_to(target)


def bet(state, fraction_of_pot):
    target = state.street_bets[state.seat] + state.to_call
    target += fraction_of_pot * (state.pot + state.to_call)
    return legal_raise(state, target)


def board_texture(board):
    ranks = {"23456789TJQKA".index(c[0]) + 2 for c in board}
    if 14 in ranks:
        ranks.add(1)
    connected = max((len(ranks & set(range(start, start + 5))) for start in range(1, 11)), default=0)
    suits = Counter(c[1] for c in board)
    return max(suits.values(), default=0) >= 2 or connected >= 3


def has_draw(hole, board):
    """A flush draw or open-ended/double-gutshot draw using a hole card."""
    if len(board) >= 5:
        return False
    cards = hole + board
    suits = Counter(c[1] for c in cards)
    if any(count == 4 and any(c[1] == suit for c in hole) for suit, count in suits.items()):
        return True
    ranks = {"23456789TJQKA".index(c[0]) + 2 for c in cards}
    own = {"23456789TJQKA".index(c[0]) + 2 for c in hole}
    if 14 in ranks:
        ranks.add(1)
    if 14 in own:
        own.add(1)
    missing = set()
    for start in range(1, 11):
        run = set(range(start, start + 5))
        if len(run - ranks) == 1 and run & own:
            missing.update(14 if r == 1 else r for r in run - ranks)
    return len(missing) >= 2


def call_margin(state, params, ranged, profile=None):
    """Equity a postflop call needs above the price, for model error."""
    opponents = [s for s, folded in enumerate(state.folded) if s != state.seat and not folded]
    street = {3: "flop", 4: "turn", 5: "river"}[len(state.board)]
    margin = pick(params, "call_margin_" + street, ranged)
    margin += max(0, len(opponents) - 1) * params["multiway_call_margin"]
    # Uniform-card equity overstates strength against a selective bettor.
    margin += pick(params, "large_bet_margin", ranged) * min(1.0, state.to_call / max(1, state.pot - state.to_call))
    if sum(a[0] == street and a[2] == "raise" for a in state.history) > 1:
        margin += pick(params, "reraise_margin", ranged)
    if params["bluffcatch"] and len(opponents) == 1 and profile:
        # A heads-up bettor who bets most of the time is bluffing often: call lighter.
        rate = shrunk_rate(profile.get("bets", 0), profile.get("bet_chances", 0),
                           params["bluffcatch_prior"], params["bluffcatch_prior_weight"])
        if rate >= params["bluffcatch_min_rate"]:
            margin -= params["bluffcatch_margin"]
    return margin


def decide(state, equity, opp_profiles=None, params=DEFAULT_PARAMS, ranged=False, standings=None):
    """Chip-EV decision, then reweighed in game points near the end of a game."""
    action = _decide(state, equity, opp_profiles, params, ranged, standings)
    if standings is None or equity is None or not isfinite(equity):
        return action
    try:
        return by_points(state, action, equity, opp_profiles, params, ranged, standings)
    except Exception:  # finishing-position play is an enhancement; never cost the action
        return action


def _decide(state, equity, opp_profiles=None, params=DEFAULT_PARAMS, ranged=False, standings=None):
    """Shared B interface. opp_profiles maps player id -> this game's counters.

    Equity is fractional showdown share against all live opponents,
    including all-ins. It is not chip EV or a model of future betting.
    ranged: equity was computed against tracked ranges rather than random
    cards, so the range-mode margins apply.
    """
    if not state.board:
        kind, target = preflop_plan(state, equity, params, opp_profiles, ranged, standings)
        if kind == "raise":
            return legal_raise(state, target)
        if kind == "call":
            return state.call() if state.to_call else state.check()
        return safe_action(state)
    # Everyone has the same unbeatable hand. With no rake, matching a bet
    # cannot lose chips, even if other players subsequently fold or call.
    if len(state.board) == 5 and evaluate_hand(state.board) == (8, 14):
        return state.call() if state.to_call else state.check()
    if equity is None or not isfinite(equity):
        return safe_action(state)
    opponents = [s for s, folded in enumerate(state.folded) if s != state.seat and not folded]
    n = len(opponents)
    extra = max(0, n - 1)
    value = min(0.85, params["value_threshold"] + extra * params["multiway_value_margin"])
    raise_value = min(0.97, params["raise_threshold"] + extra * params["multiway_raise_margin"])
    fraction = params["size_wet"] if board_texture(state.board) else params["size_dry"]
    can_bet = state.can_raise and any(state.stacks[s] > 0 for s in opponents)
    street = {3: "flop", 4: "turn", 5: "river"}[len(state.board)]
    raises = [a for a in state.history if a[0] == "preflop" and a[2] == "raise"]
    aggressor = raises[-1][1] if raises else None
    villain = opponents[0] if n == 1 else None
    profile = profile_of(state, villain, opp_profiles) if villain is not None else None
    station = villain is not None and is_station(profile, params)
    if params["station_value"] and station:
        # Stations call too much: bet thinner and bigger for value.
        value -= params["station_value_delta"]
        fraction = params["station_value_size"]
    # Heads-up flop as the preflop raiser: ladder bots fold ~74% to a
    # pot-sized c-bet almost regardless of their hand, so bet pot with
    # everything (one size for value and air) unless they never fold.
    cbet_spot = villain is not None and street == "flop" and aggressor == state.seat
    # Turn after our heads-up flop c-bet was called: the field folds ~70% to a
    # pot-sized second barrel (21% to a third of pot), and big bets fold out
    # air, draws and weak pairs while top pair+ calls.
    flop_bettors = [a[1] for a in state.history if a[0] == "flop" and a[2] == "raise"]
    barrel_spot = (params["turn_barrel"] and villain is not None and street == "turn"
                   and aggressor == state.seat and flop_bettors == [state.seat])
    # Heads-up turn/river when we did not bet the previous street: the field
    # folds ~78% to a pot bet here, but only ~half once it called our last bet.
    prev = {"turn": "flop", "river": "turn"}.get(street)
    prev_bettors = [a[1] for a in state.history if a[0] == prev and a[2] == "raise"]
    stab_spot = (params["stab"] and villain is not None and prev is not None
                 and state.seat not in prev_bettors)
    # Heads-up turn/river bets are pot-sized, value and bluffs alike: the
    # field pays off big value bets (bettor EV rises with size up to pot).
    late_hu = villain is not None and street != "flop"
    if not state.to_call:
        if can_bet and equity >= value:
            if equity >= params["shove_equity"] and state.my_stack <= params["shove_spr"] * state.pot:
                return legal_raise(state, state.max_raise_to)
            if cbet_spot:
                return bet(state, params["cbet_pot_fraction"])
            return bet(state, params["late_pot_fraction"] if late_hu else fraction)
        own_pair = (state.hole[0][0] == state.hole[1][0]
                    or bool({c[0] for c in state.hole} & {c[0] for c in state.board}))
        made_or_draw = own_pair or has_draw(state.hole, state.board)
        # Pure air bets only while this opponent still folds to our bets
        # often enough to pay for a pot-sized bluff, and to anyone's bets
        # often enough (rarely-folding players lose bluffs from either), and
        # then only some of the time so a watching opponent cannot assume
        # every bet is a bluff.
        bluff = (fold_to_us(profile, params) >= params["bluff_min_fold"]
                 and fold_to_any(profile, params) >= params["bluff_min_fold_any"]
                 and mixed(state, params["bluff_frequency"]))
        # Air only bets in position: the field folds 83% to an in-position
        # pot bet but 55% when we act first (45% to an OOP turn barrel).
        air_ok = villain is not None and in_position(state, villain)
        if can_bet and cbet_spot and not station and (made_or_draw or (bluff and air_ok)):
            return bet(state, params["cbet_pot_fraction"])
        # Barrel air and draws at the value size; weak pairs keep their
        # showdown value and check.
        if can_bet and barrel_spot and not station and bluff and (air_ok or made_or_draw) and (
                params["barrel_weak_pairs"] if own_pair else params["barrel_bluffs"]):
            return bet(state, params["late_pot_fraction"])
        if can_bet and stab_spot and not own_pair and not station and bluff:
            return bet(state, params["late_pot_fraction"])
        # Against a station, only the modest c-bet with a pair or draw.
        if can_bet and cbet_spot and equity >= params["cbet_equity"] and made_or_draw:
            return bet(state, params["size_dry"])
        return state.check()

    price = points_price(state, standings)
    price = pot_odds(state) if price is None else price
    margin = call_margin(state, params, ranged, profile)
    if can_bet and equity >= raise_value:
        if equity >= params["shove_equity"] and state.my_stack <= params["shove_spr"] * (state.pot + state.to_call):
            return legal_raise(state, state.max_raise_to)
        return bet(state, params["raise_pot_fraction"])
    return state.call() if equity >= price + margin else state.fold()


def by_points(state, action, equity, opp_profiles, params, ranged, standings):
    """Near the end of a game, swap the chip-EV action for a safer or bolder
    one when that is worth clearly more expected game points (standings.py).
    Call/fold is already priced in points; this weighs check or call against
    the proposed bet, a pot-sized bet and all-in. Bolder actions than the
    proposal are only considered heads-up, where the fold estimate is ours."""
    if (not params["endgame_bets"] or not standings.active(state)
            or action.kind == "fold" or not state.can_raise):
        return action
    villain = standings.favourite(state)
    if villain is None or state.stacks[villain] == 0:
        return action
    opponents = [s for s, folded in enumerate(state.folded) if s != state.seat and not folded]
    heads_up = len(opponents) == 1
    if state.board:
        profile = profile_of(state, villain, opp_profiles) if heads_up else None
        margin = call_margin(state, params, ranged, profile) if state.to_call else 0.0
    else:
        margin = pick(params, "preflop_call_margin", ranged) if state.to_call else 0.0
    shown = max(0.0, equity - margin)
    fold = standings.fold_chance(state, opp_profiles)
    passive = state.call() if state.to_call else state.check()

    def target(a):
        return min(state.max_raise_to, max(state.min_raise_to, a.amount))

    def score(a):
        if a.kind == "raise":
            return standings.raise_points(state, target(a), equity, fold)
        return standings.passive_points(state, shown)

    options = [passive, state.raise_to(state.max_raise_to)]
    if action.kind == "raise":
        options.append(state.raise_to(target(action)))
    elif heads_up and state.board:
        pot_bet = state.street_bets[state.seat] + state.to_call + (state.pot + state.to_call)
        options.append(state.raise_to(min(state.max_raise_to, max(state.min_raise_to, pot_bet))))
    if not heads_up or not state.board:
        # Multiway or preflop: only ever step down from the proposal.
        size = target(action) if action.kind == "raise" else 0
        options = [a for a in options if a.kind != "raise" or target(a) <= size]
    points = {a: score(a) for a in [action] + options}
    # The same outcomes valued linearly: what chip EV alone would say. Only
    # the bend in the points curve, which the chip strategy cannot see, may
    # overturn it, so a switch needs both a clear points gain and a clear
    # gain over the linear view.
    standings.linearise(state)
    try:
        linear = {a: score(a) for a in points}
    finally:
        standings.linearise(None)
    hysteresis = params["endgame_hysteresis"]
    best, best_gain = action, 0.0
    for a in options:
        gain = points[a] - points[action]
        bend = gain - (linear[a] - linear[action])
        if gain > hysteresis and bend > hysteresis and gain > best_gain:
            best, best_gain = a, gain
    return best
