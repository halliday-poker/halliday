"""Fixed 169-class preflop tables for the 1/2 blind, 100 bb game.

These are simple starting ranges, not solver-derived charts. No opponent
identity or game score is used; this game's shove counts (opponents.py)
only widen calls against a proven shover.
"""

if __package__:
    from .opponents import is_shover, profile_of
    from .params import margin
else:
    from opponents import is_shover, profile_of
    from params import margin

RANKS = "23456789TJQKA"


def expand_range(spec):
    """Expand pairs / suited / offsuit classes with optional +.

    77+ raises the pair rank; A9s+ keeps A fixed and raises the kicker.
    Ranges such as A5s-A2s and unspecified suitedness are invalid.
    """
    result = set()
    for token in spec.split(","):
        token = token.strip()
        if not token:
            raise ValueError("Empty range token")
        plus = token.endswith("+")
        base = token[:-1] if plus else token
        if len(base) not in (2, 3) or any(r not in RANKS for r in base[:2]):
            raise ValueError(f"Invalid hand class: {token}")
        hi, lo = map(RANKS.index, base[:2])
        if len(base) == 2 and hi == lo:
            result.update(RANKS[i] * 2 for i in range(hi, 13) if plus or i == hi)
        elif len(base) == 3 and base[2] in "so" and hi > lo:
            result.update(RANKS[hi] + RANKS[i] + base[2]
                          for i in range(lo, hi) if plus or i == lo)
        else:
            raise ValueError(f"Invalid hand class: {token}")
    return frozenset(result)


def hand_class(hole):
    first, second = sorted(hole, key=lambda c: RANKS.index(c[0]), reverse=True)
    ranks = first[0] + second[0]
    return ranks if first[0] == second[0] else ranks + ("s" if first[1] == second[1] else "o")


# Position depends on players dealt in, not on who folded.
OPEN_RANGES = {
    "early": expand_range("66+,A5s,A4s,ATs+,KTs+,QTs+,JTs,T9s,AJo+,KQo"),
    "middle": expand_range("55+,A2s+,KTs+,QTs+,JTs,T9s,98s,ATo+,KJo+,QJo"),
    "cutoff": expand_range("22+,A2s+,K8s+,Q9s+,J9s+,T8s+,98s,87s,76s,A9o+,KTo+,QTo+,JTo"),
    "button": expand_range("22+,A2s+,K2s+,Q5s+,J7s+,T7s+,97s+,86s+,75s+,65s,54s,A2o+,K8o+,Q9o+,J9o+,T9o"),
    "small_blind": expand_range("22+,A2s+,K5s+,Q8s+,J8s+,T8s+,98s,87s,76s,65s,A5o+,K9o+,QTo+,JTo"),
    "heads_up": expand_range("22+,A2s+,K2s+,Q2s+,J4s+,T6s+,96s+,85s+,74s+,64s+,53s+,43s,A2o+,K2o+,Q7o+,J8o+,T8o+,98o,87o"),
}
THREE_BET = expand_range("JJ+,AQs+,AKo")
THREE_BET_LATE = expand_range("TT+,AJs+,KQs,AQo+")
CALL_OPEN = expand_range("22+,ATs+,KJs+,QJs,JTs,T9s,AQo+")
CALL_OPEN_LATE = expand_range("22+,A2s+,KTs+,QTs+,JTs,T9s,98s,87s,ATo+,KQo")
BB_DEFEND = expand_range("22+,A2s+,K5s+,Q8s+,J8s+,T8s+,97s+,86s+,75s+,65s,54s,A8o+,KTo+,QTo+,JTo")
# Ladder 3-bets are light (about half are outside the top 30%) but the field
# folds only ~19% to 4-bets: value 4-bet wider, flat wider in position, and
# never 4-bet bluff.
FOUR_BET = expand_range("QQ+,AKs,AKo")
CALL_THREE_BET = expand_range("TT+,AQs+,AKo")
CALL_THREE_BET_IP = expand_range("77+,AJs+,KQs,AQo+")
LARGE_CALL = expand_range("QQ+,AKs,AKo")


