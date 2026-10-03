"""Generated fitted opponent: 'Sus bot'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Sus bot'
    STYLE = {'vpip': 0.22, 'pfr': 0.22, 'threebet': 0.03, 'limp': 0.05, 'aggression': 0.5, 'cbet': 0.45, 'bluff': 0.65, 'stickiness': 0.33, 'size': 0.75, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 23, 'epoch': 40, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
