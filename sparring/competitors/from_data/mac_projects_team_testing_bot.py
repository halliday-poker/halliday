"""Generated fitted opponent: 'MAC Projects Team Testing Bot'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'MAC Projects Team Testing Bot'
    STYLE = {'vpip': 0.23, 'pfr': 0.23, 'threebet': 0.04, 'limp': 0.15000000000000002, 'aggression': 0.15000000000000002, 'cbet': 0.6000000000000001, 'bluff': 1.0, 'stickiness': 0.09, 'size': 0.365, 'adaptive': 1}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 14, 'epoch': 24, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
