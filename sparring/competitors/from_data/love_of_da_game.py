"""Generated fitted opponent: 'love-of-da-game'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'love-of-da-game'
    STYLE = {'vpip': 0.23, 'pfr': 0.23, 'threebet': 0.03, 'limp': 0.15000000000000002, 'aggression': 0.05, 'cbet': 0.4, 'bluff': 0.8, 'stickiness': 0.53, 'size': 0.895, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
