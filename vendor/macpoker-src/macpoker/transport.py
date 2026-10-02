"""Transports connect the match runner to bots.

InProcessTransport runs a Bot instance in the engine's own process (fast,
used for local dev). SubprocessTransport speaks the newline-delimited JSON
protocol over a child process's stdin/stdout — the same mechanism the judge
uses with sandboxed containers, so local subprocess play has full protocol
parity with production.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from collections import deque

from .actions import Action


class ProtocolError(Exception):
    pass


class BotDied(Exception):
    pass


class Transport:
    def start(self) -> None:
        pass

    def send(self, msg: dict) -> None:
        raise NotImplementedError

    def act(self, view: dict, timeout_ms: float) -> tuple[Action, float]:
        raise NotImplementedError

    def close(self) -> None:
        pass


class InProcessTransport(Transport):
    def __init__(self, bot, name: str | None = None):
        from .sdk import BotSession

        self.session = BotSession(bot)
        self.name = name or type(bot).__name__

    def send(self, msg: dict) -> None:
        try:
            self.session.handle(msg)
        except Exception as exc:  # bot bug
            raise BotDied(str(exc)) from exc

    def act(self, view: dict, timeout_ms: float) -> tuple[Action, float]:
        t0 = time.perf_counter()
        try:
            action = self.session.handle(view)
        except Exception as exc:
            raise BotDied(str(exc)) from exc
        elapsed_ms = (time.perf_counter() - t0) * 1000
        if action is None:
            raise ProtocolError("bot returned no action")
        if not isinstance(action, Action):
            raise ProtocolError(f"bot returned {action!r}, expected an Action")
        return action, elapsed_ms


class SubprocessTransport(Transport):
    def __init__(self, cmd: list[str], name: str | None = None):
        self.cmd = cmd
        self.name = name or " ".join(cmd[-1:])
        self.proc: subprocess.Popen | None = None
        self._lines: queue.Queue = queue.Queue()
        self._stderr_tail: deque[str] = deque(maxlen=200)

    def start(self) -> None:
        try:
            self.proc = subprocess.Popen(
                self.cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise BotDied(f"failed to start {self.cmd}: {exc}") from exc
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
            self._lines.put(line)
        self._lines.put(None)  # EOF sentinel

    def _read_stderr(self) -> None:
        assert self.proc and self.proc.stderr
        for line in self.proc.stderr:
            self._stderr_tail.append(line.rstrip("\n"))

    def stderr_tail(self) -> str:
        return "\n".join(self._stderr_tail)

    def send(self, msg: dict) -> None:
        if self.proc is None or self.proc.stdin is None or self.proc.poll() is not None:
            raise BotDied("bot process is not running")
        try:
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise BotDied(str(exc)) from exc

    def act(self, view: dict, timeout_ms: float) -> tuple[Action, float]:
        # drop any unsolicited output from before this request
        while True:
            try:
                stale = self._lines.get_nowait()
                if stale is None:
                    raise BotDied("bot exited")
            except queue.Empty:
                break
        t0 = time.perf_counter()
        self.send(view)
        try:
            line = self._lines.get(timeout=max(timeout_ms, 0) / 1000)
        except queue.Empty:
            raise TimeoutError("bot exceeded its clock")
        elapsed_ms = (time.perf_counter() - t0) * 1000
        if line is None:
            raise BotDied("bot exited mid-hand")
        try:
            return Action.from_wire(json.loads(line)), elapsed_ms
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise ProtocolError(f"bad action line {line!r}: {exc}") from exc

    def close(self) -> None:
        if self.proc is None:
            return
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
