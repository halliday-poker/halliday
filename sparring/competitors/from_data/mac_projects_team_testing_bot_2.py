"""Generated fitted opponent: 'MAC Projects Team Testing Bot 2'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'MAC Projects Team Testing Bot 2'
    STYLE = {'vpip': 0.22, 'pfr': 0.21, 'threebet': 0.03, 'limp': 0.1, 'aggression': 1.0, 'cbet': 0.25, 'bluff': 1.0, 'stickiness': 0.35000000000000003, 'size': 0.495, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
