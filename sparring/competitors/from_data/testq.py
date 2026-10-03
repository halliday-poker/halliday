"""Generated fitted opponent: 'testQ'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'testQ'
    STYLE = {'vpip': 0.17, 'pfr': 0.17, 'threebet': 0.02, 'limp': 0.0, 'aggression': 0.35000000000000003, 'cbet': 0.45, 'bluff': 0.7000000000000001, 'stickiness': 0.84, 'size': 0.615, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 69, 'epoch': 113, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
