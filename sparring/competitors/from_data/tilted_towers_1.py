"""Generated fitted opponent: 'Tilted_towers_1'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Tilted_towers_1'
    STYLE = {'vpip': 0.1, 'pfr': 0.1, 'threebet': 0.01, 'limp': 0.0, 'aggression': 0.5, 'cbet': 0.1, 'bluff': 0.55, 'stickiness': 0.79, 'size': 0.7, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 27, 'epoch': 0, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
