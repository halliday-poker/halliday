"""Fixed-hand-count games and duplicate sets.

A game deals `deals` hands, each from its own freshly shuffled deck. The
button is always seat 0 and the bots move one seat every hand, so each bot
plays every position equally often. Chip deltas are summed per bot.

Duplicate play happens across games. A duplicate set is one game per seat
that share a seed: every game deals the same decks, and game k shifts every
bot k seats along. Over the set each bot plays every deck from every seat,
and because each game is its own bot process, no bot ever sees a deck twice.

Bots are charged against a chess-style clock (base bank + increment per
hand). A bot that times out, crashes or breaks protocol is marked dead with
a verdict (TLE/RTE/PV) and check-folds the remainder of the game; the game
always completes and always produces a result.

Each bot is a player id 0..n-1, fixed for the whole game. Every message
sent to a bot carries `players` (seat -> player id) so bots can follow
opponents across hands as the seats move.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import Callable

from .actions import Action
from .cards import shuffled_deck
from .hand import Sink, play_hand
from .transport import BotDied, ProtocolError, Transport


VERDICT_OK = "OK"
VERDICT_TLE = "TLE"
VERDICT_RTE = "RTE"
VERDICT_PV = "PV"


@dataclass
class MatchConfig:
    seats: int = 2
    deals: int = 100  # hands in the game, one fresh deck each
    offset: int = 0  # seat shift; game k of a duplicate set uses offset k
    stack: int = 200
    sb: int = 1
    bb: int = 2
    seed: str = "0"
    base_time_ms: int = 30_000
    increment_ms: int = 100

    @property
    def num_hands(self) -> int:
        return self.deals


@dataclass
class MatchResult:
    chips: list[int]
    verdicts: list[str]
    num_hands: int
    mbb_per_hand: list[float]
    hands: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "chips": self.chips,
            "verdicts": self.verdicts,
            "num_hands": self.num_hands,
            "mbb_per_hand": self.mbb_per_hand,
        }


class _MatchSink(Sink):
    def __init__(self, runner: "MatchRunner", seat_map: list[int], record: dict):
        self.runner = runner
        self.seat_map = seat_map  # seat -> bot index
        self.record = record

    def notify(self, seat: int | None, msg: dict) -> None:
        if seat is None:
            self.record.setdefault("events", []).append(msg)
            out = {**msg, "players": list(self.seat_map)}
            for s, bot in enumerate(self.seat_map):
                self.runner._send(bot, out)
        else:
            if msg.get("type") == "hand_start":
                # spectator record only - never broadcast to other bots
                self.record.setdefault("holes", {})[str(seat)] = msg["hole"]
            self.runner._send(self.seat_map[seat], {**msg, "players": list(self.seat_map)})

    def request_action(self, seat: int, view: dict) -> Action | None:
        return self.runner._act(self.seat_map[seat], {**view, "players": list(self.seat_map)})


class MatchRunner:
    def __init__(self, config: MatchConfig, transports: list[Transport]):
        assert len(transports) == config.seats
        self.config = config
        self.transports = transports
        n = config.seats
        self.dead = [False] * n
        self.verdicts = [VERDICT_OK] * n
        self.banks_ms = [float(config.base_time_ms)] * n
        self.chips = [0] * n
        self.hands: list[dict] = []

    def _send(self, bot: int, msg: dict) -> None:
        if self.dead[bot]:
            return
        try:
            self.transports[bot].send(msg)
        except BotDied:
            self._kill(bot, VERDICT_RTE)

    def _act(self, bot: int, view: dict) -> Action | None:
        if self.dead[bot]:
            return None
        view = dict(view)
        view["clock_ms"] = int(self.banks_ms[bot])
        try:
            action, elapsed_ms = self.transports[bot].act(view, timeout_ms=self.banks_ms[bot])
        except TimeoutError:
            self._kill(bot, VERDICT_TLE)
            return None
        except ProtocolError:
            self._kill(bot, VERDICT_PV)
            return None
        except BotDied:
            self._kill(bot, VERDICT_RTE)
            return None
        self.banks_ms[bot] -= elapsed_ms
        if self.banks_ms[bot] < 0:
            self._kill(bot, VERDICT_TLE)
            return None
        return action

    def _kill(self, bot: int, verdict: str) -> None:
        if not self.dead[bot]:
            self.dead[bot] = True
            self.verdicts[bot] = verdict
            self.transports[bot].close()

    def run(self) -> MatchResult:
        cfg = self.config
        n = cfg.seats
        hello = {
            "type": "hello",
            "num_players": n,
            "num_hands": cfg.num_hands,
            "stack": cfg.stack,
            "blinds": [cfg.sb, cfg.bb],
            "time_bank_ms": cfg.base_time_ms,
            "increment_ms": cfg.increment_ms,
        }
        for bot in range(n):
            try:
                self.transports[bot].start()
                self._send(bot, {**hello, "player": bot})
            except BotDied:
                self._kill(bot, VERDICT_RTE)

        for hand_no in range(cfg.deals):
            deck = shuffled_deck(random.Random(f"{cfg.seed}:{hand_no}"))
            shift = hand_no + cfg.offset
            # bot b sits in seat (b + shift) % n  =>  seat s holds bot (s - shift) % n
            seat_map = [(s - shift) % n for s in range(n)]
            for bot in range(n):
                if not self.dead[bot]:
                    self.banks_ms[bot] += cfg.increment_ms
            record: dict = {
                "hand": hand_no,
                "offset": cfg.offset,
                "seat_map": seat_map,
                "events": [],
            }
            sink = _MatchSink(self, seat_map, record)
            result = play_hand(
                stacks=[cfg.stack] * n,
                button=0,
                deck=deck,
                sink=sink,
                sb=cfg.sb,
                bb=cfg.bb,
                hand_no=hand_no,
            )
            for seat, delta in enumerate(result.deltas):
                self.chips[seat_map[seat]] += delta
            record["deltas_by_bot"] = [result.deltas[(b + shift) % n] for b in range(n)]
            self.hands.append(record)

        totals = {"type": "match_end", "chips": list(self.chips), "verdicts": list(self.verdicts)}
        for bot in range(n):
            self._send(bot, totals)
            self.transports[bot].close()

        mbb = [round(c / cfg.bb / max(cfg.num_hands, 1) * 1000, 2) for c in self.chips]
        assert sum(self.chips) == 0, f"game not zero-sum: {self.chips}"
        return MatchResult(
            chips=self.chips,
            verdicts=self.verdicts,
            num_hands=cfg.num_hands,
            mbb_per_hand=mbb,
            hands=self.hands,
        )


def play_set(
    config: MatchConfig,
    make_transports: Callable[[int], list[Transport]],
    games: int | None = None,
) -> list[MatchResult]:
    """Play a duplicate set: `games` games (default one per seat) over the
    same decks, game k shifting every bot k seats. `make_transports(k)` must
    return fresh transports for game k, so no bot carries memory between
    games."""
    results = []
    for k in range(games if games is not None else config.seats):
        cfg = replace(config, offset=config.offset + k)
        results.append(MatchRunner(cfg, make_transports(k)).run())
    return results
