"""Generated fitted opponent: 'preflop-warrior'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'preflop-warrior'
    STYLE = {'vpip': 0.22, 'pfr': 0.22, 'threebet': 0.03, 'limp': 0.15000000000000002, 'aggression': 0.65, 'cbet': 0.5, 'bluff': 0.15000000000000002, 'stickiness': 0.27, 'size': 0.64, 'adaptive': 1}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 60, 'epoch': 105, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
