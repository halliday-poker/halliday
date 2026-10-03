"""Generated fitted opponent: 'larp larp sahur'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'larp larp sahur'
    STYLE = {'vpip': 0.17, 'pfr': 0.17, 'threebet': 0.03, 'limp': 0.1, 'aggression': 0.5, 'cbet': 0.7000000000000001, 'bluff': 0.6000000000000001, 'stickiness': 0.26, 'size': 0.745, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
