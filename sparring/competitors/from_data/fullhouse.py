"""Generated fitted opponent: 'fullhouse'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'fullhouse'
    STYLE = {'vpip': 0.11, 'pfr': 0.11, 'threebet': 0.03, 'limp': 0.65, 'aggression': 0.2, 'cbet': 0.7000000000000001, 'bluff': 1.0, 'stickiness': 0.39, 'size': 1.375, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 43, 'epoch': 62, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
