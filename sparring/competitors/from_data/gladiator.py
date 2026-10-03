"""Generated fitted opponent: 'Gladiator'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Gladiator'
    STYLE = {'vpip': 0.28, 'pfr': 0.21, 'threebet': 0.06, 'limp': 0.30000000000000004, 'aggression': 0.5, 'cbet': 0.8, 'bluff': 0.30000000000000004, 'stickiness': 0.99, 'size': 0.615, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 5, 'epoch': 9, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
