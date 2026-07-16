#!/usr/bin/env python3
"""Preview periodic-report cards from local cache and optionally persist pack/view."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Union


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UTILS_DIR = PROJECT_ROOT / "scripts" / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from periodic_report_evidence_pack import build_periodic_report_evidence_pack  # noqa: E402
from periodic_report_narrative_evidence_cards import (  # noqa: E402
    SOURCE_TYPE,
    build_periodic_report_narrative_evidence_cards,
)
from periodic_report_narrative_pack_store import write_periodic_report_narrative_pack  # noqa: E402
from periodic_report_narrative_view_writer import write_periodic_report_narrative_view  # noqa: E402


DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "periodic_reports"


def default_output_path(stock_name: str, stock_code: str, report_type: str) -> Path:
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
    knowledge_base_dir: Optional[Union[str, Path]] = None,
    write_knowledge: bool = False,
    refresh_existing: bool = False,
    refresh_frontmatter_only: bool = False,
    existing_only: bool = False,
) -> str:
    if refresh_existing or refresh_frontmatter_only or existing_only:
        raise ValueError("legacy_note_options_removed")
    if write_knowledge and not knowledge_base_dir:
        raise ValueError("knowledge_base_dir_required")

    cache_path = _find_cache_file(
        cache_dir=cache_dir, stock_code=stock_code, stock_name=stock_name,
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
    ]
    if write_knowledge:
        pack = write_periodic_report_narrative_pack(
            stock_name=title_name, stock_code=stock_code,
            card_pack=cards_pack, base_dir=knowledge_base_dir,
        )
        view = write_periodic_report_narrative_view(
            stock_name=title_name, stock_code=stock_code,
            report_year=report_year, report_type=report_type,
            base_dir=knowledge_base_dir,
        )
        lines.extend((
            "- knowledge_write_mode：`pack_and_view`",
            "",
            "## Knowledge outputs",
            "",
            f"- periodic_narrative_pack：`{pack.pack_path}` ({pack.state})",
            f"- periodic_narrative_manifest：`{pack.manifest_path}`",
            f"- periodic_narrative_view：`{view.view_path}` ({view.state})",
            f"- displayed_cards：{view.displayed_cards} / {view.total_cards}",
        ))
    elif knowledge_base_dir:
        lines.append("- knowledge_write_mode：`disabled`")
    lines.append("")

    if not cards_pack.get("cards"):
        lines.extend(("未抽取到 narrative evidence cards。", ""))
    for idx, card in enumerate(cards_pack.get("cards") or [], 1):
        family = card.get("argument_family") or card.get("card_type", "")
        lines.extend((
            f"## {idx}. {card.get('title', '')} / `{family}`",
            "",
            f"- card_id：`{card.get('card_id', '')}`",
            f"- source_block_id：`{card.get('source_block_id', '')}`",
            f"- source_credit：`{card.get('source_credit', '')}`",
            "",
            "> " + str(card.get("source_excerpt", "")),
            "",
        ))
    if include_json:
        lines.extend((
            "## JSON", "", "```json",
            json.dumps(cards_pack, ensure_ascii=False, indent=2),
            "```", "",
        ))
    return "\n".join(lines)


def _find_cache_file(
    *, cache_dir: Union[str, Path], stock_code: str, stock_name: str,
    report_type: str,
) -> Optional[Path]:
    root = Path(cache_dir)
    if not root.exists():
        return None
    report_token = _report_token(report_type)
    needles = [token for token in (stock_name, stock_code) if token]
    candidates = sorted(
        path for path in root.rglob("*.txt")
        if report_token in path.name.lower()
        and ("jina" in path.name.lower() or "annual" in path.name.lower()
             or "semiannual" in path.name.lower())
    )
    for path in candidates:
        if any(needle in path.name for needle in needles):
            return path
    return candidates[0] if len(candidates) == 1 else None


def _report_token(report_type: str) -> str:
    text = str(report_type or "annual").lower()
    return "semiannual" if "semi" in text or "interim" in text else "annual"


def _safe_filename(value: str) -> str:
    text = str(value or "").strip()
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text) or "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render local periodic-report narrative evidence cards preview"
    )
    parser.add_argument("--stock-code", required=True, help="Stock code, e.g. 300777")
    parser.add_argument("--stock-name", default="", help="Optional stock name for cache matching")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--report-type", default="annual", choices=[
        "annual", "annual_report", "semiannual", "semiannual_report", "interim_report",
    ])
    parser.add_argument("--report-year", type=int, default=2025)
    parser.add_argument("--include-json", action="store_true")
    parser.add_argument("--output")
    parser.add_argument("--knowledge-base-dir", help="Knowledge root for pack/view output")
    parser.add_argument("--write-knowledge", action="store_true", help="Write pack and human view")
    parser.add_argument("--refresh-existing", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--refresh-frontmatter-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--existing-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    try:
        markdown = build_preview_markdown(
            stock_code=args.stock_code, stock_name=args.stock_name,
            cache_dir=args.cache_dir, report_type=args.report_type,
            report_year=args.report_year, include_json=args.include_json,
            knowledge_base_dir=args.knowledge_base_dir,
            write_knowledge=args.write_knowledge,
            refresh_existing=args.refresh_existing,
            refresh_frontmatter_only=args.refresh_frontmatter_only,
            existing_only=args.existing_only,
        )
    except ValueError as exc:
        if str(exc) in {"legacy_note_options_removed", "knowledge_base_dir_required"}:
            parser.error(str(exc))
        raise
    out_path = Path(args.output) if args.output else default_output_path(
        args.stock_name, args.stock_code, args.report_type,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
