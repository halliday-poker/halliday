"""Generated fitted opponent: 'fold-a2'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'fold-a2'
    STYLE = {'vpip': 0.0, 'pfr': 0.0, 'threebet': 0.0, 'limp': 0.05, 'aggression': 0.0, 'cbet': 0.65, 'bluff': 0.0, 'stickiness': 1.0, 'size': 0.66, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 34, 'epoch': 43, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
