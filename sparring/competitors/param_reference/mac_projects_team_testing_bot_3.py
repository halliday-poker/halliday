"""Generated fitted opponent: 'MAC Projects Team Testing Bot 3'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'MAC Projects Team Testing Bot 3'
    STYLE = {'vpip': 0.22, 'pfr': 0.22, 'threebet': 0.06, 'limp': 0.0, 'aggression': 0.5, 'cbet': 1.0, 'bluff': 0.7000000000000001, 'stickiness': 0.45, 'size': 0.33999999999999997, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
