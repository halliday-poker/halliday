"""Generated fitted opponent: 'the GOON'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'the GOON'
    STYLE = {'vpip': 0.17, 'pfr': 0.17, 'threebet': 0.05, 'limp': 0.1, 'aggression': 0.30000000000000004, 'cbet': 0.65, 'bluff': 1.0, 'stickiness': 0.36, 'size': 0.365, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 70, 'epoch': 121, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
