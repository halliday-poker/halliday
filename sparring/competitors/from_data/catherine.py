"""Generated fitted opponent: 'catherine'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'catherine'
    STYLE = {'vpip': 0.18, 'pfr': 0.18, 'threebet': 0.06, 'limp': 0.1, 'aggression': 0.7000000000000001, 'cbet': 0.9, 'bluff': 0.2, 'stickiness': 0.49, 'size': 1.17, 'adaptive': 1}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
