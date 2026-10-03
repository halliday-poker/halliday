"""Generated fitted opponent: 'lil-fruit'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'lil-fruit'
    STYLE = {'vpip': 1.0, 'pfr': 0.1, 'threebet': 0.04, 'limp': 0.35000000000000003, 'aggression': 0.5, 'cbet': 0.15000000000000002, 'bluff': 0.05, 'stickiness': 0.23, 'size': 0.96, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 57, 'epoch': 0, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
