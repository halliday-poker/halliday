"""Generated fitted opponent: 'Gladiator_v3'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Gladiator_v3'
    STYLE = {'vpip': 0.52, 'pfr': 0.49, 'threebet': 0.02, 'limp': 0.5, 'aggression': 0.5, 'cbet': 0.45, 'bluff': 1.0, 'stickiness': 0.41000000000000003, 'size': 1.2149999999999999, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 4, 'epoch': 10, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
