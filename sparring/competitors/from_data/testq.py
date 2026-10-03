"""Generated fitted opponent: 'testQ'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'testQ'
    STYLE = {'vpip': 0.22333333333333333, 'pfr': 0.22000000000000003, 'threebet': 0.026666666666666665, 'limp': 0.20000000000000004, 'aggression': 0.2, 'cbet': 0.5166666666666667, 'bluff': 0.6666666666666667, 'stickiness': 0.18000000000000002, 'size': 0.44333333333333336, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 79, 'epoch': 153, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
