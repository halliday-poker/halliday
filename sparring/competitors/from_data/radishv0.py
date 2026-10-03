"""Generated fitted opponent: 'radishv0'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'radishv0'
    STYLE = {'vpip': 0.64, 'pfr': 0.52, 'threebet': 0.05, 'limp': 0.0, 'aggression': 0.7000000000000001, 'cbet': 0.55, 'bluff': 0.15000000000000002, 'stickiness': 0.39, 'size': 0.71, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 62, 'epoch': 0, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
