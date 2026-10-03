"""Generated fitted opponent: 'Tilted_Towers_2'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Tilted_Towers_2'
    STYLE = {'vpip': 0.13, 'pfr': 0.13, 'threebet': 0.03, 'limp': 0.1, 'aggression': 0.5, 'cbet': 0.0, 'bluff': 0.25, 'stickiness': 1.0, 'size': 0.375, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 20, 'epoch': 29, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