def position(state, seat=None):
    seat = state.seat if seat is None else seat
    pos = (seat - state.button) % state.num_players
    if state.num_players == 2:
        return "heads_up" if pos == 0 else "big_blind"
    if pos == 0:
        return "button"
    if pos == 1:
        return "small_blind"
    if pos == 2:
        return "big_blind"
    if pos == state.num_players - 1:
        return "cutoff"
    return "early" if pos <= state.num_players - 3 else "middle"


def in_position(state, opponent):
    """Postflop order, including the heads-up button/small-blind exception."""
    order = lambda seat: (seat - state.button - 1) % state.num_players
    return order(state.seat) > order(opponent)


def pot_odds(state):
    """Exclude current-street chips above hero's possible all-in call.

    Earlier streets have already been matched by a hero who can still act.
    Equity versus all live opponents remains conservative for side pots
    which a shorter all-in opponent cannot contest.
    """
    cap = state.street_bets[state.seat] + state.to_call
    excess = sum(max(0, amount - cap) for amount in state.street_bets)
    return state.to_call / max(1, state.pot + state.to_call - excess)


def preflop_plan(state, equity, params, opp_profiles=None, ranged=False):
    """Return (kind, desired raise-to) for the legal-action wrapper."""
    hand, pos = hand_class(state.hole), position(state)
    raises = [a for a in state.history if a[0] == "preflop" and a[2] == "raise"]
    bb = params["big_blind"]
    current = max(state.street_bets)
    passive = ("check", 0) if state.to_call == 0 else ("fold", 0)
    if not raises:
        limpers = sum(a[0] == "preflop" and a[2] == "call" for a in state.history)
        opening = OPEN_RANGES["cutoff" if pos == "big_blind" else pos]
        if hand in opening:
            return "raise", round(bb * (params["open_bb"] + params["limper_bb"] * limpers))
        return passive

    # The whitelist guards against treating every huge raise as random cards.
    if current >= bb * params["large_bet_bb"] or len(raises) >= 3:
        if hand == "AA":
            return "raise", state.max_raise_to
        price = pot_odds(state)
        if hand in LARGE_CALL and equity is not None and equity >= price + margin(params, "preflop_call_margin", ranged):
            return "call", 0
        # A proven shover's all-in is close to random cards, which is what
        # the equity estimate assumes, so any hand beating the price calls.
        # Not when someone else has already called the shove.
        shove = raises[-1]
        shover = shove[1]
        called = any(a[0] == "preflop" and a[2] == "call"
                     for a in state.history[state.history.index(shove) + 1:])
        if (state.stacks[shover] == 0 and not called and equity is not None
                and is_shover(profile_of(state, shover, opp_profiles), params)
                and equity >= price + params["shover_call_margin"]):
            return "call", 0
        return passive

    raiser = raises[-1][1]
    if len(raises) == 1:
        late = position(state, raiser) in ("button", "small_blind", "heads_up", "cutoff")
        if hand in (THREE_BET_LATE if late else THREE_BET):
            factor = params["threebet_ip"] if in_position(state, raiser) else params["threebet_oop"]
            callers = sum(a[0] == "preflop" and a[2] == "call"
                          for a in state.history[state.history.index(raises[-1]) + 1:])
            return "raise", round(current * (factor + callers))
        calling = CALL_OPEN_LATE if late else CALL_OPEN
        if pos == "big_blind" and current <= 3 * bb:
            calling = BB_DEFEND
        if hand in calling and current <= bb * params["max_open_call_bb"]:
            return "call", 0
    else:
        if hand in FOUR_BET:
            return "raise", round(current * params["fourbet_multiplier"])
        calling = CALL_THREE_BET_IP if in_position(state, raiser) else CALL_THREE_BET
        if hand in calling and current <= bb * params["max_threebet_call_bb"]:
            return "call", 0
    return passive
