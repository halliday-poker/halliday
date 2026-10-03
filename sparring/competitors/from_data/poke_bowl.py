"""Generated fitted opponent: 'poke-bowl'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'poke-bowl'
    STYLE = {'vpip': 0.17, 'pfr': 0.17, 'threebet': 0.03, 'limp': 0.05, 'aggression': 0.5, 'cbet': 0.1, 'bluff': 0.55, 'stickiness': 0.33, 'size': 0.645, 'adaptive': 1}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 67, 'epoch': 0, 'weight': 1, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'fitted_public_context_policy'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
