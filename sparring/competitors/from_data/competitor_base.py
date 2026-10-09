"""Shared ParamBot scaffold for the generated offline competitors."""

import importlib.util
from pathlib import Path
import random


# Resolve the scaffold relative to this file, including when the SDK loads a
# competitor from outside the repository root. Do not shadow another bot's
# top-level `param` module or change the process import path.
_path = Path(__file__).resolve().parents[2] / "param.py"
_spec = importlib.util.spec_from_file_location("_competitor_param", _path)
_param = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_param)


class FittedBot(_param.ParamBot):
    """Use the fitted style unchanged; every game gets fresh counters and RNG."""

    def __init__(self, seed=None):
        super().__init__(style=self.STYLE,
                         seed=seed if seed is not None else random.getrandbits(128))
