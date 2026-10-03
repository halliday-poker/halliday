"""Generated fitted opponent: 'orcabot'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'orcabot'
    STYLE = {'vpip': 0.16, 'pfr': 0.16, 'threebet': 0.03, 'limp': 0.7000000000000001, 'aggression': 0.5, 'cbet': 0.5, 'bluff': 0.65, 'stickiness': 0.39, 'size': 1.165, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 64, 'epoch': 123, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
