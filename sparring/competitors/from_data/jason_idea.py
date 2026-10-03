"""Generated fitted opponent: 'Jason_idea'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Jason_idea'
    STYLE = {'vpip': 1.0, 'pfr': 1.0, 'threebet': 1.0, 'limp': 0.1, 'aggression': 0.5, 'cbet': 0.1, 'bluff': 0.1, 'stickiness': 0.27, 'size': 0.39, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
