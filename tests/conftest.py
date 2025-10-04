"""Pytest configuration to ensure project packages are importable."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _PROJECT_ROOT / "src"

# Prepend paths so tests can import the project modules (e.g. `src.analytics`).
for path in (_SRC_PATH, _PROJECT_ROOT):
    str_path = str(path)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)
