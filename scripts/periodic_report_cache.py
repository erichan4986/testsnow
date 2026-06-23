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

from periodic_report_cache import (  # noqa: E402
    _download_url_bytes,
    _load_cninfo_disclosures,
    cache_periodic_report,
    cache_periodic_report_from_url,
    discover_cninfo_annual_report,
)


DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "periodic_reports"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Register a local annual/semiannual report txt/pdf into data/raw/periodic_reports, "
            "or discover an A-share annual report announcement via CNINFO."
        )
    )
    parser.add_argument("--discover-cninfo", action="store_true", help="Only discover A-share annual report URL via CNINFO")
    parser.add_argument("--download-discovered", action="store_true", help="With --discover-cninfo, download the discovered URL into cache")
    parser.add_argument("--download-url", help="Download this periodic report URL and register it into cache")
    parser.add_argument("--stock", help="Stock name, e.g. 黑芝麻智能")
    parser.add_argument("--code", help="Stock code, e.g. 02533 or 300661")
    parser.add_argument("--year", type=int, help="Report year, e.g. 2025")
    parser.add_argument("--market", help="Market label, e.g. A, HK, US")
    parser.add_argument("--input", help="Local txt/pdf path")
    parser.add_argument("--report-type", default="annual", help="Report type, default annual")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Output cache dir")
    parser.add_argument("--official-url", default="", help="Optional official report URL")
    parser.add_argument("--encoding", default="utf-8", help="Text input encoding")
    args = parser.parse_args(argv)

    if args.discover_cninfo:
        if not args.code or not args.year:
            parser.error("--discover-cninfo requires --code and --year")
        discovery = discover_cninfo_annual_report(
            stock_code=args.code,
            report_year=args.year,
            disclosure_loader=_load_cninfo_disclosures,
        )
        if not args.download_discovered:
            print(json.dumps(discovery, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if not args.stock:
            parser.error("--download-discovered requires --stock")
        result = cache_periodic_report_from_url(
            stock_name=args.stock,
            stock_code=args.code,
            report_year=args.year,
            market=args.market or "A",
            url=discovery["url"],
            cache_dir=args.cache_dir,
            report_type=args.report_type,
            downloader=_download_url_bytes,
        )
        print(json.dumps(result.to_cli_payload(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.download_url:
        required = {
            "--stock": args.stock,
            "--code": args.code,
            "--year": args.year,
            "--market": args.market,
        }
        missing = [name for name, value in required.items() if value in (None, "")]
        if missing:
            parser.error(f"{', '.join(missing)} required with --download-url")
        result = cache_periodic_report_from_url(
            stock_name=args.stock,
            stock_code=args.code,
            report_year=args.year,
            market=args.market,
            url=args.download_url,
            cache_dir=args.cache_dir,
            report_type=args.report_type,
            downloader=_download_url_bytes,
        )
        print(json.dumps(result.to_cli_payload(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    required = {
        "--stock": args.stock,
        "--code": args.code,
        "--year": args.year,
        "--market": args.market,
        "--input": args.input,
    }
    missing = [name for name, value in required.items() if value in (None, "")]
    if missing:
        parser.error(f"{', '.join(missing)} required unless --discover-cninfo is set")

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
