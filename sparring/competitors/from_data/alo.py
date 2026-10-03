"""Generated fitted opponent: 'alo'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'alo'
    STYLE = {'vpip': 1.0, 'pfr': 1.0, 'threebet': 1.0, 'limp': 0.0, 'aggression': 0.6000000000000001, 'cbet': 0.65, 'bluff': 0.15000000000000002, 'stickiness': 0.45, 'size': 0.66, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
