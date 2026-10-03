"""Generated fitted opponent: 'MAC Projects Team Testing Bot 2'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'MAC Projects Team Testing Bot 2'
    STYLE = {'vpip': 0.23, 'pfr': 0.23, 'threebet': 0.06, 'limp': 0.15000000000000002, 'aggression': 0.30000000000000004, 'cbet': 0.7000000000000001, 'bluff': 1.0, 'stickiness': 0.0, 'size': 0.36, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
