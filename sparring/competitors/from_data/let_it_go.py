"""Generated fitted opponent: 'let it go'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'let it go'
    STYLE = {'vpip': 0.06, 'pfr': 0.0, 'threebet': 0.0, 'limp': 0.05, 'aggression': 0.0, 'cbet': 0.0, 'bluff': 0.15000000000000002, 'stickiness': 0.01, 'size': 0.435, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
