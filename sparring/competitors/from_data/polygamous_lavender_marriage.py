"""Generated fitted opponent: 'polygamous lavender marriage'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'polygamous lavender marriage'
    STYLE = {'vpip': 0.22, 'pfr': 0.22, 'threebet': 0.03, 'limp': 0.1, 'aggression': 0.2, 'cbet': 0.75, 'bluff': 0.8500000000000001, 'stickiness': 0.0, 'size': 0.5449999999999999, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 69, 'epoch': 134, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
