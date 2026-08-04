"""Shared import-path bootstrap for direct command-line scripts."""

from __future__ import annotations

import sys
from pathlib import Path


def prepend_sys_path(path: str | Path) -> str:
    """Put one canonical path first while preserving unrelated entries."""
    canonical = str(Path(path).resolve())
    target = Path(canonical)
    retained = [
        entry for entry in sys.path if Path(entry or ".").resolve() != target
    ]
    sys.path[:] = [canonical, *retained]
    return canonical
