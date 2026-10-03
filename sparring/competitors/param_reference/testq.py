"""Generated fitted opponent: 'testQ'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'testQ'
    STYLE = {'vpip': 0.24, 'pfr': 0.17, 'threebet': 0.02, 'limp': 0.8, 'aggression': 0.2, 'cbet': 0.7000000000000001, 'bluff': 0.45, 'stickiness': 0.26, 'size': 0.6799999999999999, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
