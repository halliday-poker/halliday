"""Generated fitted opponent: 'poke-bowl-one'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'poke-bowl-one'
    STYLE = {'vpip': 0.22, 'pfr': 0.22, 'threebet': 0.06, 'limp': 0.15000000000000002, 'aggression': 0.7000000000000001, 'cbet': 0.45, 'bluff': 0.5, 'stickiness': 0.35000000000000003, 'size': 0.6000000000000001, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
