"""Generated fitted opponent: 'the notorious'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'the notorious'
    STYLE = {'vpip': 0.14, 'pfr': 0.14, 'threebet': 0.07, 'limp': 0.05, 'aggression': 0.05, 'cbet': 0.45, 'bluff': 0.30000000000000004, 'stickiness': 0.24, 'size': 1.1800000000000002, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 82, 'epoch': 166, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
