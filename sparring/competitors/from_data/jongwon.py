"""Generated fitted opponent: 'jongwon'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'jongwon'
    STYLE = {'vpip': 0.15, 'pfr': 0.15, 'threebet': 0.02, 'limp': 0.05, 'aggression': 0.0, 'cbet': 0.4, 'bluff': 0.9500000000000001, 'stickiness': 0.87, 'size': 0.89, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 45, 'epoch': 64, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
