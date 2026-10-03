"""Generated fitted opponent: 'guaguanco 2'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'guaguanco 2'
    STYLE = {'vpip': 0.29, 'pfr': 0.18, 'threebet': 0.07, 'limp': 0.05, 'aggression': 0.0, 'cbet': 0.6500000000000001, 'bluff': 0.0, 'stickiness': 0.45, 'size': 0.66, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 46, 'epoch': 0, 'weight': 0, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'sparse_scaffold_fallback'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
