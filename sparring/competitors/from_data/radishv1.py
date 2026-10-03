"""Generated fitted opponent: 'radishv1'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'radishv1'
    STYLE = {'vpip': 0.38, 'pfr': 0.38, 'threebet': 0.02, 'limp': 0.35000000000000003, 'aggression': 0.5, 'cbet': 0.4, 'bluff': 0.0, 'stickiness': 0.35000000000000003, 'size': 0.71, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 73, 'epoch': 0, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
