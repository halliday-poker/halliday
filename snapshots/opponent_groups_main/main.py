"""SDK glue for the strategy, the equity engine, this game's opponent counters
and tracked opponent ranges (ranges.py)."""

from hashlib import blake2b
import json
import random
import secrets
from math import isfinite, log, sqrt

from macpoker import Bot

if __package__:
    from .engine import EquitySamplingError, EquityTimeout, estimate_equity
    from .group_observer import GroupObserver
    from .group_priors import GROUPS, CONFIG
    from .groups import GroupModel
    from .opponents import OpponentTracker, is_shover, profile_of
    from .params import DEFAULT_PARAMS
    from .preflop import terminal_call
    from .ranges import RangeTracker
    from .strategy import decide
else:  # SDK loads main.py as a standalone module from the submission folder.
    from engine import EquitySamplingError, EquityTimeout, estimate_equity
    from group_observer import GroupObserver
    from group_priors import GROUPS, CONFIG
    from groups import GroupModel
    from opponents import OpponentTracker, is_shover, profile_of
    from params import DEFAULT_PARAMS
    from preflop import terminal_call
    from ranges import RangeTracker
    from strategy import decide


class MyBot(Bot):
    def __init__(self, seed=None):
        self.last_equity = None
        self.last_estimate = None
        self.opponents = OpponentTracker()
        self.group_observer = GroupObserver()
        self._groups_available = True
        self.groups = GroupModel(self.group_observer,GROUPS,CONFIG)
        self.ranges = RangeTracker(self.opponents.profiles, DEFAULT_PARAMS, self.group_prior)
        self._mix = random.Random(secrets.randbits(128) if seed is None else seed)
        self.last_groups = {}
        self.last_ranged = False

    def on_hand_start(self, info):
        self.last_equity = None
        self.last_estimate = None
        self.opponents.on_hand_start(info)
        self.ranges.on_hand_start(info)
        self.observe_group('on_hand_start',info)

    def on_action(self, event):
        self.opponents.on_action(event)
        self.ranges.on_action(event)
        self.observe_group('on_action',event)

    def on_street(self, event):
        self.opponents.on_street(event)
        self.ranges.on_street(event)
        self.observe_group('on_street',event)

    def on_hand_end(self, info):
        self.ranges.on_hand_end(info)
        self.observe_group('on_hand_end',info)

    def observe_group(self,method,event):
        if DEFAULT_PARAMS['group_enabled'] and self._groups_available:
            try:
                getattr(self.group_observer,method)(event)
            except (KeyError,IndexError,TypeError,ValueError,AttributeError):
                # Malformed input must not poison an exploit. Retain the tested
                # baseline for this game; valid SDK games never take this path.
                self._groups_available=False

    def group_prior(self, player):
        p=DEFAULT_PARAMS
        return self.groups.parameters(player,p,counters=False,strength=p['group_strength']) if p['group_enabled'] and self._groups_available else p

    def decision_parameters(self,state):
        p=DEFAULT_PARAMS
        self.last_groups={}
        if not p['group_enabled'] or not self._groups_available:
            return p
        self.group_observer.learn_pending()
        for player in state.players:
            if player==state.player:continue
            result=self.groups.classify(player)
            self.last_groups[str(player)]=dict(group=GROUPS[result['top']]['name'],
                probability=round(result['probability'],4),weight=round(result['weight'],4),
                hands=result['hands'],drift=round(result['drift'],4))
        if not p['group_counters']:
            return p
        seats=[i for i,f in enumerate(state.folded) if not f and i!=state.seat]
        if not seats:return p
        # Calls target the bettor, while each opponent's hand range has its own
        # group prior. For an unbet multiway pot, retain the lowest bluff rate.
        raises=[a[1] for a in state.history if a[0]==state.street and a[2]=='raise' and a[1] in seats]
        if state.to_call and raises:seats=[raises[-1]]
        settings=[self.groups.parameters(state.player_at(s),p,strength=p['group_strength']) for s in seats]
        result=dict(p)
        keys=set(GROUPS[0]['counter'])
        for key in keys:
            result[key]=sum(v[key] for v in settings)/len(settings)
        result['bluff_frequency']=min(v['bluff_frequency'] for v in settings)
        adaptive=max(self.groups.adaptive_weight(state.player_at(s)) for s in seats)*p['group_strength']
        jitter=p['group_mix']*adaptive
        if jitter:
            factor=1+self._mix.uniform(-jitter,jitter)
            # Identical sizing randomization for value and bluffs; never perturb
            # call/fold thresholds or strong value decisions with random noise.
            for key in ('cbet_pot_fraction','late_pot_fraction','size_dry','size_wet','raise_pot_fraction'):
                result[key]*=factor
            result['bluff_frequency']*=1-jitter
        return result

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
        return [None if is_shover(profile_of(state, seat, self.opponents.profiles), p) else r
                for seat, r in zip(opponents, ranges)]

    def act(self, state):
        self.last_equity = None
        self.last_estimate = None
        self.last_ranged = False
        p = self.decision_parameters(state)
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
                      and result.samples >= p["partial_min_samples"] and isfinite(result.equity)):
                    n=result.samples
                    radius=sqrt(log(n*(n+1)/p["partial_equity_alpha"])/(2*n))
                    self.last_equity=max(0.0,result.equity-radius)
                    self.last_ranged=ranged
                    action=decide(state,self.last_equity,self.opponents.profiles,params=p,ranged=ranged)
                    return state.call() if action.kind in ('call','raise') else action
            except (EquityTimeout, EquitySamplingError):
                pass
        return decide(state, self.last_equity, self.opponents.profiles, params=p,
                      ranged=self.last_ranged)


def make_seeded_bot(seed):
    """Offline reproducible private mixing; normal submissions use OS entropy."""
    return MyBot(seed=seed)
