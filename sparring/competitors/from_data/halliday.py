"""Generated fitted opponent: 'Halliday'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Halliday'
    STYLE = {'vpip': 0.14, 'pfr': 0.14, 'threebet': 0.03, 'limp': 0.05, 'aggression': 0.2, 'cbet': 0.45, 'bluff': 0.55, 'stickiness': 0.25, 'size': 0.895, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 5, 'epoch': 13, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
