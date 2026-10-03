"""Generated fitted opponent: 'MAC Projects Team Testing Bot 2'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'MAC Projects Team Testing Bot 2'
    STYLE = {'vpip': 0.23, 'pfr': 0.23, 'threebet': 0.06, 'limp': 0.15000000000000002, 'aggression': 0.30000000000000004, 'cbet': 0.7000000000000001, 'bluff': 1.0, 'stickiness': 0.0, 'size': 0.36, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 12, 'epoch': 19, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
