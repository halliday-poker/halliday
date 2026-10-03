"""Generated fitted opponent: 'RiverForge'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'RiverForge'
    STYLE = {'vpip': 0.16, 'pfr': 0.16, 'threebet': 0.01, 'limp': 0.15000000000000002, 'aggression': 0.5, 'cbet': 0.2, 'bluff': 0.5, 'stickiness': 0.99, 'size': 0.5449999999999999, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 18, 'epoch': 27, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
