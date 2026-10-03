"""Generated fitted opponent: 'Messi'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Messi'
    STYLE = {'vpip': 0.12, 'pfr': 0.12, 'threebet': 0.01, 'limp': 0.7000000000000001, 'aggression': 0.30000000000000004, 'cbet': 0.8, 'bluff': 0.75, 'stickiness': 0.02, 'size': 0.51, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
