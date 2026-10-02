"""Built-in reference bots, used for local testing and submission validation."""

from __future__ import annotations

import random

from ..actions import Action
from ..sdk import Bot, GameState


class CheckCallBot(Bot):
    name = "call"

    def act(self, state: GameState) -> Action:
        return state.call() if state.to_call > 0 else state.check()


class CheckFoldBot(Bot):
    name = "checkfold"

    def act(self, state: GameState) -> Action:
        return state.check() if state.to_call == 0 else state.fold()


class AllInBot(Bot):
    name = "allin"

    def act(self, state: GameState) -> Action:
        if state.can_raise:
            return state.all_in()
        return state.call() if state.to_call > 0 else state.check()


class RandomBot(Bot):
    name = "random"

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)

    def act(self, state: GameState) -> Action:
        r = self.rng.random()
        if state.can_raise and r < 0.2:
            span = state.max_raise_to - state.min_raise_to
            amount = state.min_raise_to + int(span * self.rng.random() * 0.25)
            return state.raise_to(amount)
        if state.to_call > 0:
            return state.call() if r < 0.85 else state.fold()
        return state.check()


BUILTINS: dict[str, type[Bot]] = {
    "call": CheckCallBot,
    "checkfold": CheckFoldBot,
    "allin": AllInBot,
    "random": RandomBot,
}
