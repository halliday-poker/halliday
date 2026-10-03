"""Generated fitted opponent: 'RaiseYourEdge'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'RaiseYourEdge'
    STYLE = {'vpip': 0.15, 'pfr': 0.15, 'threebet': 0.05, 'limp': 0.15000000000000002, 'aggression': 0.35000000000000003, 'cbet': 0.30000000000000004, 'bluff': 0.6000000000000001, 'stickiness': 0.24, 'size': 0.89, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
