"""Generated fitted opponent: 'tungbot'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'tungbot'
    STYLE = {'vpip': 0.22, 'pfr': 0.22, 'threebet': 0.06, 'limp': 0.2, 'aggression': 0.15000000000000002, 'cbet': 0.6000000000000001, 'bluff': 1.0, 'stickiness': 0.27, 'size': 0.365, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 73, 'epoch': 126, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
