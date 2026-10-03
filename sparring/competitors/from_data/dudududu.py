"""Generated fitted opponent: 'dudududu'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'dudududu'
    STYLE = {'vpip': 0.18, 'pfr': 0.18, 'threebet': 0.04, 'limp': 0.05, 'aggression': 0.8500000000000001, 'cbet': 0.65, 'bluff': 0.25, 'stickiness': 0.99, 'size': 0.45, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
