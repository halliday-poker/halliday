"""Generated fitted opponent: 'renbot'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'renbot'
    STYLE = {'vpip': 0.23, 'pfr': 0.23, 'threebet': 0.03, 'limp': 0.1, 'aggression': 1.0, 'cbet': 1.0, 'bluff': 1.0, 'stickiness': 0.41000000000000003, 'size': 1.17, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 65, 'epoch': 107, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
