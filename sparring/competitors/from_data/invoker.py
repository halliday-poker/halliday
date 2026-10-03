"""Generated fitted opponent: 'Invoker'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Invoker'
    STYLE = {'vpip': 0.97, 'pfr': 0.97, 'threebet': 0.01, 'limp': 0.25, 'aggression': 0.7000000000000001, 'cbet': 0.75, 'bluff': 1.0, 'stickiness': 0.18, 'size': 0.335, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 9, 'epoch': 0, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
