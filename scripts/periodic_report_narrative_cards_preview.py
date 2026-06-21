#!/usr/bin/env python3
"""Render local periodic-report narrative evidence cards from cached report text.

This is a standalone helper-only preview entrypoint. It reads local cache files,
does not call LLMs, does not access the network, and does not write to reports/
or knowledge/.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Union


PROJECT_ROOT = Path(__file__).resolve().parent.parent
UTILS_DIR = PROJECT_ROOT / "scripts" / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from periodic_report_evidence_pack import build_periodic_report_evidence_pack  # noqa: E402
from periodic_report_narrative_evidence_cards import (  # noqa: E402
    SOURCE_TYPE,
    build_periodic_report_narrative_evidence_cards,
)


DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "periodic_reports"


def default_output_path(stock_name: str, stock_code: str, report_type: str) -> Path:
    """Return the default /tmp preview path."""
    label = stock_name or stock_code or "unknown"
    code = stock_code or "unknown"
    return Path("/tmp") / (
        f"{_safe_filename(label)}_{_safe_filename(code)}_"
        f"{_safe_filename(report_type or 'annual')}_narrative_cards_preview.md"
    )


def build_preview_markdown(
    *,
    stock_code: str,
    stock_name: str = "",
    cache_dir: Union[str, Path] = DEFAULT_CACHE_DIR,
    report_type: str = "annual",
    report_year: int = 2025,
    include_json: bool = False,
) -> str:
    """Build deterministic Markdown preview from a local report cache."""
    cache_path = _find_cache_file(
        cache_dir=cache_dir,
        stock_code=stock_code,
        stock_name=stock_name,
        report_type=report_type,
    )
    title_name = stock_name or stock_code or "未知公司"
    header = [
        "# 定期报告 Narrative Evidence Cards Preview",
        "",
        f"- 股票：{title_name}",
        f"- 代码：{stock_code or '—'}",
        f"- 报告类型：{report_type}",
        f"- 来源类型：{SOURCE_TYPE}",
        f"- 缓存目录：{Path(cache_dir)}",
        "",
    ]
    if not cache_path:
        return "\n".join(header + ["未找到本地年报缓存。", ""])

    raw_text = cache_path.read_text(encoding="utf-8", errors="ignore")
    evidence_pack = build_periodic_report_evidence_pack(raw_text, report_type=report_type)
    cards_pack = build_periodic_report_narrative_evidence_cards(
        stock_code=stock_code,
        stock_name=title_name,
        report_year=report_year,
        report_type=report_type,
        evidence_pack=evidence_pack,
        raw_text=raw_text,
    )

    lines = header + [
        f"- 缓存文件：`{cache_path}`",
        f"- evidence blocks：{len(evidence_pack.get('blocks') or [])}",
        f"- cards：{len(cards_pack.get('cards') or [])}",
        "",
    ]
    if not cards_pack.get("cards"):
        lines.extend(["未抽取到 narrative evidence cards。", ""])
    for idx, card in enumerate(cards_pack.get("cards") or [], 1):
        lines.extend([
            f"## {idx}. {card.get('title', '')} / `{card.get('card_type', '')}`",
            "",
            f"- card_id：`{card.get('card_id', '')}`",
            f"- source_block_id：`{card.get('source_block_id', '')}`",
            f"- confidence：`{card.get('confidence', '')}`",
            f"- source_credit：`{card.get('source_credit', '')}`",
            f"- keywords：`{', '.join(card.get('keywords') or [])}`",
            "",
            "> " + str(card.get("source_excerpt", "")),
            "",
        ])
    if include_json:
        lines.extend([
            "## JSON",
            "",
            "```json",
            json.dumps(cards_pack, ensure_ascii=False, indent=2),
            "```",
            "",
        ])
    return "\n".join(lines)


def _find_cache_file(
    *,
    cache_dir: Union[str, Path],
    stock_code: str,
    stock_name: str,
    report_type: str,
) -> Optional[Path]:
    root = Path(cache_dir)
    if not root.exists():
        return None
    report_token = _report_token(report_type)
    needles = [token for token in (stock_name, stock_code) if token]
    candidates = sorted(
        path
        for path in root.rglob("*.txt")
        if report_token in path.name.lower()
        and ("jina" in path.name.lower() or "annual" in path.name.lower() or "semiannual" in path.name.lower())
    )
    for path in candidates:
        if any(needle in path.name for needle in needles):
            return path
    return candidates[0] if len(candidates) == 1 else None


def _report_token(report_type: str) -> str:
    text = str(report_type or "annual").lower()
    if "semi" in text or "interim" in text:
        return "semiannual"
    return "annual"


def _safe_filename(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render local periodic-report narrative evidence cards preview"
    )
    parser.add_argument("--stock-code", required=True, help="Stock code, e.g. 300777")
    parser.add_argument("--stock-name", default="", help="Optional stock name used for cache matching and title")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Local periodic report cache directory")
    parser.add_argument("--report-type", default="annual", choices=["annual", "annual_report", "semiannual", "semiannual_report", "interim_report"])
    parser.add_argument("--report-year", type=int, default=2025, help="Report year used in stable card ids")
    parser.add_argument("--include-json", action="store_true", help="Append raw card pack JSON")
    parser.add_argument("--output", help="Output markdown path; defaults to /tmp")
    args = parser.parse_args(argv)

    markdown = build_preview_markdown(
        stock_code=args.stock_code,
        stock_name=args.stock_name,
        cache_dir=args.cache_dir,
        report_type=args.report_type,
        report_year=args.report_year,
        include_json=args.include_json,
    )
    out_path = Path(args.output) if args.output else default_output_path(
        args.stock_name,
        args.stock_code,
        args.report_type,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
