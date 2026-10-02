"""Command line interface.

  macpoker play <seat> <seat> [...]   play a local duplicate set between 2-9 seats
  macpoker run-bot <spec>             stdio protocol runner (used in sandboxes)

Every argument after `play` is one seat at the table: a path to a python
file that defines a Bot, or a built-in house bot written as house:<name>
(house:call, house:checkfold, house:allin, house:random). Bare house-bot
names are accepted as a shorthand.

`play` runs a duplicate set like the tournament: one game per seat over the
same decks, every bot shifted one seat each game, and a fresh instance of
every bot for each game.
"""

from __future__ import annotations

import argparse
import json
import sys

from .bots import BUILTINS
from .match import VERDICT_OK, MatchConfig, play_set
from .sdk import Bot, load_bot_from_file, run_bot
from .transport import InProcessTransport, SubprocessTransport, Transport


def resolve_bot(spec: str) -> Bot:
    if spec.startswith(("house:", "builtin:")):
        name = spec.split(":", 1)[1]
        if name not in BUILTINS:
            raise SystemExit(
                f"unknown house bot {name!r}; available: {', '.join(sorted(BUILTINS))}"
            )
        return BUILTINS[name]()
    if spec in BUILTINS:
        return BUILTINS[spec]()
    return load_bot_from_file(spec)


def _make_transport(spec: str, use_subprocess: bool) -> Transport:
    if use_subprocess:
        return SubprocessTransport(
            [sys.executable, "-m", "macpoker", "run-bot", spec], name=spec
        )
    return InProcessTransport(resolve_bot(spec), name=spec)


def cmd_play(args: argparse.Namespace) -> int:
    specs = args.bots
    config = MatchConfig(
        seats=len(specs),
        deals=args.deals,
        stack=args.stack,
        sb=args.sb,
        bb=args.bb,
        seed=args.seed,
        base_time_ms=args.time_ms,
        increment_ms=args.increment_ms,
    )
    games = args.games if args.games is not None else len(specs)
    transports_by_game: list[list[Transport]] = []

    def make_transports(k: int) -> list[Transport]:
        transports = [_make_transport(s, args.subprocess) for s in specs]
        transports_by_game.append(transports)
        return transports

    results = play_set(config, make_transports, games=games)

    hands = config.deals * len(results)
    chips = [sum(r.chips[b] for r in results) for b in range(len(specs))]
    print(f"\n{hands} hands ({len(results)} game{'s' if len(results) != 1 else ''} x {config.deals} hands, same decks, seats shifted each game)")
    print(f"{'bot':<30}{'chips':>10}{'mbb/hand':>12}  verdict")
    for b in sorted(range(len(specs)), key=lambda b: -chips[b]):
        mbb = chips[b] / config.bb / max(hands, 1) * 1000
        bad = [(k, r.verdicts[b]) for k, r in enumerate(results) if r.verdicts[b] != VERDICT_OK]
        verdict = ", ".join(f"{v} (game {k + 1})" for k, v in bad) if bad else VERDICT_OK
        print(f"{specs[b]:<30}{chips[b]:>+10}{mbb:>12.1f}  {verdict}")
    for k, (r, transports) in enumerate(zip(results, transports_by_game)):
        for b, t in enumerate(transports):
            if isinstance(t, SubprocessTransport) and r.verdicts[b] != VERDICT_OK:
                tail = t.stderr_tail()
                if tail:
                    print(f"\n--- {specs[b]}, game {k + 1} stderr ---\n{tail}")

    if args.history:
        with open(args.history, "w") as f:
            config_args = {k: v for k, v in vars(args).items() if k != "func"}
            json.dump(
                {
                    "config": config_args,
                    "games": [{"result": r.to_dict(), "hands": r.hands} for r in results],
                },
                f,
            )
        print(f"\nhand history written to {args.history}")
    return 0


def cmd_run_bot(args: argparse.Namespace) -> int:
    run_bot(resolve_bot(args.spec))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="macpoker")
    sub = parser.add_subparsers(dest="command", required=True)

    play = sub.add_parser("play", help="play a local duplicate set between 2-9 seats")
    play.add_argument(
        "bots",
        nargs="+",
        metavar="SEAT",
        help="each seat is a .py bot file or a house bot: house:call, "
        "house:checkfold, house:allin, house:random (mix freely, e.g. "
        "`macpoker play mybot.py v2.py house:call`)",
    )
    play.add_argument("--deals", type=int, default=50, help="hands per game, one fresh deck each")
    play.add_argument("--games", type=int, default=None, help="games in the set (default: one per seat)")
    play.add_argument("--stack", type=int, default=200)
    play.add_argument("--sb", type=int, default=1)
    play.add_argument("--bb", type=int, default=2)
    play.add_argument("--seed", default="local")
    play.add_argument("--time-ms", type=int, default=30_000, dest="time_ms")
    play.add_argument("--increment-ms", type=int, default=100, dest="increment_ms")
    play.add_argument("--subprocess", action="store_true", help="run bots as subprocesses over the wire protocol")
    play.add_argument("--history", help="write full hand history JSON to this file")
    play.set_defaults(func=cmd_play)

    runbot = sub.add_parser("run-bot", help="stdio protocol runner (used inside sandboxes)")
    runbot.add_argument("spec")
    runbot.set_defaults(func=cmd_run_bot)

    args = parser.parse_args(argv)
    if getattr(args, "bots", None) is not None and not 2 <= len(args.bots) <= 9:
        parser.error("play needs between 2 and 9 bots")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
