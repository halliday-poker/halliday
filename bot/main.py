"""Shared entry point: Person A engine smoke wiring; Person B owns decisions."""

from macpoker import Bot

if __package__:
    from .engine import EquitySamplingError, EquityTimeout, equity
else:  # SDK loads main.py as a standalone module from the submission folder.
    from engine import EquitySamplingError, EquityTimeout, equity


class MyBot(Bot):
    def __init__(self):
        self.last_equity = None

    def on_hand_start(self, info):
        self.last_equity = None

    def act(self, state):
        self.last_equity = None
        if state.clock_ms >= 250:
            # B/C replace None with ranges matched to these live player ids.
            opponents = [s for s, folded in enumerate(state.folded)
                         if s != state.seat and not folded]
            try:
                self.last_equity = equity(
                    state.hole, state.board, [None] * len(opponents),
                    256 if state.clock_ms >= 5000 else 64,
                    25 if state.clock_ms >= 5000 else 10)
            except (EquityTimeout, EquitySamplingError):
                pass  # B's strategy must handle unavailable equity explicitly.

        # Original scaffold policy until Person B's decide() is merged here.
        if state.to_call == 0:
            return state.check()
        if state.to_call / (state.pot + state.to_call) < 0.3:
            return state.call()
        return state.fold()
