"""Generated fitted opponent: 'Gladiators'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Gladiators'
    STYLE = {'vpip': 0.52, 'pfr': 0.52, 'threebet': 0.02, 'limp': 0.5, 'aggression': 0.8500000000000001, 'cbet': 0.7000000000000001, 'bluff': 1.0, 'stickiness': 0.47000000000000003, 'size': 1.165, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 7, 'epoch': 16, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
