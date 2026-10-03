"""Generated fitted opponent: 'BigBaller'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'BigBaller'
    STYLE = {'vpip': 0.2, 'pfr': 0.2, 'threebet': 0.06, 'limp': 0.05, 'aggression': 0.2, 'cbet': 0.05, 'bluff': 0.5, 'stickiness': 0.59, 'size': 0.61, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
