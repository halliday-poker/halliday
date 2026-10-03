"""Generated fitted opponent: 'big dog'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'big dog'
    STYLE = {'vpip': 0.22, 'pfr': 0.22, 'threebet': 0.03, 'limp': 0.2, 'aggression': 0.7000000000000001, 'cbet': 0.65, 'bluff': 0.2, 'stickiness': 0.84, 'size': 0.745, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
