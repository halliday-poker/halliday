"""Generated fitted opponent: 'jongwon'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'jongwon'
    STYLE = {'vpip': 0.16, 'pfr': 0.16, 'threebet': 0.03, 'limp': 0.05, 'aggression': 0.5, 'cbet': 0.15000000000000002, 'bluff': 0.55, 'stickiness': 0.33, 'size': 0.89, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 52, 'epoch': 84, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
