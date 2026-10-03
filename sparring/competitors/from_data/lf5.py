"""Generated fitted opponent: 'LF5'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'LF5'
    STYLE = {'vpip': 0.03, 'pfr': 0.03, 'threebet': 0.03, 'limp': 0.30000000000000004, 'aggression': 0.9500000000000001, 'cbet': 0.0, 'bluff': 0.0, 'stickiness': 0.25, 'size': 0.585, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 9, 'epoch': 0, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
