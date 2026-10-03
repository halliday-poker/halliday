"""The value-oriented baseline plus narrow field exploits (FIELD_EXPLOITS.md)."""

from collections import Counter
from hashlib import blake2b
import json
from math import ceil, isfinite

if __package__:
    from .engine import evaluate_hand
    from .opponents import fold_to_us, is_station, profile_of
    from .params import DEFAULT_PARAMS
    from .preflop import pot_odds, preflop_plan
else:
    from engine import evaluate_hand
    from opponents import fold_to_us, is_station, profile_of
    from params import DEFAULT_PARAMS
    from preflop import pot_odds, preflop_plan


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


def decide(state, equity, opp_profiles=None, params=DEFAULT_PARAMS):
    """Shared B interface. opp_profiles maps player id -> this game's counters.

    Equity is fractional showdown share against all live opponents,
    including all-ins. It is not chip EV or a model of future betting.
    """
    if not state.board:
        kind, target = preflop_plan(state, equity, params, opp_profiles)
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
    if not state.to_call:
        if can_bet and equity >= value:
            if equity >= params["shove_equity"] and state.my_stack <= params["shove_spr"] * state.pot:
                return legal_raise(state, state.max_raise_to)
            return bet(state, params["cbet_pot_fraction"] if cbet_spot else fraction)
        own_pair = (state.hole[0][0] == state.hole[1][0]
                    or bool({c[0] for c in state.hole} & {c[0] for c in state.board}))
        made_or_draw = own_pair or has_draw(state.hole, state.board)
        # Pure air bets only while this opponent still folds to our bets
        # often enough to pay for a pot-sized bluff, and then only some of
        # the time so a watching opponent cannot assume every bet is a bluff.
        bluff = (fold_to_us(profile, params) >= params["bluff_min_fold"]
                 and mixed(state, params["bluff_frequency"]))
        if can_bet and cbet_spot and not station and (made_or_draw or bluff):
            return bet(state, params["cbet_pot_fraction"])
        # Against a station, only the modest c-bet with a pair or draw.
        if can_bet and cbet_spot and equity >= params["cbet_equity"] and made_or_draw:
            return bet(state, params["size_dry"])
        return state.check()

    price = pot_odds(state)
    street_raises = sum(a[0] == street and a[2] == "raise" for a in state.history)
    if villain is not None and street == "flop" and aggressor == villain and street_raises == 1:
        # Facing their heads-up flop c-bet: ~56% of ladder c-bets are air
        # and their ranges are wide, so uniform-card equity is roughly
        # right. Drop the big-bet and street margins.
        margin = params["cbet_defence_margin"]
    else:
        margin = params["call_margin_" + street] + extra * params["multiway_call_margin"]
        # Uniform-card equity overstates strength against a selective bettor.
        margin += params["large_bet_margin"] * min(1.0, state.to_call / max(1, state.pot - state.to_call))
        if street_raises > 1:
            margin += params["reraise_margin"]
    if can_bet and equity >= raise_value:
        if equity >= params["shove_equity"] and state.my_stack <= params["shove_spr"] * (state.pot + state.to_call):
            return legal_raise(state, state.max_raise_to)
        return bet(state, params["raise_pot_fraction"])
    return state.call() if equity >= price + margin else state.fold()
