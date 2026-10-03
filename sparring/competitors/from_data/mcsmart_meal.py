"""Generated fitted opponent: 'McSmart Meal'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'McSmart Meal'
    STYLE = {'vpip': 0.47000000000000003, 'pfr': 0.47000000000000003, 'threebet': 0.03, 'limp': 0.15000000000000002, 'aggression': 0.7000000000000001, 'cbet': 0.5, 'bluff': 0.1, 'stickiness': 0.27, 'size': 0.64, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 17, 'epoch': 28, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
