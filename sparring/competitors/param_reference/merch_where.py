"""Generated fitted opponent: 'merch where'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'merch where'
    STYLE = {'vpip': 1.0, 'pfr': 1.0, 'threebet': 0.05, 'limp': 0.15000000000000002, 'aggression': 0.7000000000000001, 'cbet': 0.55, 'bluff': 0.8500000000000001, 'stickiness': 0.37, 'size': 0.315, 'adaptive': 1}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
