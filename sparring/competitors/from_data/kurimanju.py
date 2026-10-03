"""Generated fitted opponent: 'kurimanju'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'kurimanju'
    STYLE = {'vpip': 0.35000000000000003, 'pfr': 0.35000000000000003, 'threebet': 0.02, 'limp': 0.25, 'aggression': 0.2, 'cbet': 0.45, 'bluff': 0.2, 'stickiness': 0.33, 'size': 0.71, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 54, 'epoch': 86, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
