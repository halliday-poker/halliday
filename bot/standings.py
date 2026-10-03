"""Finishing-position play: this game's chip totals and expected game points.

A game is scored by finishing position at the table (n points for 1st down
to 1), not by chips. Game points equal 1 plus the number of opponents we
finish above, so with each total drifting by about sigma chips a hand,

    E[points] = 1 + sum_j P(our final total > j's final total)
              ~ 1 + sum_j Phi((ours - theirs) / sqrt((s_us^2 + s_j^2) * hands_left))

Early in a game this is almost linear in chips, so chip EV decides; near
the end it bends: a safe lead makes risk costly and a near miss makes it
cheap. The only input is the per-seat chip changes the engine sends every
bot in `hand_end`. No identities, earlier games or hidden cards are used.
"""

from math import erf, sqrt

if __package__:
    from .opponents import fold_to_any, fold_to_us, profile_of
else:
    from opponents import fold_to_any, fold_to_us, profile_of


def _phi(z):
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))


class Standings:
    """Running chip totals by player id, kept from the observer hooks."""

    def __init__(self, params):
        self.p = params
        self.me = None
        self.num_hands = 100
        self.totals = {}
        self.sq = {}       # sum of squared per-hand deltas, by player id
        self.hands = {}    # hands counted, by player id
        self._players = []
        self._start = []
        self._linear = None

    def on_match_start(self, info):
        try:
            self.me = info.get("player", self.me)
            self.num_hands = int(info.get("num_hands", self.num_hands))
        except (TypeError, ValueError, AttributeError):
            pass

    def on_hand_start(self, info):
        try:
            self._players = list(info["players"])
            self._start = list(info["stacks"])
            if self.me is None:
                self.me = self._players[info["seat"]]
            for pid in self._players:
                self.totals.setdefault(pid, 0)
        except (KeyError, IndexError, TypeError):
            self._players, self._start = [], []

    def on_hand_end(self, info):
        try:
            players = info.get("players") or self._players
            for seat, delta in enumerate(info["deltas"]):
                pid = players[seat]
                self.totals[pid] = self.totals.get(pid, 0) + delta
                self.sq[pid] = self.sq.get(pid, 0) + delta * delta
                self.hands[pid] = self.hands.get(pid, 0) + 1
        except (KeyError, IndexError, TypeError):
            pass

    # -- the points model -------------------------------------------------

    def sigma(self, pid):
        """Per-hand chip swing, shrunk toward the field's ~27 chips."""
        prior, weight = self.p["endgame_sigma"], self.p["endgame_sigma_weight"]
        return sqrt((prior * prior * weight + self.sq.get(pid, 0)) / (weight + self.hands.get(pid, 0)))

    def hands_after(self, state):
        """Hands still to be dealt after the current one."""
        return max(0, self.num_hands - 1 - state.hand)

    def active(self, state):
        return (self.p["endgame_enabled"] and self.me is not None and len(self.totals) > 1
                and self.hands_after(state) < self.p["endgame_window"])

    def expected_points(self, totals, future):
        mine = totals[self.me]
        points = 1.0
        for pid, theirs in totals.items():
            if pid == self.me:
                continue
            spread = sqrt((self.sigma(self.me) ** 2 + self.sigma(pid) ** 2) * future)
            if spread <= 0:
                points += 1.0 if mine > theirs else 0.5 if mine == theirs else 0.0
            else:
                points += _phi((mine - theirs) / spread)
        return points

    def committed(self, state):
        """Chips each seat has put in this hand (stacks reset every hand)."""
        if len(self._start) == len(state.stacks):
            return [max(0, a - b) for a, b in zip(self._start, state.stacks)]
        start = self.p["endgame_stack"]
        return [max(0, start - s) for s in state.stacks]

    def outcome(self, state, winner, extra=None):
        """Expected points if `winner` (a seat) takes the pot after `extra`
        more chips per seat go in. Everyone else loses what they put in."""
        extra = extra or {}
        put = self.committed(state)
        for seat, chips in extra.items():
            put[seat] += chips
        totals = dict(self.totals)
        for seat, chips in enumerate(put):
            pid = state.player_at(seat)
            totals[pid] = totals.get(pid, 0) - chips + (sum(put) if seat == winner else 0)
        if self._linear is not None:
            u0, grad = self._linear
            return u0 + sum(g * (totals.get(pid, 0) - self.totals.get(pid, 0)) for pid, g in grad.items())
        return self.expected_points(totals, self.hands_after(state))

    def linearise(self, state):
        """Make outcome() a first-order (chip-EV-like) version of itself,
        around the totals before this hand; restore with linearise(None)."""
        if state is None:
            self._linear = None
            return
        # At least one hand of drift: on the last hand the step function is
        # flat almost everywhere and would have no slope to compare with.
        future = max(1, self.hands_after(state))
        grad = {}
        for pid in self.totals:
            up, down = dict(self.totals), dict(self.totals)
            up[pid] += 1
            down[pid] -= 1
            grad[pid] = (self.expected_points(up, future) - self.expected_points(down, future)) / 2
        self._linear = (self.expected_points(self.totals, future), grad)

    def favourite(self, state):
        """The opponent assumed to take the pot when we do not: the last
        aggressor if still in, else the first live opponent."""
        live = [s for s, f in enumerate(state.folded) if s != state.seat and not f]
        for action in reversed(state.history):
            if action[2] in ("raise", "allin") and action[1] in live:
                return action[1]
        return live[0] if live else None

    # -- decisions --------------------------------------------------------

    def call_price(self, state):
        """The equity a call needs in points, the analogue of pot odds:
        (U(fold) - U(call, lose)) / (U(call, win) - U(call, lose))."""
        villain = self.favourite(state)
        if villain is None:
            return None
        call = {state.seat: min(state.to_call, state.my_stack)}
        fold = self.outcome(state, villain)
        win = self.outcome(state, state.seat, call)
        lose = self.outcome(state, villain, call)
        if win - lose <= 1e-9:
            return None
        return min(1.0, max(0.0, (fold - lose) / (win - lose)))

    def fold_chance(self, state, opp_profiles):
        """Chance everyone left folds to a bet: our own fold dial heads-up,
        the fold-to-anyone rate multiplied across a multiway pot."""
        live = [s for s, f in enumerate(state.folded) if s != state.seat and not f]
        if len(live) == 1:
            return fold_to_us(profile_of(state, live[0], opp_profiles), self.p)
        chance = 1.0
        for s in live:
            chance *= fold_to_any(profile_of(state, s, opp_profiles), self.p)
        return chance

    def raise_points(self, state, target, equity, fold):
        """Expected points of raising to `target` (a street total): they all
        fold, or the favourite calls and our equity is cut for being called."""
        villain = self.favourite(state)
        mine = min(state.my_stack, target - state.street_bets[state.seat])
        cover = min(state.stacks[villain], max(0, target - state.street_bets[villain]))
        called = max(0.0, equity - self.p["endgame_called_haircut"] * min(1.0, mine / max(1, state.pot)))
        put = {state.seat: mine, villain: cover}
        won_now = self.outcome(state, state.seat)
        return (fold * won_now + (1 - fold) * (called * self.outcome(state, state.seat, put)
                                               + (1 - called) * self.outcome(state, villain, put)))

    def passive_points(self, state, equity):
        """Expected points of checking or calling down: showdown at equity."""
        villain = self.favourite(state)
        if state.to_call:
            put = {state.seat: min(state.to_call, state.my_stack)}
        else:
            put = {}
        return equity * self.outcome(state, state.seat, put) + (1 - equity) * self.outcome(state, villain, put)


def points_price(state, standings):
    """The call price in game points when finishing-position play is on,
    else None so the caller keeps chip pot odds."""
    if standings is None:
        return None
    try:
        return standings.call_price(state) if standings.active(state) else None
    except Exception:  # an enhancement; never cost the action
        return None
