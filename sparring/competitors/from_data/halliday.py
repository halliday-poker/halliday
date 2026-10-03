"""Generated fitted opponent: 'Halliday'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Halliday'
    STYLE = {'vpip': 0.16, 'pfr': 0.16, 'threebet': 0.03, 'limp': 0.1, 'aggression': 0.2, 'cbet': 0.65, 'bluff': 0.65, 'stickiness': 0.68, 'size': 0.895, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 8, 'epoch': 20, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
