"""Generated fitted opponent: 'Jason_idea'. See profiles.json for uncertainty."""

import competitor_base


class CompetitorBot(competitor_base.FittedBot):
    DISPLAY_NAME = 'Jason_idea'
    STYLE = {'vpip': 0.8533333333333334, 'pfr': 0.8533333333333334, 'threebet': 0.8450000000000001, 'limp': 0.08333333333333334, 'aggression': 0.5, 'cbet': 0.07500000000000001, 'bluff': 0.12500000000000003, 'stickiness': 0.38333333333333336, 'size': 0.39083333333333337, 'adaptive': 0}
    POLICY = {'file': 'behavior-policy.npz', 'bot': 11, 'epoch': 23, 'weight': 0, 'model': 'upload', 'heldout_comparison': 'behavior-comparison.json', 'status': 'sparse_scaffold_fallback'}


def make_seeded_bot(seed):
    return CompetitorBot(seed=seed)
