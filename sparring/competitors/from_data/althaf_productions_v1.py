"""Generated fitted opponent: 'Althaf Productions v1'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Althaf Productions v1'
    STYLE = {'vpip': 0.13, 'pfr': 0.13, 'threebet': 0.03, 'limp': 0.1, 'aggression': 0.8500000000000001, 'cbet': 0.9, 'bluff': 1.0, 'stickiness': 0.17, 'size': 0.9, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 2, 'epoch': 3, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
