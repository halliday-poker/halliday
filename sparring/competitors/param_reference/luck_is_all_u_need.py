"""Generated fitted opponent: 'luck is all u need'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'luck is all u need'
    STYLE = {'vpip': 0.13, 'pfr': 0.13, 'threebet': 0.03, 'limp': 0.1, 'aggression': 0.5, 'cbet': 0.15000000000000002, 'bluff': 0.05, 'stickiness': 0.23, 'size': 0.63, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
