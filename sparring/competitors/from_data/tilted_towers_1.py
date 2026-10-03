"""Generated fitted opponent: 'Tilted_towers_1'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Tilted_towers_1'
    STYLE = {'vpip': 0.1, 'pfr': 0.1, 'threebet': 0.01, 'limp': 0.0, 'aggression': 0.5, 'cbet': 0.05, 'bluff': 0.55, 'stickiness': 0.79, 'size': 0.75, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
