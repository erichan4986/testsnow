#!/usr/bin/env python3
"""One-command preparation of annual-report cache, narrative cards preview, and optional knowledge notes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
UTILS_DIR = PROJECT_ROOT / "scripts" / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from periodic_report_cache import (  # noqa: E402
    PeriodicReportCacheResult,
    _download_url_bytes,
    _load_cninfo_disclosures,
    cache_periodic_report_from_url,
    discover_cninfo_annual_report,
)
from periodic_report_evidence_pack import build_periodic_report_evidence_pack  # noqa: E402
from periodic_report_narrative_card_note_writer import (  # noqa: E402
    write_periodic_report_narrative_card_notes,
)
from periodic_report_narrative_cards_preview import (  # noqa: E402
    _safe_filename,
    build_preview_markdown,
)
from periodic_report_narrative_evidence_cards import (  # noqa: E402
    build_periodic_report_narrative_evidence_cards,
)
from hk_periodic_report_fetcher import discover_hkex_periodic_report  # noqa: E402


DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "periodic_reports"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "stocks.json"
DEFAULT_BASE_DIR = PROJECT_ROOT / "knowledge"


def _load_stock_entry_from_config(config_path: str | Path, stock: str) -> dict:
    """Find a stock entry in config by name, code, xueqiu_code, or gid."""
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


def _infer_market_from_stock_entry(entry: dict) -> str:
    """Infer market label ('A', 'HK', or '') from a stock config entry."""
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


def _cache_discovered_report(
    *,
    discovery: dict,
    stock_name: str,
    stock_code: str,
    report_year: int,
    market: str,
    cache_dir: str | Path,
    report_type: str,
    downloader: Any = _download_url_bytes,
) -> PeriodicReportCacheResult:
    """Cache a discovered periodic report from its PDF URL."""
    return cache_periodic_report_from_url(
        stock_name=stock_name,
        stock_code=stock_code,
        report_year=report_year,
        market=market,
        url=discovery["url"],
        cache_dir=cache_dir,
        report_type=report_type,
        downloader=downloader,
    )


def _default_preview_path(
    stock_name: str, stock_code: str, report_year: int, report_type: str
) -> Path:
    """Return the default /tmp preview path."""
    label = stock_name or stock_code or "unknown"
    safe = _safe_filename(label)
    return (
        Path("/tmp")
        / f"{safe}_{int(report_year)}_{_safe_filename(report_type)}_narrative_cards_preview.md"
    )


def prepare_annual_report_materials(
    *,
    stock: str,
    year: int,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    report_type: str = "annual",
    preview_output: Optional[str] = None,
    write_knowledge: bool = False,
    base_dir: str | Path = DEFAULT_BASE_DIR,
    _downloader: Any = _download_url_bytes,
    _cninfo_loader: Any = _load_cninfo_disclosures,
    _hkex_discoverer: Any = discover_hkex_periodic_report,
) -> Dict[str, Any]:
    """Prepare cache, narrative cards preview, and optional knowledge notes.

    Returns a dict suitable for JSON CLI output.
    """
    entry = _load_stock_entry_from_config(config_path, stock)
    stock_name = str(entry.get("name") or stock)
    stock_code = str(entry.get("code") or "")
    market = _infer_market_from_stock_entry(entry)
    annual_url = str(entry.get("annual_report_url") or "").strip()

    # 1. Prepare cache
    if annual_url:
        cache_result = cache_periodic_report_from_url(
            stock_name=stock_name,
            stock_code=stock_code,
            report_year=year,
            market=market,
            url=annual_url,
            cache_dir=cache_dir,
            report_type=report_type,
            downloader=_downloader,
        )
    elif market == "A":
        discovery = discover_cninfo_annual_report(
            stock_code=stock_code,
            report_year=year,
            disclosure_loader=_cninfo_loader,
        )
        cache_result = _cache_discovered_report(
            discovery=discovery,
            stock_name=stock_name,
            stock_code=stock_code,
            report_year=year,
            market=market,
            cache_dir=cache_dir,
            report_type=report_type,
            downloader=_downloader,
        )
    elif market == "HK":
        discovery = _hkex_discoverer(
            stock_code=stock_code,
            report_year=year,
            report_type=report_type,
        )
        cache_result = _cache_discovered_report(
            discovery=discovery,
            stock_name=stock_name,
            stock_code=stock_code,
            report_year=year,
            market=market,
            cache_dir=cache_dir,
            report_type=report_type,
            downloader=_downloader,
        )
    else:
        raise SystemExit(
            f"Cannot determine cache strategy for {stock}: market={market!r} and no annual_report_url"
        )

    # 2. Build evidence pack and narrative cards
    raw_text = Path(cache_result.text_path).read_text(encoding="utf-8", errors="ignore")
    evidence_pack = build_periodic_report_evidence_pack(raw_text, report_type=report_type)
    cards_pack = build_periodic_report_narrative_evidence_cards(
        stock_code=stock_code,
        stock_name=stock_name,
        report_year=year,
        report_type=report_type,
        evidence_pack=evidence_pack,
        raw_text=raw_text,
    )

    # 3. Write preview markdown
    preview_path = Path(
        preview_output
        if preview_output
        else _default_preview_path(stock_name, stock_code, year, report_type)
    )
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_markdown = build_preview_markdown(
        stock_code=stock_code,
        stock_name=stock_name,
        cache_dir=cache_dir,
        report_type=report_type,
        report_year=year,
        write_knowledge=False,
    )
    preview_path.write_text(preview_markdown, encoding="utf-8")

    # 4. Optionally write knowledge notes
    knowledge_written_count = 0
    if write_knowledge:
        write_plan = write_periodic_report_narrative_card_notes(
            stock_name=stock_name,
            stock_code=stock_code,
            card_pack=cards_pack,
            base_dir=base_dir,
            dry_run=False,
        )
        knowledge_written_count = len(write_plan.written)

    return {
        "stock_name": stock_name,
        "stock_code": stock_code,
        "market": market,
        "report_year": year,
        "report_type": report_type,
        "text_path": str(cache_result.text_path),
        "meta_path": str(cache_result.meta_path),
        "preview_path": str(preview_path),
        "evidence_blocks_count": len(evidence_pack.get("blocks") or []),
        "cards_count": len(cards_pack.get("cards") or []),
        "wrote_knowledge": write_knowledge,
        "knowledge_written_count": knowledge_written_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare annual report cache, narrative cards preview, and optional knowledge notes."
    )
    parser.add_argument("--stock", required=True, help="Stock name or code from config")
    parser.add_argument("--year", type=int, required=True, help="Report year")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to stocks config JSON (default: config/stocks.json)",
    )
    parser.add_argument(
        "--cache-dir",
        default=str(DEFAULT_CACHE_DIR),
        help="Cache output directory (default: data/raw/periodic_reports)",
    )
    parser.add_argument(
        "--report-type",
        default="annual",
        help="Report type (default: annual)",
    )
    parser.add_argument(
        "--preview-output",
        default="",
        help="Override default /tmp preview markdown output path",
    )
    parser.add_argument(
        "--write-knowledge",
        action="store_true",
        help="Write narrative card notes to knowledge/10-Stocks/<stock>/periodic_narrative_cards/",
    )
    parser.add_argument(
        "--base-dir",
        default=str(DEFAULT_BASE_DIR),
        help="Knowledge base directory (default: knowledge)",
    )
    args = parser.parse_args(argv)

    result = prepare_annual_report_materials(
        stock=args.stock,
        year=args.year,
        config_path=args.config,
        cache_dir=args.cache_dir,
        report_type=args.report_type,
        preview_output=args.preview_output or None,
        write_knowledge=args.write_knowledge,
        base_dir=args.base_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
