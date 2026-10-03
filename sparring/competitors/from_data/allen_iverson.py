"""Generated fitted opponent: 'Allen Iverson'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Allen Iverson'
    STYLE = {'vpip': 0.11, 'pfr': 0.11, 'threebet': 0.03, 'limp': 0.05, 'aggression': 0.5, 'cbet': 0.1, 'bluff': 0.2, 'stickiness': 0.9500000000000001, 'size': 0.775, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 0, 'epoch': 1, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
