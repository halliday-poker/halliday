"""Generated fitted opponent: 'Allen Iverson 2.0'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Allen Iverson 2.0'
    STYLE = {'vpip': 0.1, 'pfr': 0.1, 'threebet': 0.03, 'limp': 0.05, 'aggression': 0.0, 'cbet': 0.25, 'bluff': 0.45, 'stickiness': 0.92, 'size': 0.775, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
