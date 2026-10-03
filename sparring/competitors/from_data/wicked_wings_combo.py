"""Generated fitted opponent: 'wicked wings combo'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'wicked wings combo'
    STYLE = {'vpip': 0.38, 'pfr': 0.38, 'threebet': 0.03, 'limp': 0.15000000000000002, 'aggression': 0.2, 'cbet': 0.6000000000000001, 'bluff': 0.2, 'stickiness': 0.19, 'size': 0.645, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 86, 'epoch': 172, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
