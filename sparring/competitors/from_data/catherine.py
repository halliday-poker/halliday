"""Generated fitted opponent: 'catherine'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'catherine'
    STYLE = {'vpip': 0.18, 'pfr': 0.18, 'threebet': 0.03, 'limp': 0.15000000000000002, 'aggression': 0.7000000000000001, 'cbet': 0.8, 'bluff': 0.15000000000000002, 'stickiness': 0.24, 'size': 1.185, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 28, 'epoch': 39, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
