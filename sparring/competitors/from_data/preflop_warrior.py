"""Generated fitted opponent: 'preflop-warrior'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'preflop-warrior'
    STYLE = {'vpip': 0.22, 'pfr': 0.21, 'threebet': 0.03, 'limp': 0.1, 'aggression': 0.75, 'cbet': 0.5, 'bluff': 0.35000000000000003, 'stickiness': 0.31, 'size': 0.6000000000000001, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 70, 'epoch': 143, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
