"""Generated fitted opponent: 'best-bot'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'best-bot'
    STYLE = {'vpip': 0.23, 'pfr': 0.23, 'threebet': 0.06, 'limp': 0.15000000000000002, 'aggression': 0.5, 'cbet': 0.55, 'bluff': 1.0, 'stickiness': 0.56, 'size': 0.91, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 25, 'epoch': 33, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
