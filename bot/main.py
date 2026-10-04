"""SDK glue for the strategy, the equity engine, this game's opponent counters
and tracked opponent ranges (ranges.py)."""

from hashlib import blake2b
import json
from math import isfinite, log, sqrt

from macpoker import Bot

if __package__:
    from .engine import EquitySamplingError, EquityTimeout, estimate_equity
    from .opponents import OpponentTracker, is_big_raiser, is_shover, profile_of
    from .params import DEFAULT_PARAMS
    from .preflop import terminal_call
    from .ranges import RangeTracker
    from .strategy import decide
else:  # SDK loads main.py as a standalone module from the submission folder.
    from engine import EquitySamplingError, EquityTimeout, estimate_equity
    from opponents import OpponentTracker, is_big_raiser, is_shover, profile_of
    from params import DEFAULT_PARAMS
    from preflop import terminal_call
    from ranges import RangeTracker
    from strategy import decide


class MyBot(Bot):
    def __init__(self):
        self.last_equity = None
        self.last_estimate = None
        self.opponents = OpponentTracker(DEFAULT_PARAMS["large_bet_bb"] * DEFAULT_PARAMS["big_blind"])
        self.ranges = RangeTracker(self.opponents.profiles, DEFAULT_PARAMS)
        self.last_ranged = False

    def on_hand_start(self, info):
        self.last_equity = None
        self.last_estimate = None
        self.opponents.on_hand_start(info)
        self.ranges.on_hand_start(info)

    def on_action(self, event):
        self.opponents.on_action(event)
        self.ranges.on_action(event)

    def on_street(self, event):
        self.opponents.on_street(event)
        self.ranges.on_street(event)

    def on_hand_end(self, info):
        self.ranges.on_hand_end(info)

    def opponent_ranges(self, state, opponents):
        """Tracked ranges per live opponent (None = random cards), or all None
        when tracking is off, the clock is low, or anything goes wrong."""
        p = DEFAULT_PARAMS
        if (not p["range_enabled"] or state.clock_ms < p["low_clock_ms"]
                or (len(opponents) > 1 and not p["range_multiway"])):
            return [None] * len(opponents)
        try:
            ranges = self.ranges.ranges_for(opponents, state.hole, state.board)
        except Exception:  # tracking is an enhancement; never let it cost the action
            return [None] * len(opponents)
        # A proven shover's range stays random cards: the shover rule's premise.
        profiles = [profile_of(state, seat, self.opponents.profiles) for seat in opponents]
        return [None if is_shover(prof, p) or is_big_raiser(prof, p) else r
                for prof, r in zip(profiles, ranges)]

    def act(self, state):
        self.last_equity = None
        self.last_estimate = None
        self.last_ranged = False
        p = DEFAULT_PARAMS
        # Learn from finished showdowns every turn, so they never pile up
        # into one slow decision. Cheap when nothing is pending.
        if p["range_enabled"] and state.clock_ms >= p["low_clock_ms"]:
            try:
                self.ranges.learn_pending()
            except Exception:
                self.ranges._pending.clear()
        # Ordinary preflop decisions need only the fixed tables.
        raises = sum(a[0] == "preflop" and a[2] == "raise" for a in state.history)
        needs_equity = (bool(state.board) or raises >= 3
                        or max(state.street_bets) >= p["large_bet_bb"] * p["big_blind"])
        if needs_equity and state.clock_ms >= p["skip_equity_clock_ms"]:
            opponents = [s for s, folded in enumerate(state.folded)
                         if s != state.seat and not folded]
            # Facing a preflop all-in, players still to act mostly fold: price
            # the call against those already in the pot, not as a multiway hand.
            if not state.board:
                pre = [a for a in state.history if a[0] == "preflop"]
                raisers = [a[1] for a in pre if a[2] == "raise"]
                if raisers and state.stacks[raisers[-1]] == 0:
                    in_pot = {a[1] for a in pre if a[2] in ("call", "raise")}
                    opponents = [s for s in opponents if s in in_pot] or opponents
            low = state.clock_ms < p["low_clock_ms"]
            iterations = p["low_clock_iters"] if low else p["equity_iters"]
            budget = p["low_clock_budget_ms"] if low else p["equity_budget_ms"]
            # A private simulation seed from legal observations only. It has
            # no connection to deck seeds, identities, scores or earlier hands.
            observed = (sorted(state.hole), state.board, state.seat, state.button,
                        state.stacks, state.folded, state.history)
            seed = int.from_bytes(blake2b(json.dumps(observed).encode(), digest_size=8).digest(), "big")
            ranges = self.opponent_ranges(state, opponents)
            ranged = any(r is not None for r in ranges)
            try:
                try:
                    result = estimate_equity(state.hole, state.board, ranges,
                                             iterations, budget, seed=seed)
                except ValueError:  # ranges that cannot coexist: fall back to random cards
                    ranged = False
                    result = estimate_equity(state.hole, state.board, [None] * len(opponents),
                                             iterations, budget, seed=seed)
                self.last_estimate = result
                if result.method == "exact" or result.samples >= p["equity_min_samples"]:
                    self.last_equity = result.equity
                    self.last_ranged = ranged
                elif (p["partial_terminal_equity"] and terminal_call(state)
                      and result.samples >= p["partial_min_samples"]
                      and isfinite(result.equity)):
                    # A bound for fractional showdown share in [0, 1]. Use
                    # alpha/(n*(n+1)) at each sample count, so the union bound
                    # remains conservative when the clock chooses when to stop.
                    n = result.samples
                    radius = sqrt(log(n * (n + 1) / p["partial_equity_alpha"]) / (2 * n))
                    self.last_equity = max(0.0, result.equity - radius)
                    self.last_ranged = ranged
                    # A sparse estimate may rescue a call, never justify a
                    # raise. Existing street/range margins still apply.
                    action = decide(state, self.last_equity, self.opponents.profiles,
                                    params=p, ranged=ranged)
                    return state.call() if action.kind in ("call", "raise") else action
            except (EquityTimeout, EquitySamplingError):
                pass
        return decide(state, self.last_equity, self.opponents.profiles, params=p,
                      ranged=self.last_ranged)
