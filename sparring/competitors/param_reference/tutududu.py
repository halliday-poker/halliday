"""Generated fitted opponent: 'tutududu'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'tutududu'
    STYLE = {'vpip': 0.18, 'pfr': 0.18, 'threebet': 0.05, 'limp': 0.0, 'aggression': 0.7000000000000001, 'cbet': 0.7000000000000001, 'bluff': 0.45, 'stickiness': 1.0, 'size': 0.445, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
