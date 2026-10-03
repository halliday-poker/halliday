"""Offline opponent estimation. Never imported by the submitted bot."""

import importlib.util
from pathlib import Path
import sys

if importlib.util.find_spec("macpoker") is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor" / "macpoker-src"))
