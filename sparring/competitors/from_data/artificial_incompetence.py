"""Generated fitted opponent: 'Artificial Incompetence'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Artificial Incompetence'
    STYLE = {'vpip': 1.0, 'pfr': 1.0, 'threebet': 0.24, 'limp': 0.05, 'aggression': 0.8, 'cbet': 0.8, 'bluff': 1.0, 'stickiness': 0.08, 'size': 0.9400000000000001, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
