"""Generated fitted opponent: 'pocket-nuts'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'pocket-nuts'
    STYLE = {'vpip': 0.17, 'pfr': 0.17, 'threebet': 0.06, 'limp': 0.1, 'aggression': 0.5, 'cbet': 0.4, 'bluff': 0.7000000000000001, 'stickiness': 0.86, 'size': 0.5449999999999999, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 56, 'epoch': 94, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
