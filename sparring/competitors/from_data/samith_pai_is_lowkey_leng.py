"""Generated fitted opponent: 'samith pai is lowkey leng'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'samith pai is lowkey leng'
    STYLE = {'vpip': 0.22000000000000003, 'pfr': 0.22000000000000003, 'threebet': 0.04, 'limp': 0.2, 'aggression': 0.7000000000000001, 'cbet': 0.8500000000000001, 'bluff': 0.26666666666666666, 'stickiness': 0.8800000000000001, 'size': 0.585, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 66, 'epoch': 109, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
