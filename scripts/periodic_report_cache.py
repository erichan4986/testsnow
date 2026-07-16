#!/usr/bin/env python3
"""Prepare periodic report files in the standard local cache.

The command writes only data/raw/periodic_reports cache files.  It can register
local txt/pdf files, download a provided official PDF URL, or discover A-share
annual reports through CNINFO.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _path_bootstrap import prepend_sys_path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
UTILS_DIR = PROJECT_ROOT / "scripts" / "utils"
prepend_sys_path(UTILS_DIR)

from periodic_report_cache import (  # noqa: E402
    _download_url_bytes,
    _load_cninfo_disclosures,
    cache_periodic_report,
    cache_periodic_report_from_url,
    discover_cninfo_annual_report,
)
from hk_periodic_report_fetcher import discover_hkex_periodic_report  # noqa: E402


DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "periodic_reports"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "stocks.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Register a local annual/semiannual report txt/pdf into data/raw/periodic_reports, "
            "or discover an A-share annual report announcement via CNINFO."
        )
    )
    parser.add_argument("--discover-cninfo", action="store_true", help="Only discover A-share annual report URL via CNINFO")
    parser.add_argument("--discover-hkex", action="store_true", help="Only discover HK annual/interim report URL via HKEX")
    parser.add_argument("--download-discovered", action="store_true", help="With --discover-cninfo, download the discovered URL into cache")
    parser.add_argument("--from-config", action="store_true", help="Read stock metadata and annual_report_url from config/stocks.json")
    parser.add_argument("--download-url", help="Download this periodic report URL and register it into cache")
    parser.add_argument("--stock", help="Stock name, e.g. 黑芝麻智能")
    parser.add_argument("--code", help="Stock code, e.g. 02533 or 300661")
    parser.add_argument("--year", type=int, help="Report year, e.g. 2025")
    parser.add_argument("--market", help="Market label, e.g. A, HK, US")
    parser.add_argument("--input", help="Local txt/pdf path")
    parser.add_argument("--report-type", default="annual", help="Report type, default annual")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Output cache dir")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Stock config JSON path")
    parser.add_argument("--official-url", default="", help="Optional official report URL")
    parser.add_argument("--encoding", default="utf-8", help="Text input encoding")
    parser.add_argument("--lang", default="ZH", help="Disclosure search language for HKEX, default ZH")
    args = parser.parse_args(argv)

    if args.from_config:
        if not args.stock or not args.year:
            parser.error("--from-config requires --stock and --year")
        stock_cfg = _load_stock_entry_from_config(args.config, args.stock)
        stock_name = str(stock_cfg.get("name") or args.stock)
        stock_code = str(stock_cfg.get("code") or args.code or "")
        if not stock_code:
            parser.error("--from-config stock entry must include code")
        market = args.market or _infer_market_from_stock_entry(stock_cfg)
        annual_report_url = str(stock_cfg.get("annual_report_url") or "").strip()
        if annual_report_url:
            result = cache_periodic_report_from_url(
                stock_name=stock_name,
                stock_code=stock_code,
                report_year=args.year,
                market=market,
                url=annual_report_url,
                cache_dir=args.cache_dir,
                report_type=args.report_type,
                downloader=_download_url_bytes,
            )
            print(json.dumps(result.to_cli_payload(), ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if market == "A":
            discovery = discover_cninfo_annual_report(
                stock_code=stock_code,
                report_year=args.year,
                disclosure_loader=_load_cninfo_disclosures,
            )
        elif market == "HK":
            discovery = discover_hkex_periodic_report(
                stock_code=stock_code,
                report_year=args.year,
                report_type=args.report_type,
                lang=args.lang,
            )
        else:
            parser.error(
                "--from-config requires annual_report_url for non-A/HK markets; "
                "use --download-url or --input for local reports"
            )
        result = _cache_discovered_report(
            discovery=discovery,
            stock_name=stock_name,
            stock_code=stock_code,
            report_year=args.year,
            market=market,
            cache_dir=args.cache_dir,
            report_type=args.report_type,
        )
        print(json.dumps(result.to_cli_payload(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0

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

    if args.discover_hkex:
        if not args.code or not args.year:
            parser.error("--discover-hkex requires --code and --year")
        discovery = discover_hkex_periodic_report(
            stock_code=args.code,
            report_year=args.year,
            report_type=args.report_type,
            lang=args.lang,
        )
        if not args.download_discovered:
            print(json.dumps(discovery, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if not args.stock:
            parser.error("--download-discovered requires --stock")
        result = _cache_discovered_report(
            discovery=discovery,
            stock_name=args.stock,
            stock_code=args.code,
            report_year=args.year,
            market=args.market or "HK",
            cache_dir=args.cache_dir,
            report_type=args.report_type,
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


def _load_stock_entry_from_config(config_path: str | Path, stock: str) -> dict:
    path = Path(config_path)
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"stock config not found: {path}") from None
    if not isinstance(entries, list):
        raise SystemExit(f"stock config must be a list: {path}")

    target = str(stock)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        names = {
            str(entry.get("name") or ""),
            str(entry.get("code") or ""),
            str(entry.get("xueqiu_code") or ""),
            str(entry.get("gid") or ""),
        }
        if target in names:
            return entry
    raise SystemExit(f"stock not found in config: {stock}")


def _cache_discovered_report(
    *,
    discovery: dict,
    stock_name: str,
    stock_code: str,
    report_year: int,
    market: str,
    cache_dir: str | Path,
    report_type: str,
):
    return cache_periodic_report_from_url(
        stock_name=stock_name,
        stock_code=stock_code,
        report_year=report_year,
        market=market,
        url=discovery["url"],
        cache_dir=cache_dir,
        report_type=report_type,
        downloader=_download_url_bytes,
    )


def _infer_market_from_stock_entry(entry: dict) -> str:
    explicit = str(entry.get("market") or "").upper()
    if explicit:
        return explicit
    xueqiu_code = str(entry.get("xueqiu_code") or "").upper()
    if xueqiu_code.startswith("HK"):
        return "HK"
    code = str(entry.get("code") or "")
    if code.isdigit() and len(code) == 6:
        return "A"
    return "HK" if code.startswith("0") and len(code) == 5 else ""


if __name__ == "__main__":
    raise SystemExit(main())
