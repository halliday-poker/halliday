"""Generated fitted opponent: 'Phil_Ivey_GOAT'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Phil_Ivey_GOAT'
    STYLE = {'vpip': 0.07, 'pfr': 0.07, 'threebet': 0.01, 'limp': 0.05, 'aggression': 0.5, 'cbet': 0.0, 'bluff': 0.8, 'stickiness': 0.29, 'size': 0.7, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 20, 'epoch': 33, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
