"""Generated fitted opponent: 'love-of-da-game'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'love-of-da-game'
    STYLE = {'vpip': 0.17, 'pfr': 0.17, 'threebet': 0.03, 'limp': 0.0, 'aggression': 0.30000000000000004, 'cbet': 0.4, 'bluff': 0.8, 'stickiness': 0.17, 'size': 0.89, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 52, 'epoch': 76, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
