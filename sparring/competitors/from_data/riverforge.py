"""Generated fitted opponent: 'RiverForge'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'RiverForge'
    STYLE = {'vpip': 0.22, 'pfr': 0.22, 'threebet': 0.03, 'limp': 0.1, 'aggression': 0.1, 'cbet': 0.1, 'bluff': 0.25, 'stickiness': 0.45, 'size': 0.46499999999999997, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 22, 'epoch': 37, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
