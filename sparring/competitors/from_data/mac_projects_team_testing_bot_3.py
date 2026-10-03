"""Generated fitted opponent: 'MAC Projects Team Testing Bot 3'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'MAC Projects Team Testing Bot 3'
    STYLE = {'vpip': 0.22000000000000003, 'pfr': 0.21000000000000002, 'threebet': 0.06, 'limp': 0.05, 'aggression': 0.3500000000000001, 'cbet': 1.0, 'bluff': 1.0, 'stickiness': 0.45000000000000007, 'size': 0.33999999999999997, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 13, 'epoch': 20, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
