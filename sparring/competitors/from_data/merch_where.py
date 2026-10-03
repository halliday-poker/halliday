"""Generated fitted opponent: 'merch where'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'merch where'
    STYLE = {'vpip': 0.93, 'pfr': 0.93, 'threebet': 0.06, 'limp': 0.15000000000000002, 'aggression': 0.5, 'cbet': 0.6000000000000001, 'bluff': 0.9500000000000001, 'stickiness': 0.44, 'size': 0.315, 'adaptive': 1}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 54, 'epoch': 90, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
