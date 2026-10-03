"""Generated fitted opponent: 'goatbot'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'goatbot'
    STYLE = {'vpip': 0.38, 'pfr': 0.38, 'threebet': 0.06, 'limp': 0.15000000000000002, 'aggression': 0.7000000000000001, 'cbet': 0.2, 'bluff': 0.45, 'stickiness': 0.43, 'size': 0.365, 'adaptive': 1}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 37, 'epoch': 0, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
