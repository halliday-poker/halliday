"""Generated fitted opponent: 'the big dog'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'the big dog'
    STYLE = {'vpip': 0.17, 'pfr': 0.17, 'threebet': 0.03, 'limp': 0.2, 'aggression': 0.5, 'cbet': 0.55, 'bluff': 0.15000000000000002, 'stickiness': 0.71, 'size': 0.745, 'adaptive': 1}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 71, 'epoch': 123, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
