"""Generated fitted opponent: 'netanyahu'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'netanyahu'
    STYLE = {'vpip': 0.23, 'pfr': 0.23, 'threebet': 0.03, 'limp': 0.1, 'aggression': 1.0, 'cbet': 1.0, 'bluff': 1.0, 'stickiness': 0.0, 'size': 0.35, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
