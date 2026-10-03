"""Generated fitted opponent: 'idc'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'idc'
    STYLE = {'vpip': 0.17333333333333334, 'pfr': 0.16999999999999998, 'threebet': 0.03333333333333333, 'limp': 0.16666666666666669, 'aggression': 0.5, 'cbet': 0.4666666666666667, 'bluff': 0.3666666666666667, 'stickiness': 0.89, 'size': 0.8450000000000001, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 44, 'epoch': 58, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
