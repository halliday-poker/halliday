"""Generated fitted opponent: 'Nice Hand, Sir'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Nice Hand, Sir'
    STYLE = {'vpip': 0.97, 'pfr': 0.97, 'threebet': 0.06, 'limp': 0.2, 'aggression': 0.9500000000000001, 'cbet': 0.75, 'bluff': 1.0, 'stickiness': 0.0, 'size': 0.335, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
