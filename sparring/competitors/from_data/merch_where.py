"""Generated fitted opponent: 'merch where'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'merch where'
    STYLE = {'vpip': 1.0, 'pfr': 1.0, 'threebet': 0.07, 'limp': 0.2, 'aggression': 0.15000000000000002, 'cbet': 0.6000000000000001, 'bluff': 1.0, 'stickiness': 0.27, 'size': 1.48, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 62, 'epoch': 118, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
