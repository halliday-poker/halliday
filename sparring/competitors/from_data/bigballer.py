"""Generated fitted opponent: 'BigBaller'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'BigBaller'
    STYLE = {'vpip': 0.22, 'pfr': 0.22, 'threebet': 0.07, 'limp': 0.1, 'aggression': 0.2, 'cbet': 0.0, 'bluff': 0.55, 'stickiness': 0.8, 'size': 0.605, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 4, 'epoch': 6, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
