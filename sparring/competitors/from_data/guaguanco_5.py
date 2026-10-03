"""Generated fitted opponent: 'guaguanco 5'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'guaguanco 5'
    STYLE = {'vpip': 0.16, 'pfr': 0.16, 'threebet': 0.05, 'limp': 0.05, 'aggression': 0.7000000000000001, 'cbet': 0.4, 'bluff': 1.0, 'stickiness': 0.4, 'size': 0.875, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 49, 'epoch': 66, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
