"""Generated fitted opponent: 'Tester67'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Tester67'
    STYLE = {'vpip': 0.18, 'pfr': 0.18, 'threebet': 0.05, 'limp': 0.1, 'aggression': 0.7000000000000001, 'cbet': 0.45, 'bluff': 0.35000000000000003, 'stickiness': 0.89, 'size': 0.65, 'adaptive': 1}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 24, 'epoch': 41, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
