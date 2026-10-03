"""Generated fitted opponent: 'guaguanco 5'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'guaguanco 5'
    STYLE = {'vpip': 0.16, 'pfr': 0.16, 'threebet': 0.02, 'limp': 0.05, 'aggression': 0.65, 'cbet': 0.5, 'bluff': 1.0, 'stickiness': 0.34, 'size': 0.875, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
