"""The bot-facing SDK.

Subclass Bot, implement act(), and either run it locally with
`macpoker play mybot.py call` or upload the file to the tournament site.

The module also contains BotSession (message dispatch shared by the
in-process transport and the stdio runner) and run_bot(), the stdio
protocol loop that executes inside the sandbox.
"""

from __future__ import annotations

import json
import sys

from .actions import Action


class GameState:
    """Read-only view of the table at a decision point."""

    def __init__(self, msg: dict):
        self._m = msg

    # --- raw fields -------------------------------------------------
    @property
    def hand(self) -> int:
        return self._m["hand"]

    @property
    def seat(self) -> int:
        return self._m["seat"]

    @property
    def players(self) -> list[int]:
        """Player id sitting in each seat this hand. Ids are fixed for the
        whole game, so they follow opponents as the seats rotate."""
        return self._m["players"]

    @property
    def player(self) -> int:
        return self.players[self.seat]

    @property
    def street(self) -> str:
        return self._m["street"]

    @property
    def board(self) -> list[str]:
        return self._m["board"]

    @property
    def hole(self) -> list[str]:
        return self._m["hole"]

    @property
    def pot(self) -> int:
        return self._m["pot"]

    @property
    def to_call(self) -> int:
        return self._m["to_call"]

    @property
    def min_raise_to(self) -> int:
        return self._m["min_raise_to"]

    @property
    def max_raise_to(self) -> int:
        return self._m["max_raise_to"]

    @property
    def can_raise(self) -> bool:
        return self._m["can_raise"]

    @property
    def stacks(self) -> list[int]:
        return self._m["stacks"]

    @property
    def street_bets(self) -> list[int]:
        return self._m["street_bets"]

    @property
    def folded(self) -> list[bool]:
        return self._m["folded"]

    @property
    def button(self) -> int:
        return self._m["button"]

    @property
    def history(self) -> list[list]:
        """Actions this hand so far: [street, seat, kind, amount]."""
        return self._m["history"]

    @property
    def clock_ms(self) -> int:
        return self._m.get("clock_ms", 0)

    # --- helpers ----------------------------------------------------
    def player_at(self, seat: int) -> int:
        return self.players[seat]

    def seat_of(self, player: int) -> int:
        return self.players.index(player)

    @property
    def my_stack(self) -> int:
        return self.stacks[self.seat]

    @property
    def num_players(self) -> int:
        return len(self.stacks)

    @property
    def players_in_hand(self) -> int:
        return sum(1 for f in self.folded if not f)

    # --- action constructors ----------------------------------------
    def fold(self) -> Action:
        return Action.fold()

    def check(self) -> Action:
        return Action.check()

    def call(self) -> Action:
        return Action.call()

    def raise_to(self, amount: int) -> Action:
        return Action.raise_to(amount)

    def all_in(self) -> Action:
        return Action.all_in()

    def raw(self) -> dict:
        return dict(self._m)


class Bot:
    """Base class for tournament bots. Implement act(); the other hooks are
    optional observers."""

    name: str = ""

    def act(self, state: GameState) -> Action:
        raise NotImplementedError

    def on_match_start(self, info: dict) -> None:
        pass

    def on_hand_start(self, info: dict) -> None:
        pass

    def on_action(self, event: dict) -> None:
        pass

    def on_street(self, event: dict) -> None:
        pass

    def on_hand_end(self, info: dict) -> None:
        pass

    def on_match_end(self, info: dict) -> None:
        pass


class BotSession:
    """Dispatches protocol messages to a Bot. Returns an Action for 'act'
    messages and None for everything else."""

    def __init__(self, bot: Bot):
        self.bot = bot

    def handle(self, msg: dict) -> Action | None:
        t = msg.get("type")
        if t == "act":
            action = self.bot.act(GameState(msg))
            if not isinstance(action, Action):
                raise TypeError(f"act() must return an Action, got {action!r}")
            return action
        if t == "hello":
            self.bot.on_match_start(msg)
        elif t == "hand_start":
            self.bot.on_hand_start(msg)
        elif t == "action":
            self.bot.on_action(msg)
        elif t == "street":
            self.bot.on_street(msg)
        elif t == "hand_end":
            self.bot.on_hand_end(msg)
        elif t == "match_end":
            self.bot.on_match_end(msg)
        return None


def run_bot(bot: Bot) -> None:
    """Speak the stdio protocol on behalf of `bot`. The bot's own prints are
    redirected to stderr so they can't corrupt the protocol stream."""
    protocol_out = sys.stdout
    sys.stdout = sys.stderr
    session = BotSession(bot)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        action = session.handle(msg)
        if msg.get("type") == "act":
            protocol_out.write(json.dumps(action.to_wire()) + "\n")
            protocol_out.flush()
        if msg.get("type") == "match_end":
            break


def load_bot_from_file(path: str) -> Bot:
    """Load a user bot: the file must define `bot = MyBot()` or exactly one
    Bot subclass (which gets instantiated with no arguments). The file's
    directory is added to sys.path so a zipped project can import its own
    sibling modules from main.py."""
    import importlib.util
    import os

    parent = os.path.dirname(os.path.abspath(path))
    if parent not in sys.path:
        sys.path.insert(0, parent)

    spec = importlib.util.spec_from_file_location("user_bot", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load bot from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    candidate = getattr(module, "bot", None)
    if isinstance(candidate, Bot):
        return candidate
    subclasses = [
        v
        for v in vars(module).values()
        if isinstance(v, type) and issubclass(v, Bot) and v is not Bot
    ]
    if len(subclasses) == 1:
        return subclasses[0]()
    raise ValueError(
        f"{path} must define `bot = YourBot()` or exactly one Bot subclass "
        f"(found {len(subclasses)})"
    )
