"""Generated fitted opponent: 'dan_negreanu_on_ket'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'dan_negreanu_on_ket'
    STYLE = {'vpip': 0.27, 'pfr': 0.27, 'threebet': 0.06, 'limp': 0.1, 'aggression': 0.0, 'cbet': 0.05, 'bluff': 0.65, 'stickiness': 0.45, 'size': 0.36, 'adaptive': 1}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
