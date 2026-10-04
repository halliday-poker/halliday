"""The value-oriented baseline plus narrow field exploits (FIELD_EXPLOITS.md)."""

from collections import Counter
from hashlib import blake2b
import json
from math import ceil, isfinite

if __package__:
    from .engine import evaluate_hand
    from .opponents import fold_to_any, fold_to_us, is_station, profile_of
    from .params import DEFAULT_PARAMS, margin as pick
    from .preflop import in_position, pot_odds, preflop_plan
else:
    from engine import evaluate_hand
    from opponents import fold_to_any, fold_to_us, is_station, profile_of
    from params import DEFAULT_PARAMS, margin as pick
    from preflop import in_position, pot_odds, preflop_plan


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


def decide(state, equity, opp_profiles=None, params=DEFAULT_PARAMS, ranged=False):
    """Shared B interface. opp_profiles maps player id -> this game's counters.

    Equity is fractional showdown share against all live opponents,
    including all-ins. It is not chip EV or a model of future betting.
    ranged: equity was computed against tracked ranges rather than random
    cards, so the range-mode margins apply.
    """
    if not state.board:
        kind, target = preflop_plan(state, equity, params, opp_profiles, ranged)
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
        # Flop c-bets are the exception at short tables, where an OOP pot
        # c-bet still gets 65% folds (4-6 seats; 58% at 8).
        air_ok = villain is not None and in_position(state, villain)
        cbet_air_ok = air_ok or state.num_players <= params["oop_cbet_max_seats"]
        if can_bet and cbet_spot and not station and (made_or_draw or (bluff and cbet_air_ok)):
            return bet(state, params["cbet_pot_fraction"])
        # Barrel air and draws at the value size; weak pairs keep their
        # showdown value and check.
        if can_bet and barrel_spot and not station and bluff and (air_ok or made_or_draw) and (
                params["barrel_weak_pairs"] if own_pair else params["barrel_bluffs"]):
            return bet(state, params["late_pot_fraction"])
        if can_bet and stab_spot and not own_pair and not station and bluff:
            return bet(state, params["late_pot_fraction"])
        # Heads-up limped flop: the field folds 87-89% to a pot bet when
        # checked to and 67-69% when we act first.
        limp_spot = params["limp_stab"] and villain is not None and street == "flop" and aggressor is None
        if can_bet and limp_spot and not station and bluff:
            return bet(state, params["cbet_pot_fraction"])
        # Against a station, only the modest c-bet with a pair or draw.
        if can_bet and cbet_spot and equity >= params["cbet_equity"] and made_or_draw:
            return bet(state, params["size_dry"])
        return state.check()

    price = pot_odds(state)
    street_raises = sum(a[0] == street and a[2] == "raise" for a in state.history)
    margin = pick(params, "call_margin_" + street, ranged) + extra * params["multiway_call_margin"]
    # Uniform-card equity overstates strength against a selective bettor.
    margin += pick(params, "large_bet_margin", ranged) * min(1.0, state.to_call / max(1, state.pot - state.to_call))
    if street_raises > 1:
        margin += pick(params, "reraise_margin", ranged)
    if can_bet and equity >= raise_value:
        if equity >= params["shove_equity"] and state.my_stack <= params["shove_spr"] * (state.pot + state.to_call):
            return legal_raise(state, state.max_raise_to)
        return bet(state, params["raise_pot_fraction"])
    return state.call() if equity >= price + margin else state.fold()
