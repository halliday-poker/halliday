"""Generated fitted opponent: 'Invokerv2'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Invokerv2'
    STYLE = {'vpip': 0.93, 'pfr': 0.93, 'threebet': 0.02, 'limp': 0.2, 'aggression': 1.0, 'cbet': 0.9500000000000001, 'bluff': 1.0, 'stickiness': 0.07, 'size': 0.33999999999999997, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
