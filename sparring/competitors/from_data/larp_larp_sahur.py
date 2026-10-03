"""Generated fitted opponent: 'larp larp sahur'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'larp larp sahur'
    STYLE = {'vpip': 0.15, 'pfr': 0.15, 'threebet': 0.03, 'limp': 0.1, 'aggression': 0.5, 'cbet': 0.65, 'bluff': 0.65, 'stickiness': 0.26, 'size': 0.745, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 55, 'epoch': 90, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
