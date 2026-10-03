"""Generated fitted opponent: 'poke-bowl'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'poke-bowl'
    STYLE = {'vpip': 0.17, 'pfr': 0.17, 'threebet': 0.05, 'limp': 0.05, 'aggression': 0.5, 'cbet': 0.15000000000000002, 'bluff': 0.55, 'stickiness': 0.52, 'size': 0.755, 'adaptive': 1}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
