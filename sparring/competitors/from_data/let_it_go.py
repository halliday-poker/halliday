"""Generated fitted opponent: 'let it go'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'let it go'
    STYLE = {'vpip': 0.06, 'pfr': 0.0, 'threebet': 0.0, 'limp': 0.05, 'aggression': 0.2, 'cbet': 0.0, 'bluff': 0.15000000000000002, 'stickiness': 0.02, 'size': 0.435, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 48, 'epoch': 69, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
