"""Generated fitted opponent: 'idc'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'idc'
    STYLE = {'vpip': 0.15, 'pfr': 0.15, 'threebet': 0.03, 'limp': 0.15000000000000002, 'aggression': 0.5, 'cbet': 0.4, 'bluff': 0.35000000000000003, 'stickiness': 0.36, 'size': 0.9500000000000001, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
