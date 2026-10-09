"""Generated fitted opponent: 'Thanos'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Thanos'
    STYLE = {'vpip': 0.19, 'pfr': 0.19, 'threebet': 0.07, 'limp': 0.05, 'aggression': 0.5, 'cbet': 0.2, 'bluff': 0.35000000000000003, 'stickiness': 0.87, 'size': 0.665, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
