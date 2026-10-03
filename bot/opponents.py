"""Per-opponent counters built from this game's public events only.

Four narrow reads gate the field exploits in strategy.py:
- a shover moves all in preflop often, so its shoves are near-random hands;
- a station calls almost every postflop bet, so bluffing it cannot work;
- how often a player folds to our own postflop bets sets how hard we bluff
  them, so we back off anyone who starts calling us down;
- how often it folds to anyone's postflop bets stops bluffs against players
  who rarely fold, before they have faced many of ours.
Preflop frequencies (vpip, pfr, 3-bets per chance) also set how wide
ranges.py assumes each player's opening, calling and 3-betting ranges are.
Counters are keyed by player id, which is fixed for one game; nothing is
stored between games or keyed to a bot's name.
"""

from collections import Counter, defaultdict

# Decay applied to old evidence in the *_recent counters at each new chance.
RECENT_DECAY = 0.75


class OpponentTracker:
    def __init__(self):
        self.profiles = defaultdict(Counter)
        self._start_stacks = []
        self._bets = []
        self._shoved = set()
        self._me = None
        self._aggressor = None
        self._preflop_raises = 0
        self._counted = set()  # (player, stat) already counted this hand
        self._button = 0
        self._opener = None      # seat of the first preflop raiser
        self._steal = False      # that open came from CO/BTN/SB with no limpers
        self._preflop_calls = 0

    def on_hand_start(self, info):
        try:
            players, stacks = info["players"], info["stacks"]
            for player in players:
                self.profiles[player]["hands"] += 1
            self._start_stacks = list(stacks)
            self._bets = [0] * len(players)
            self._shoved = set()
            self._me = info.get("seat")
            self._aggressor = None
            self._preflop_raises = 0
            self._counted = set()
            self._button = info.get("button", 0)
            self._opener = None
            self._steal = False
            self._preflop_calls = 0
        except (AttributeError, KeyError, TypeError):
            pass

    def on_street(self, event):
        self._bets = [0] * len(self._bets)
        self._aggressor = None

    def on_action(self, event):
        try:
            seat, street = event["seat"], event["street"]
            kind, amount = event["action"], event["amount"]
            player = event["players"][seat]
            if street == "preflop":
                # Raise amounts are street totals, so a raise to the starting
                # stack is an all-in. Blinds are not sent to bots.
                if (kind == "raise" and amount >= self._start_stacks[seat]
                        and player not in self._shoved):
                    self._shoved.add(player)
                    self.profiles[player]["shoves"] += 1
                # Each stat counts at most once per player per hand. A 3-bet
                # chance is acting when exactly one raise is in front.
                if kind in ("call", "raise"):
                    self._count_once(player, "vpip")
                if kind == "raise":
                    self._count_once(player, "pfr")
                if self._preflop_raises == 1 and kind != "check":
                    if self._count_once(player, "threebet_chances") and kind == "raise":
                        self.profiles[player]["threebets"] += 1
                n = len(self._start_stacks)
                pos = (seat - self._button) % n
                # Fold to a 3-bet: the opener acting with exactly one re-raise in front.
                if self._preflop_raises == 2 and seat == self._opener:
                    if self._count_once(player, "faced_3bet"):
                        prof = self.profiles[player]
                        prof["fold_3bet"] += kind == "fold"
                        # Recency-weighted copies: each new chance shrinks the old
                        # evidence, so a player who stops folding is noticed fast.
                        prof["faced_3bet_recent"] = prof["faced_3bet_recent"] * RECENT_DECAY + 1
                        prof["fold_3bet_recent"] = (prof["fold_3bet_recent"] * RECENT_DECAY
                                                    + (kind == "fold"))
                # Fold to an open: anyone facing a lone open with no callers yet.
                if (self._preflop_raises == 1 and seat != self._opener
                        and self._preflop_calls == 0):
                    if self._count_once(player, "faced_open") and kind == "fold":
                        self.profiles[player]["fold_open"] += 1
                # Fold to a steal: a blind facing a lone late-position open.
                if (self._preflop_raises == 1 and self._steal and seat != self._opener
                        and pos in (1, 2) and self._preflop_calls == 0):
                    if self._count_once(player, "faced_steal") and kind == "fold":
                        self.profiles[player]["fold_steal"] += 1
                if kind == "raise":
                    if self._preflop_raises == 0:
                        self._opener = seat
                        self._steal = self._preflop_calls == 0 and pos in (0, 1, n - 1)
                    self._preflop_raises += 1
                elif kind == "call":
                    self._preflop_calls += 1
                return
            facing = max(self._bets) > self._bets[seat]
            ours = facing and self._me is not None and self._aggressor == self._me
            if kind == "raise":
                self._bets[seat] = amount
                self._aggressor = seat
            elif kind == "call":
                self._bets[seat] += amount
            if not facing:
                # Postflop betting frequency when not facing a bet.
                self.profiles[player]["bet_chances"] += 1
                self.profiles[player]["bets"] += kind == "raise"
            if facing:
                profile = self.profiles[player]
                profile["faced"] += 1
                profile[kind] += 1
                if ours:
                    profile["faced_us"] += 1
                    profile[kind + "_us"] += 1
        except (KeyError, IndexError, TypeError, ValueError):
            pass

    def _count_once(self, player, stat):
        if (player, stat) in self._counted:
            return False
        self._counted.add((player, stat))
        self.profiles[player][stat] += 1
        return True


def shrunk_rate(count, chances, prior, weight):
    """A frequency pulled toward the field's prior until there is evidence."""
    return (count + prior * weight) / (chances + weight)


def profile_of(state, seat, profiles):
    if not profiles:
        return None
    try:
        return profiles.get(state.player_at(seat))
    except (IndexError, KeyError):
        return None


def is_shover(profile, params):
    if not profile or profile["hands"] < params["shover_min_hands"]:
        return False
    shoves = profile["shoves"]
    return shoves >= params["shover_min_shoves"] and shoves / profile["hands"] >= params["shover_min_rate"]


def is_station(profile, params):
    if not profile or profile["faced"] < params["station_min_faced"]:
        return False
    faced = profile["faced"]
    return (profile["fold"] / faced <= params["station_max_fold"]
            and profile["raise"] / faced <= params["station_max_raise"])


def fold_to_any(profile, params):
    """This game's fold rate to anyone's postflop bets, once there are enough."""
    if not profile or profile["faced"] < params["bluff_any_min_faced"]:
        return params["bluff_any_prior"]
    return shrunk_rate(profile["fold"], profile["faced"], params["bluff_any_prior"], params["bluff_prior_weight"])


def fold_to_us(profile, params):
    """This game's fold rate to our postflop bets, shrunk toward the field's."""
    prior, weight = params["bluff_fold_prior"], params["bluff_prior_weight"]
    faced = profile["faced_us"] if profile else 0
    folds = profile["fold_us"] if profile else 0
    return (folds + prior * weight) / (faced + weight)
