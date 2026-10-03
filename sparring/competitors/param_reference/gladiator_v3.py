"""Generated fitted opponent: 'Gladiator_v3'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Gladiator_v3'
    STYLE = {'vpip': 0.52, 'pfr': 0.47000000000000003, 'threebet': 0.02, 'limp': 0.55, 'aggression': 0.5, 'cbet': 0.55, 'bluff': 1.0, 'stickiness': 0.41000000000000003, 'size': 1.175, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
