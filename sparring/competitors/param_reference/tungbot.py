"""Generated fitted opponent: 'tungbot'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'tungbot'
    STYLE = {'vpip': 0.22, 'pfr': 0.22, 'threebet': 0.06, 'limp': 0.2, 'aggression': 0.25, 'cbet': 0.65, 'bluff': 1.0, 'stickiness': 0.24, 'size': 0.365, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
