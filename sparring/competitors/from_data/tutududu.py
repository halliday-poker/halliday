"""Generated fitted opponent: 'tutududu'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'tutududu'
    STYLE = {'vpip': 0.18, 'pfr': 0.18, 'threebet': 0.04, 'limp': 0.0, 'aggression': 0.7000000000000001, 'cbet': 0.7000000000000001, 'bluff': 0.4, 'stickiness': 1.0, 'size': 0.45, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 74, 'epoch': 128, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
