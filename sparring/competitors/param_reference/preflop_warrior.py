"""Generated fitted opponent: 'preflop-warrior'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'preflop-warrior'
    STYLE = {'vpip': 0.22, 'pfr': 0.22, 'threebet': 0.03, 'limp': 0.15000000000000002, 'aggression': 0.5, 'cbet': 0.2, 'bluff': 0.15000000000000002, 'stickiness': 0.36, 'size': 0.6000000000000001, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
