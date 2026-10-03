"""Generated fitted opponent: 'axiom'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'axiom'
    STYLE = {'vpip': 0.22, 'pfr': 0.22, 'threebet': 0.06, 'limp': 0.25, 'aggression': 0.7000000000000001, 'cbet': 0.05, 'bluff': 0.15000000000000002, 'stickiness': 0.35000000000000003, 'size': 0.925, 'adaptive': 1}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
