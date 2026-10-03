"""Generated fitted opponent: 'tripi tropi'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'tripi tropi'
    STYLE = {'vpip': 0.17, 'pfr': 0.17, 'threebet': 0.03, 'limp': 0.1, 'aggression': 0.5, 'cbet': 0.6000000000000001, 'bluff': 0.25, 'stickiness': 0.87, 'size': 0.745, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 72, 'epoch': 124, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
