"""Generated fitted opponent: 'diddy blud'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'diddy blud'
    STYLE = {'vpip': 0.03, 'pfr': 0.03, 'threebet': 0.03, 'limp': 0.15000000000000002, 'aggression': 1.0, 'cbet': 0.0, 'bluff': 0.2, 'stickiness': 0.24, 'size': 0.585, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 37, 'epoch': 0, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
