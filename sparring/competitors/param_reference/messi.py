"""Generated fitted opponent: 'Messi'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Messi'
    STYLE = {'vpip': 0.1, 'pfr': 0.01, 'threebet': 0.0, 'limp': 0.9500000000000001, 'aggression': 0.0, 'cbet': 0.15000000000000002, 'bluff': 0.15000000000000002, 'stickiness': 0.0, 'size': 0.435, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
