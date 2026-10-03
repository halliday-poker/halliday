"""SDK glue for the strategy, the equity engine and this game's opponent counters."""

from hashlib import blake2b
import json

from macpoker import Bot

if __package__:
    from .engine import EquitySamplingError, EquityTimeout, estimate_equity
    from .opponents import OpponentTracker
    from .params import DEFAULT_PARAMS
    from .strategy import decide
else:  # SDK loads main.py as a standalone module from the submission folder.
    from engine import EquitySamplingError, EquityTimeout, estimate_equity
    from opponents import OpponentTracker
    from params import DEFAULT_PARAMS
    from strategy import decide


class MyBot(Bot):
    def __init__(self):
        self.last_equity = None
        self.last_estimate = None
        self.opponents = OpponentTracker()

    def on_hand_start(self, info):
        self.last_equity = None
        self.last_estimate = None
        self.opponents.on_hand_start(info)

    def on_action(self, event):
        self.opponents.on_action(event)

    def on_street(self, event):
        self.opponents.on_street(event)

    def act(self, state):
        self.last_equity = None
        self.last_estimate = None
        p = DEFAULT_PARAMS
        # Ordinary preflop decisions need only the fixed tables.
        raises = sum(a[0] == "preflop" and a[2] == "raise" for a in state.history)
        needs_equity = (bool(state.board) or raises >= 3
                        or max(state.street_bets) >= p["large_bet_bb"] * p["big_blind"])
        if needs_equity and state.clock_ms >= p["skip_equity_clock_ms"]:
            opponents = [s for s, folded in enumerate(state.folded)
                         if s != state.seat and not folded]
            low = state.clock_ms < p["low_clock_ms"]
            iterations = p["low_clock_iters"] if low else p["equity_iters"]
            budget = p["low_clock_budget_ms"] if low else p["equity_budget_ms"]
            # A private simulation seed from legal observations only. It has
            # no connection to deck seeds, identities, scores or earlier hands.
            observed = (sorted(state.hole), state.board, state.seat, state.button,
                        state.stacks, state.folded, state.history)
            seed = int.from_bytes(blake2b(json.dumps(observed).encode(), digest_size=8).digest(), "big")
            try:
                result = estimate_equity(state.hole, state.board, [None] * len(opponents),
                                         iterations, budget, seed=seed)
                self.last_estimate = result
                if result.method == "exact" or result.samples >= p["equity_min_samples"]:
                    self.last_equity = result.equity
            except (EquityTimeout, EquitySamplingError):
                pass
        return decide(state, self.last_equity, self.opponents.profiles, params=p)
