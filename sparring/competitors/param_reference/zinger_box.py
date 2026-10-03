"""Generated fitted opponent: 'zinger box'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'zinger box'
    STYLE = {'vpip': 0.38, 'pfr': 0.38, 'threebet': 0.03, 'limp': 0.15000000000000002, 'aggression': 0.5, 'cbet': 0.5, 'bluff': 0.05, 'stickiness': 0.4, 'size': 0.645, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
