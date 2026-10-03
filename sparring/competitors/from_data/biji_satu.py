"""Generated fitted opponent: 'biji satu'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'biji satu'
    STYLE = {'vpip': 1.0, 'pfr': 1.0, 'threebet': 0.08, 'limp': 0.25, 'aggression': 0.7000000000000001, 'cbet': 0.7000000000000001, 'bluff': 1.0, 'stickiness': 0.37, 'size': 0.335, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 33, 'epoch': 0, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
