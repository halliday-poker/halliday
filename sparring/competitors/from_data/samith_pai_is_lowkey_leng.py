"""Generated fitted opponent: 'samith pai is lowkey leng'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'samith pai is lowkey leng'
    STYLE = {'vpip': 0.22, 'pfr': 0.22, 'threebet': 0.04, 'limp': 0.2, 'aggression': 0.7000000000000001, 'cbet': 0.8, 'bluff': 0.30000000000000004, 'stickiness': 0.88, 'size': 0.745, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
