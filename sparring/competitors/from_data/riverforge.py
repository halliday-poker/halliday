"""Generated fitted opponent: 'RiverForge'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'RiverForge'
    STYLE = {'vpip': 0.16, 'pfr': 0.16, 'threebet': 0.03, 'limp': 0.15000000000000002, 'aggression': 0.5, 'cbet': 0.25, 'bluff': 0.35000000000000003, 'stickiness': 1.0, 'size': 0.535, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
