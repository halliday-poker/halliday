"""Generated fitted opponent: 'jongwon'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'jongwon'
    STYLE = {'vpip': 0.17, 'pfr': 0.17, 'threebet': 0.02, 'limp': 0.1, 'aggression': 0.2, 'cbet': 0.35000000000000003, 'bluff': 0.9500000000000001, 'stickiness': 0.44, 'size': 0.88, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
