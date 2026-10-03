"""Generated fitted opponent: 'tungbot'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'tungbot'
    STYLE = {'vpip': 0.23, 'pfr': 0.23, 'threebet': 0.06, 'limp': 0.2, 'aggression': 0.30000000000000004, 'cbet': 0.65, 'bluff': 1.0, 'stickiness': 0.2, 'size': 0.365, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
