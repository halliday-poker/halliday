"""Generated fitted opponent: 'guaguanco 3'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'guaguanco 3'
    STYLE = {'vpip': 0.0, 'pfr': 0.0, 'threebet': 0.0, 'limp': 0.05, 'aggression': 0.0, 'cbet': 0.65, 'bluff': 0.0, 'stickiness': 1.0, 'size': 0.66, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
