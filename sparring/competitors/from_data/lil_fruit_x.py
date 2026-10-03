"""Generated fitted opponent: 'lil-fruit x'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'lil-fruit x'
    STYLE = {'vpip': 1.0, 'pfr': 1.0, 'threebet': 0.39, 'limp': 0.0, 'aggression': 0.7000000000000001, 'cbet': 0.6000000000000001, 'bluff': 1.0, 'stickiness': 0.02, 'size': 0.355, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 51, 'epoch': 0, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
