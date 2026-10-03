"""Generated fitted opponent: 'radishv2'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'radishv2'
    STYLE = {'vpip': 0.38, 'pfr': 0.38, 'threebet': 0.02, 'limp': 0.2, 'aggression': 0.05, 'cbet': 0.35000000000000003, 'bluff': 0.35000000000000003, 'stickiness': 0.43, 'size': 0.7150000000000001, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 64, 'epoch': 106, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
