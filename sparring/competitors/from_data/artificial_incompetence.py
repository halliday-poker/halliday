"""Generated fitted opponent: 'Artificial Incompetence'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Artificial Incompetence'
    STYLE = {'vpip': 1.0, 'pfr': 1.0, 'threebet': 0.24, 'limp': 0.05, 'aggression': 0.8, 'cbet': 0.75, 'bluff': 1.0, 'stickiness': 0.08, 'size': 0.9400000000000001, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 3, 'epoch': 0, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
