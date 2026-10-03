"""Generated fitted opponent: 'dan_negreanu_on_ket'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'dan_negreanu_on_ket'
    STYLE = {'vpip': 0.26, 'pfr': 0.26, 'threebet': 0.07, 'limp': 0.1, 'aggression': 0.30000000000000004, 'cbet': 0.35000000000000003, 'bluff': 0.45, 'stickiness': 0.44, 'size': 0.605, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 35, 'epoch': 57, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
