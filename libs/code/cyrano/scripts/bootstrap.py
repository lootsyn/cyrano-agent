"""Activate only this dcode source tree for offline development."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def activate() -> Path:
    """Return the CYRANO root after registering the dcode root."""
    code_root = str(ROOT.parent)
    if code_root not in sys.path:
        sys.path.insert(0, code_root)
    return ROOT
