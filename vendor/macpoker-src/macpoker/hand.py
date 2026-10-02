"""Single-hand no-limit hold'em state machine for 2..9 seats.

The engine is transport-agnostic: it asks a `Sink` for each decision and
notifies it of every public/private event. The match runner supplies a sink
that forwards to bot processes, enforces clocks and records history.

Rules implemented:
- blinds (heads-up: button posts the small blind and acts first preflop)
- raise-to semantics with proper minimum raise tracking
- short all-in raises do not reopen the action for players who already acted
- side pots layered by contribution, uncalled bets refunded
- invalid actions are coerced to the nearest legal action; a None action
  (dead/timed-out bot) is treated as check/fold
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .actions import Action
from .cards import cards_str
from .evaluator import evaluate

STREETS = ("preflop", "flop", "turn", "river")


@dataclass
class HandResult:
    deltas: list[int]
    board: list[int]
    actions: list[list]  # [street, seat, kind, amount]
    pots: list[dict]  # {"amount": int, "winners": [seat]}
    revealed: dict[int, list[int]]  # seat -> hole cards shown at showdown
    folded: list[bool]


class Sink:
    """Interface between the hand engine and the outside world."""

    def notify(self, seat: int | None, msg: dict) -> None:
        """Deliver an event to one seat, or to every seat if seat is None."""

    def request_action(self, seat: int, view: dict) -> Action | None:
        """Ask the bot in `seat` to act. None means the bot is dead/timed out."""
        return None


def play_hand(
    stacks: list[int],
    button: int,
    deck: list[int],
    sink: Sink,
    sb: int,
    bb: int,
    hand_no: int = 0,
) -> HandResult:
    n = len(stacks)
    assert 2 <= n <= 9
    start = list(stacks)
    stacks = list(stacks)
    folded = [False] * n
    allin = [False] * n
    contrib = [0] * n
    street_bet = [0] * n
    board: list[int] = []
    actions_log: list[list] = []

    holes = [[deck[2 * s], deck[2 * s + 1]] for s in range(n)]
    community = deck[2 * n : 2 * n + 5]

    def commit(seat: int, amount: int) -> int:
        amount = min(amount, stacks[seat])
        stacks[seat] -= amount
        street_bet[seat] += amount
        contrib[seat] += amount
        if stacks[seat] == 0:
            allin[seat] = True
        return amount

    def alive() -> list[int]:
        return [s for s in range(n) if not folded[s]]

    def can_act() -> list[int]:
        return [s for s in range(n) if not folded[s] and not allin[s]]

    for s in range(n):
        sink.notify(
            s,
            {
                "type": "hand_start",
                "hand": hand_no,
                "seat": s,
                "button": button,
                "stacks": list(start),
                "hole": cards_str(holes[s]),
            },
        )

    if n == 2:
        sb_seat, bb_seat = button, (button + 1) % n
    else:
        sb_seat, bb_seat = (button + 1) % n, (button + 2) % n
    commit(sb_seat, sb)
    commit(bb_seat, bb)
    sink.notify(None, {"type": "blinds", "sb_seat": sb_seat, "bb_seat": bb_seat, "sb": sb, "bb": bb})

    current_bet = 0
    min_inc = bb

    def normalize(act: Action | None, seat: int, to_call: int, raise_ok: bool, min_to: int, max_to: int) -> tuple[str, int]:
        if act is None:
            return ("check", 0) if to_call == 0 else ("fold", 0)
        kind = act.kind
        if kind == "raise" and raise_ok:
            amt = min(act.amount, max_to)
            if amt < min_to:
                amt = min(min_to, max_to)
            if amt <= current_bet:
                kind = "call"
            else:
                return ("raise", amt)
        elif kind == "raise":
            kind = "call"
        if kind == "call":
            return ("call", 0) if to_call > 0 else ("check", 0)
        if kind == "check":
            # checking when facing a bet is treated as check-fold
            return ("check", 0) if to_call == 0 else ("fold", 0)
        # fold; folding with nothing to call is coerced to a free check
        return ("check", 0) if to_call == 0 else ("fold", 0)

    def betting_round(street: str) -> None:
        nonlocal current_bet, min_inc, street_bet
        if street == "preflop":
            current_bet = max(street_bet)
            min_inc = bb
            opener = button if n == 2 else (button + 3) % n
        else:
            street_bet = [0] * n
            current_bet = 0
            min_inc = bb
            opener = (button + 1) % n

        order = [(opener + i) % n for i in range(n)]
        pending = deque(s for s in order if not folded[s] and not allin[s])
        can_raise = {s: True for s in range(n)}
        acted: set[int] = set()

        while pending:
            seat = pending.popleft()
            if folded[seat] or allin[seat]:
                continue
            if len(alive()) == 1:
                return
            to_call = min(current_bet - street_bet[seat], stacks[seat])
            max_to = street_bet[seat] + stacks[seat]
            min_to = (current_bet + min_inc) if current_bet > 0 else bb
            raise_ok = can_raise[seat] and max_to > current_bet and len(can_act()) > 1

            view = {
                "type": "act",
                "hand": hand_no,
                "seat": seat,
                "street": street,
                "board": cards_str(board),
                "hole": cards_str(holes[seat]),
                "pot": sum(contrib),
                "to_call": to_call,
                "min_raise_to": min(min_to, max_to),
                "max_raise_to": max_to,
                "can_raise": raise_ok,
                "stacks": list(stacks),
                "street_bets": list(street_bet),
                "folded": list(folded),
                "button": button,
                "history": [list(a) for a in actions_log],
            }
            act = sink.request_action(seat, view)
            kind, amt = normalize(act, seat, to_call, raise_ok, min_to, max_to)
            acted.add(seat)

            if kind == "fold":
                folded[seat] = True
            elif kind == "check":
                pass
            elif kind == "call":
                commit(seat, to_call)
            else:  # raise
                prev_bet = current_bet
                commit(seat, amt - street_bet[seat])
                current_bet = street_bet[seat]
                inc = current_bet - prev_bet
                full = inc >= min_inc
                if full:
                    min_inc = inc
                idx = order.index(seat)
                others = [
                    order[(idx + i) % n]
                    for i in range(1, n)
                    if not folded[order[(idx + i) % n]] and not allin[order[(idx + i) % n]]
                ]
                pending = deque(others)
                if full:
                    can_raise = {s: True for s in range(n)}
                    acted = {seat}
                else:
                    for s in acted:
                        can_raise[s] = False

            actions_log.append([street, seat, kind, amt if kind == "raise" else (to_call if kind == "call" else 0)])
            sink.notify(
                None,
                {
                    "type": "action",
                    "hand": hand_no,
                    "street": street,
                    "seat": seat,
                    "action": kind,
                    "amount": actions_log[-1][3],
                    "pot": sum(contrib),
                },
            )
            if len(alive()) == 1:
                return

    reveal_counts = {"flop": 3, "turn": 4, "river": 5}
    for street in STREETS:
        if street != "preflop":
            board = community[: reveal_counts[street]]
            sink.notify(None, {"type": "street", "hand": hand_no, "street": street, "board": cards_str(board)})
        if len(alive()) > 1 and len(can_act()) > 1:
            betting_round(street)
        elif street == "preflop" and len(can_act()) >= 1 and len(alive()) > 1:
            # blind all-in edge case: remaining actor still gets to respond
            betting_round(street)
        if len(alive()) == 1:
            break

    # refund any uncalled bet
    top = max(contrib)
    holders = [s for s in range(n) if contrib[s] == top]
    if len(holders) == 1 and top > 0:
        second = max((contrib[s] for s in range(n) if s != holders[0]), default=0)
        refund = top - second
        stacks[holders[0]] += refund
        contrib[holders[0]] -= refund

    live = alive()
    pots: list[dict] = []
    revealed: dict[int, list[int]] = {}

    if len(live) == 1:
        winner = live[0]
        stacks[winner] += sum(contrib)
        pots.append({"amount": sum(contrib), "winners": [winner]})
    else:
        # showdown over full board
        board = community[:5]
        revealed = {s: holes[s] for s in live}
        values = {s: evaluate(holes[s] + board) for s in live}
        levels = sorted(set(c for c in contrib if c > 0))
        prev = 0
        payout_order = [(button + 1 + i) % n for i in range(n)]
        for level in levels:
            amount = sum(min(contrib[s], level) - min(contrib[s], prev) for s in range(n))
            eligible = [s for s in live if contrib[s] >= level]
            if not eligible:
                eligible = live  # defensive: should not happen after refund
            best = max(values[s] for s in eligible)
            winners = [s for s in payout_order if s in eligible and values[s] == best]
            share, odd = divmod(amount, len(winners))
            for i, w in enumerate(winners):
                stacks[w] += share + (1 if i < odd else 0)
            pots.append({"amount": amount, "winners": winners})
            prev = level

    deltas = [stacks[s] - start[s] for s in range(n)]
    assert sum(deltas) == 0, f"hand not zero-sum: {deltas}"

    sink.notify(
        None,
        {
            "type": "hand_end",
            "hand": hand_no,
            "board": cards_str(board),
            "deltas": deltas,
            "revealed": {str(s): cards_str(h) for s, h in revealed.items()},
            "pots": pots,
        },
    )
    return HandResult(
        deltas=deltas,
        board=board,
        actions=actions_log,
        pots=pots,
        revealed=revealed,
        folded=folded,
    )
