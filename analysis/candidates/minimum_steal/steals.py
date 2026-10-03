"""Experimental small-open counters and late-position steal gate.

Copied into isolated candidates as steals.py. It uses public events from the
current game only. The fold-only break-even calculation is a screening rule,
not a complete EV estimate: later betting and correlated defenses can matter.
"""
from hashlib import blake2b
import json

if __package__:
    from .opponents import OpponentTracker, profile_of
else:
    from opponents import OpponentTracker, profile_of


class StealTracker(OpponentTracker):
    def __init__(self):
        super().__init__()
        self._open_to = 0
        self._voluntary = set()
        self._open_responded = set()

    def on_hand_start(self, info):
        super().on_hand_start(info)
        self._open_to = 0
        self._voluntary = set()
        self._open_responded = set()

    def on_action(self, event):
        try:
            if event['street'] == 'preflop':
                player = event['players'][event['seat']]
                kind = event['action']
                if (self._preflop_raises == 1 and 2 < self._open_to <= 6
                        and kind in ('fold', 'call', 'raise')
                        and player not in self._voluntary
                        and player not in self._open_responded):
                    self.profiles[player]['open_faced'] += 1
                    self.profiles[player]['open_fold'] += kind == 'fold'
                    self._open_responded.add(player)
                if kind == 'raise' and self._preflop_raises == 0:
                    self._open_to = event['amount']
                if kind in ('call', 'raise'):
                    self._voluntary.add(player)
        except (KeyError, IndexError, TypeError):
            pass
        super().on_action(event)


def steal_probability(state, profiles, params):
    if not state.can_raise or state.board:
        return 0.
    offset = (state.seat - state.button) % state.num_players
    if offset not in (0, 1) and not (state.num_players >= 4 and offset == state.num_players - 1):
        return 0.
    if any(a[0] == 'preflop' and a[2] in ('call', 'raise') for a in state.history):
        return 0.
    opponents = [s for s, folded in enumerate(state.folded) if not folded and s != state.seat]
    if not 1 <= len(opponents) <= params['steal_max_opponents']:
        return 0.
    all_fold = 1.
    for seat in opponents:
        profile = profile_of(state, seat, profiles)
        if state.stacks[seat] <= 0 or not profile or profile['open_faced'] < params['steal_min_faced']:
            return 0.
        count = profile['open_faced']
        rate = (profile['open_fold'] + params['steal_prior_weight'] * params['steal_fold_prior']) / (count + params['steal_prior_weight'])
        all_fold *= rate
    target = round(params['big_blind'] * params['steal_open_bb'])
    if not state.min_raise_to <= target <= state.max_raise_to:
        return 0.
    risk = target - state.street_bets[state.seat]
    fold_only_ev = all_fold * state.pot - (1 - all_fold) * risk
    return params['steal_frequency'] if fold_only_ev >= params['steal_min_ev'] else 0.


def should_steal(state, profiles, params):
    probability = steal_probability(state, profiles, params)
    if probability <= 0:
        return False
    if probability >= 1:
        return True
    spot = json.dumps(('preflop-steal', sorted(state.hole), state.history))
    draw = int.from_bytes(blake2b(spot.encode(), digest_size=8).digest(), 'big') / 2**64
    return draw < probability
