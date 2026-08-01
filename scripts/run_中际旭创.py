#!/usr/bin/env python3
"""Compatibility entry for the 中际旭创 single-stock report."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_stock_report import main as _run_generic_report

STOCK_NAME = "中际旭创"


def main(argv=None):
    return _run_generic_report(["--stock", STOCK_NAME, *(argv or [])])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
