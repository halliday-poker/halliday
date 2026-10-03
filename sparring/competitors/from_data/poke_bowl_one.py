"""Generated fitted opponent: 'poke-bowl-one'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'poke-bowl-one'
    STYLE = {'vpip': 0.36, 'pfr': 0.36, 'threebet': 0.06, 'limp': 0.30000000000000004, 'aggression': 0.0, 'cbet': 0.55, 'bluff': 0.8500000000000001, 'stickiness': 0.5, 'size': 0.605, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 68, 'epoch': 0, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
