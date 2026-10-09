"""Generated fitted opponent: 'luck is all u need'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'luck is all u need'
    STYLE = {'vpip': 0.17, 'pfr': 0.17, 'threebet': 0.03, 'limp': 0.15000000000000002, 'aggression': 0.2, 'cbet': 0.2, 'bluff': 0.2, 'stickiness': 0.33, 'size': 0.405, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
