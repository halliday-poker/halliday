"""Generated fitted opponent: 'pressure'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'pressure'
    STYLE = {'vpip': 0.1, 'pfr': 0.1, 'threebet': 0.03, 'limp': 0.65, 'aggression': 0.5, 'cbet': 0.5, 'bluff': 0.8, 'stickiness': 0.33, 'size': 1.165, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
