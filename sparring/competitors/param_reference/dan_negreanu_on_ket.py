"""Generated fitted opponent: 'dan_negreanu_on_ket'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'dan_negreanu_on_ket'
    STYLE = {'vpip': 0.24, 'pfr': 0.24, 'threebet': 0.06, 'limp': 0.1, 'aggression': 0.15000000000000002, 'cbet': 0.2, 'bluff': 0.6000000000000001, 'stickiness': 0.5, 'size': 0.605, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
