"""Generated fitted opponent: 'percy-perc-filet'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'percy-perc-filet'
    STYLE = {'vpip': 0.42, 'pfr': 0.42, 'threebet': 0.11, 'limp': 0.15000000000000002, 'aggression': 0.25, 'cbet': 0.05, 'bluff': 0.45, 'stickiness': 0.77, 'size': 0.61, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 65, 'epoch': 128, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
