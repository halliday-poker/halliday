"""Generated fitted opponent: 'larp larp sahur'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'larp larp sahur'
    STYLE = {'vpip': 0.17, 'pfr': 0.17, 'threebet': 0.03, 'limp': 0.15000000000000002, 'aggression': 0.2, 'cbet': 0.7000000000000001, 'bluff': 0.9, 'stickiness': 0.36, 'size': 0.755, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 47, 'epoch': 68, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
