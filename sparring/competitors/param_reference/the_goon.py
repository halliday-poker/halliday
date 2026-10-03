"""Generated fitted opponent: 'the GOON'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'the GOON'
    STYLE = {'vpip': 0.62, 'pfr': 0.38, 'threebet': 0.03, 'limp': 0.25, 'aggression': 0.2, 'cbet': 0.5, 'bluff': 0.8, 'stickiness': 0.27, 'size': 0.995, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
