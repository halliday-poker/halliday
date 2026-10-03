"""Generated fitted opponent: 'dan_negreanu_on_ket'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'dan_negreanu_on_ket'
    STYLE = {'vpip': 0.22, 'pfr': 0.22, 'threebet': 0.06, 'limp': 0.1, 'aggression': 0.15000000000000002, 'cbet': 0.25, 'bluff': 0.55, 'stickiness': 0.35000000000000003, 'size': 0.605, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 29, 'epoch': 41, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
