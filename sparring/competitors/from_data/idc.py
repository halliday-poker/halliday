"""Generated fitted opponent: 'idc'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'idc'
    STYLE = {'vpip': 0.15, 'pfr': 0.15, 'threebet': 0.05, 'limp': 0.15000000000000002, 'aggression': 0.5, 'cbet': 0.4, 'bluff': 0.30000000000000004, 'stickiness': 0.85, 'size': 0.6799999999999999, 'adaptive': 1}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 51, 'epoch': 76, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
