"""Generated fitted opponent: 'guaguanco 3'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'guaguanco 3'
    STYLE = {'vpip': 1.0, 'pfr': 0.0, 'threebet': 0.0, 'limp': 0.05, 'aggression': 0.0, 'cbet': 0.65, 'bluff': 0.0, 'stickiness': 0.27, 'size': 0.66, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 40, 'epoch': 0, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
