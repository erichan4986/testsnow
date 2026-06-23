#!/usr/bin/env python3
"""Register a local periodic report file into the standard cache.

This command is intentionally local-only: it does not download reports, access
the network, or write reports/Knowledge.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
UTILS_DIR = PROJECT_ROOT / "scripts" / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from periodic_report_cache import cache_periodic_report  # noqa: E402


DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "periodic_reports"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Register a local annual/semiannual report txt/pdf into data/raw/periodic_reports."
    )
    parser.add_argument("--stock", required=True, help="Stock name, e.g. 黑芝麻智能")
    parser.add_argument("--code", required=True, help="Stock code, e.g. 02533 or 300661")
    parser.add_argument("--year", required=True, type=int, help="Report year, e.g. 2025")
    parser.add_argument("--market", required=True, help="Market label, e.g. A, HK, US")
    parser.add_argument("--input", required=True, help="Local txt/pdf path")
    parser.add_argument("--report-type", default="annual", help="Report type, default annual")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Output cache dir")
    parser.add_argument("--official-url", default="", help="Optional official report URL")
    parser.add_argument("--encoding", default="utf-8", help="Text input encoding")
    args = parser.parse_args()

    result = cache_periodic_report(
        stock_name=args.stock,
        stock_code=args.code,
        report_year=args.year,
        market=args.market,
        input_path=args.input,
        cache_dir=args.cache_dir,
        report_type=args.report_type,
        official_url=args.official_url,
        encoding=args.encoding,
    )
    print(json.dumps(result.to_cli_payload(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
