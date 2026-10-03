"""Generated fitted opponent: 'finian sucks'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'finian sucks'
    STYLE = {'vpip': 0.03, 'pfr': 0.02, 'threebet': 0.02, 'limp': 0.9500000000000001, 'aggression': 0.9500000000000001, 'cbet': 0.0, 'bluff': 0.15000000000000002, 'stickiness': 0.1, 'size': 0.5449999999999999, 'adaptive': 1}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 33, 'epoch': 42, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
