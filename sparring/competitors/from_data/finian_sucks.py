"""Generated fitted opponent: 'finian sucks'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'finian sucks'
    STYLE = {'vpip': 0.03, 'pfr': 0.01, 'threebet': 0.01, 'limp': 0.8500000000000001, 'aggression': 0.65, 'cbet': 0.0, 'bluff': 0.30000000000000004, 'stickiness': 0.18, 'size': 0.5449999999999999, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 40, 'epoch': 60, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
