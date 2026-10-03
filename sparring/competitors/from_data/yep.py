"""Generated fitted opponent: 'yep'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'yep'
    STYLE = {'vpip': 0.23, 'pfr': 0.23, 'threebet': 0.05, 'limp': 0.2, 'aggression': 0.5, 'cbet': 0.65, 'bluff': 0.35000000000000003, 'stickiness': 0.45, 'size': 0.76, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 75, 'epoch': 131, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
