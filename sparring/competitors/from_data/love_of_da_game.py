"""Generated fitted opponent: 'love-of-da-game'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'love-of-da-game'
    STYLE = {'vpip': 0.17, 'pfr': 0.17, 'threebet': 0.03, 'limp': 0.05, 'aggression': 0.05, 'cbet': 0.2, 'bluff': 0.75, 'stickiness': 0.19, 'size': 0.89, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 60, 'epoch': 99, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
