"""Sparring opponent whose behaviour drifts during a game. Never submitted.

It starts as a random archetype from param.py, plus a shover. Every hand there is
a CHANGE chance (5%) that it changes: half the time it switches to a different
archetype outright (e.g. shover -> station), otherwise it rescales one to three of
its settings by 0.5-1.5x. Tests whether a bot's reads go stale when opponents change.

Drift has its own random generator, seeded at construction from the global
`random` state. The harness seeds that per game, so every candidate at a table
faces the identical sequence of changes; decisions use a separate generator.
"""

import random

import param

CHANGE = 0.05        # chance per hand of a change
SWITCH_SHARE = 0.5   # share of changes that switch archetype (the rest adjust settings)

SHOVER = dict(vpip=.45, pfr=.45, threebet=.45, limp=0.0, aggression=.9, cbet=.9,
              bluff=.5, stickiness=.6, size=1.0, adaptive=0, shove=.9)
STYLES = {**{k: dict(v, shove=0.0) for k, v in param.ARCHETYPES.items()}, "shover": SHOVER}
TUNABLE = [k for k in SHOVER if k != "adaptive"]


class DrifterBot(param.ParamBot):
    def __init__(self, seed=None):
        rng = random.Random(seed if seed is not None else random.random())
        self.drift = random.Random(rng.random())
        self.archetype = self.drift.choice(sorted(STYLES))
        super().__init__(style=self._fresh(self.archetype), seed=rng.random())
        self.changes = []  # (hand, what changed), for debugging

    def _fresh(self, name):
        centre = STYLES[name]
        s = {k: v if k == "adaptive" else v * self.drift.uniform(0.8, 1.2) for k, v in centre.items()}
        return param._clamp_style(s)

    def on_hand_start(self, info):
        if self.drift.random() >= CHANGE:
            return
        if self.drift.random() < SWITCH_SHARE:
            new = self.drift.choice(sorted(n for n in STYLES if n != self.archetype))
            self.changes.append((info.get("hand"), f"{self.archetype} -> {new}"))
            self.archetype, self.base = new, self._fresh(new)
        else:
            keys = self.drift.sample(TUNABLE, self.drift.randint(1, 3))
            for k in keys:
                old = self.base[k] or 0.1  # lets a zero setting (e.g. shove) switch on
                self.base[k] = old * self.drift.uniform(0.5, 1.5)
            self.base = param._clamp_style(self.base)
            self.changes.append((info.get("hand"), f"{self.archetype} adjusted {', '.join(keys)}"))

    def preflop(self, state, s):
        if (s.get("shove", 0) > 0 and state.can_raise
                and param.hand_percentile(state.hole) < s["vpip"] and self.rng.random() < s["shove"]):
            return state.all_in()
        return super().preflop(state, s)
