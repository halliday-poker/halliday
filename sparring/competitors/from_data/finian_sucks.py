"""Generated fitted opponent: 'finian sucks'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'finian sucks'
    STYLE = {'vpip': 0.03, 'pfr': 0.02, 'threebet': 0.02, 'limp': 0.9, 'aggression': 0.9500000000000001, 'cbet': 0.0, 'bluff': 0.05, 'stickiness': 0.11, 'size': 0.5449999999999999, 'adaptive': 1}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
