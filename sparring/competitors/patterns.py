"""Public prefix features shared by fitting and offline simulation; no Torch."""
from collections import deque
import numpy as np

HISTORY = ('score', 'rank', 'leader_gap', 'last_result', 'recent_result', 'loss_streak',
           'own_vpip', 'own_pfr', 'opponent_vpip', 'opponent_pfr',
           'opponent_shove', 'opponent_fold_share')
PROGRESS = ('hand_fraction', 'hand_squared', 'after_10', 'after_25', 'after_50', 'after_75', 'after_90')


def progress_features(hands):
    h = np.asarray(hands)
    t = np.minimum(h, 99)/99
    return np.column_stack([t, t*t, *(h >= cut for cut in (10, 25, 50, 75, 90))]).astype(np.float32)


class PublicHistory:
    """State changes only after a hand ends; never accepts hole cards."""
    def __init__(self, names):
        self.names = names
        self.hands = 0
        self.score = dict.fromkeys(names, 0)
        self.recent = {name: deque(maxlen=5) for name in names}
        self.streak = dict.fromkeys(names, 0)
        # Dealt hands, VPIP hands, PFR hands, preflop shove hands, actions, folds.
        self.counts = {name: np.zeros(6) for name in names}

    def before(self, name):
        own = self.counts[name]
        others = [other for other in self.names if other != name]
        opp = sum((self.counts[other] for other in others), np.zeros(6))
        own_score = self.score[name]
        rank = sum((self.score[other] < own_score) + .5*(self.score[other] == own_score)
                   for other in others)/len(others)
        recent = self.recent[name]
        return np.asarray([
            np.clip(own_score/1000, -5, 5), rank,
            np.clip((max(self.score.values())-own_score)/1000, 0, 10),
            np.clip((recent[-1] if recent else 0)/200, -1, 8),
            np.clip(sum(recent)/1000, -1, 8), min(self.streak[name], 10)/10,
            (own[1]+2.2)/(own[0]+10), (own[2]+1.8)/(own[0]+10),
            (opp[1]+2.2*len(others))/(opp[0]+10*len(others)),
            (opp[2]+1.8*len(others))/(opp[0]+10*len(others)),
            (opp[3]+.2*len(others))/(opp[0]+10*len(others)),
            (opp[5]+3*len(others))/(opp[4]+10*len(others)),
        ], dtype=np.float32)

    def finish(self, actions, deltas):
        if set(deltas) != set(self.names) or sum(deltas.values()) != 0:
            raise ValueError('Invalid public hand settlement')
        measurements = {}
        for name in self.names:
            rows = [e for e in actions if e['bot'] == name]
            pre = [e for e in rows if e['street'] == 'preflop']
            vpip = any(e['action'] in ('call', 'raise') for e in pre)
            pfr = any(e['action'] == 'raise' for e in pre)
            shoved = any(e['action'] == 'raise' and e['amount'] == 200 for e in pre)
            folds = sum(e['action'] == 'fold' for e in rows)
            self.counts[name] += [1, vpip, pfr, shoved, len(rows), folds]
            self.score[name] += deltas[name]
            self.recent[name].append(deltas[name])
            self.streak[name] = self.streak[name]+1 if deltas[name] < 0 else 0
            measurements[name] = (deltas[name], int(vpip), int(pfr), folds)
        self.hands += 1
        return measurements

