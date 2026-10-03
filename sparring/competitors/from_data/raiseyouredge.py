"""Generated fitted opponent: 'RaiseYourEdge'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'RaiseYourEdge'
    STYLE = {'vpip': 0.15, 'pfr': 0.15, 'threebet': 0.05, 'limp': 0.1, 'aggression': 0.35000000000000003, 'cbet': 0.2, 'bluff': 0.6000000000000001, 'stickiness': 0.19, 'size': 0.365, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 17, 'epoch': 25, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
