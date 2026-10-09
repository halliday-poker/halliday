"""Generated fitted opponent: 'radishv1'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'radishv1'
    STYLE = {'vpip': 0.38, 'pfr': 0.38, 'threebet': 0.02, 'limp': 0.5, 'aggression': 0.2, 'cbet': 0.4, 'bluff': 0.2, 'stickiness': 0.35000000000000003, 'size': 0.71, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
