"""Generated fitted opponent: 'lil-fruit'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'lil-fruit'
    STYLE = {'vpip': 1.0, 'pfr': 0.06, 'threebet': 0.03, 'limp': 0.25, 'aggression': 0.5, 'cbet': 0.0, 'bluff': 0.0, 'stickiness': 0.23, 'size': 0.955, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
