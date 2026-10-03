"""Generated fitted opponent: 'best-bot'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'best-bot'
    STYLE = {'vpip': 0.23, 'pfr': 0.23, 'threebet': 0.05, 'limp': 0.15000000000000002, 'aggression': 0.7000000000000001, 'cbet': 0.25, 'bluff': 0.35000000000000003, 'stickiness': 0.16, 'size': 0.75, 'adaptive': 0}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
