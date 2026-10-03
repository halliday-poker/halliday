"""Generated fitted opponent: 'yep'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'yep'
    STYLE = {'vpip': 0.17, 'pfr': 0.17, 'threebet': 0.03, 'limp': 0.1, 'aggression': 0.7000000000000001, 'cbet': 0.7000000000000001, 'bluff': 0.30000000000000004, 'stickiness': 0.32, 'size': 0.745, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
