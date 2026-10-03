"""Generated fitted opponent: 'axiom'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'axiom'
    STYLE = {'vpip': 0.22, 'pfr': 0.22, 'threebet': 0.06, 'limp': 0.2, 'aggression': 0.7000000000000001, 'cbet': 0.1, 'bluff': 0.15000000000000002, 'stickiness': 0.31, 'size': 0.925, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 30, 'epoch': 44, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
