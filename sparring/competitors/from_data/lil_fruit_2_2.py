"""Generated fitted opponent: 'lil-fruit 2.2'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'lil-fruit 2.2'
    STYLE = {'vpip': 0.9500000000000001, 'pfr': 0.89, 'threebet': 0.01, 'limp': 0.2, 'aggression': 0.2, 'cbet': 0.25, 'bluff': 0.1, 'stickiness': 0.35000000000000003, 'size': 0.88, 'adaptive': 1}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
