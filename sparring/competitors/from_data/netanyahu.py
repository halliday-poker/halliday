"""Generated fitted opponent: 'netanyahu'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'netanyahu'
    STYLE = {'vpip': 0.23, 'pfr': 0.23, 'threebet': 0.03, 'limp': 0.1, 'aggression': 0.7000000000000001, 'cbet': 0.45, 'bluff': 0.9500000000000001, 'stickiness': 0.21, 'size': 0.36, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 63, 'epoch': 122, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
