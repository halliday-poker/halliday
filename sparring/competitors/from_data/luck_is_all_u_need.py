"""Generated fitted opponent: 'luck is all u need'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'luck is all u need'
    STYLE = {'vpip': 0.13, 'pfr': 0.13, 'threebet': 0.02, 'limp': 0.1, 'aggression': 0.5, 'cbet': 0.15000000000000002, 'bluff': 0.05, 'stickiness': 0.31, 'size': 0.62, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 61, 'epoch': 109, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
