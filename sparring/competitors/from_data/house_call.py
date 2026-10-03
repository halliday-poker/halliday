"""Generated fitted opponent: 'house:call'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'house:call'
    STYLE = {'vpip': 1.0, 'pfr': 0.01, 'threebet': 0.01, 'limp': 0.05, 'aggression': 0.0, 'cbet': 0.65, 'bluff': 0.0, 'stickiness': 1.0, 'size': 0.66, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 50, 'epoch': 0, 'weight': 0, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'sparse_scaffold_fallback'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
