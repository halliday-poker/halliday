"""Bot actions. A raise uses raise-to semantics: `amount` is the total bet
you are raising to for the current street, not the increment."""

from __future__ import annotations

from dataclasses import dataclass

ALL_IN = 10**9  # sentinel amount, clamped to the real all-in by the engine


@dataclass(frozen=True)
class Action:
    kind: str  # fold | check | call | raise
    amount: int = 0

    @staticmethod
    def fold() -> "Action":
        return Action("fold")

    @staticmethod
    def check() -> "Action":
        return Action("check")

    @staticmethod
    def call() -> "Action":
        return Action("call")

    @staticmethod
    def raise_to(amount: int) -> "Action":
        return Action("raise", int(amount))

    @staticmethod
    def all_in() -> "Action":
        return Action("raise", ALL_IN)

    def to_wire(self) -> dict:
        if self.kind == "raise":
            return {"action": "raise", "amount": self.amount}
        return {"action": self.kind}

    @staticmethod
    def from_wire(msg: dict) -> "Action":
        kind = str(msg.get("action", "")).lower()
        if kind in ("fold", "check", "call"):
            return Action(kind)
        if kind in ("raise", "bet"):
            return Action("raise", int(msg.get("amount", 0)))
        if kind in ("allin", "all-in", "all_in"):
            return Action("raise", ALL_IN)
        raise ValueError(f"unknown action {msg!r}")
