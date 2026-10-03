"""Generated fitted opponent: 'Halliday'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Halliday'
    STYLE = {'vpip': 0.14, 'pfr': 0.14, 'threebet': 0.03, 'limp': 0.1, 'aggression': 0.5, 'cbet': 0.65, 'bluff': 0.2, 'stickiness': 1.0, 'size': 0.71, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
