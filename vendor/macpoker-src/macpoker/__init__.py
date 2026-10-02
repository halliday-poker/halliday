"""macpoker — engine and bot SDK for the MAC poker bot tournament."""

from .actions import Action
from .match import MatchConfig, MatchResult, MatchRunner
from .sdk import Bot, GameState, load_bot_from_file, run_bot

__version__ = "0.1.0"

__all__ = [
    "Action",
    "Bot",
    "GameState",
    "MatchConfig",
    "MatchResult",
    "MatchRunner",
    "load_bot_from_file",
    "run_bot",
    "__version__",
]
