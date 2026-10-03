"""Generated fitted opponent: 'guaguanco 4'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'guaguanco 4'
    STYLE = {'vpip': 0.16, 'pfr': 0.16, 'threebet': 0.05, 'limp': 0.1, 'aggression': 0.7000000000000001, 'cbet': 0.5, 'bluff': 1.0, 'stickiness': 0.73, 'size': 0.85, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
