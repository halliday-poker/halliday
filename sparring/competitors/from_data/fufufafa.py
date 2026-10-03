"""Generated fitted opponent: 'fufufafa'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'fufufafa'
    STYLE = {'vpip': 0.9, 'pfr': 0.9, 'threebet': 0.0, 'limp': 0.5, 'aggression': 1.0, 'cbet': 0.8500000000000001, 'bluff': 1.0, 'stickiness': 0.07, 'size': 0.335, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 35, 'epoch': 0, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
