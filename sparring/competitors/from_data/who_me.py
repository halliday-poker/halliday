"""Generated fitted opponent: 'Who me?'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Who me?'
    STYLE = {'vpip': 0.48, 'pfr': 0.06, 'threebet': 0.06, 'limp': 0.2, 'aggression': 0.2, 'cbet': 0.05, 'bluff': 0.2, 'stickiness': 0.03, 'size': 0.535, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
