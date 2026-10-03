"""Generated fitted opponent: 'netanyahu'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'netanyahu'
    STYLE = {'vpip': 0.23, 'pfr': 0.23, 'threebet': 0.02, 'limp': 0.1, 'aggression': 1.0, 'cbet': 0.8500000000000001, 'bluff': 1.0, 'stickiness': 0.14, 'size': 0.7050000000000001, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 55, 'epoch': 93, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
