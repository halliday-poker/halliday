"""Generated fitted opponent: 'data'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'data'
    STYLE = {'vpip': 0.5700000000000001, 'pfr': 0.5700000000000001, 'threebet': 0.08, 'limp': 0.45, 'aggression': 0.725, 'cbet': 0.6500000000000001, 'bluff': 0.625, 'stickiness': 0.36, 'size': 0.9924999999999999, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 36, 'epoch': 59, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
