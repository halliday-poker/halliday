"""Generated fitted opponent: 'Halliday'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Halliday'
    STYLE = {'vpip': 0.14, 'pfr': 0.14, 'threebet': 0.03, 'limp': 0.1, 'aggression': 0.5, 'cbet': 0.5, 'bluff': 0.25, 'stickiness': 1.0, 'size': 0.755, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
