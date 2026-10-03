"""Generated fitted opponent: 'polygamous lavender marriage'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'polygamous lavender marriage'
    STYLE = {'vpip': 0.23, 'pfr': 0.23, 'threebet': 0.03, 'limp': 0.2, 'aggression': 0.2, 'cbet': 0.8500000000000001, 'bluff': 0.9500000000000001, 'stickiness': 0.0, 'size': 0.42500000000000004, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
