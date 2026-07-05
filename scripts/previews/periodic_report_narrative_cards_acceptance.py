#!/usr/bin/env python3
"""Dry-run acceptance diagnostics for periodic narrative evidence cards.

This CLI reads local periodic-report caches and renders a compact Markdown
quality view. It does not write Knowledge notes, does not call LLMs, and does
not access the network.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple, Union


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UTILS_DIR = PROJECT_ROOT / "scripts" / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from periodic_report_evidence_pack import build_periodic_report_evidence_pack  # noqa: E402
from periodic_report_narrative_evidence_cards import (  # noqa: E402
    build_periodic_report_narrative_evidence_cards,
)
from periodic_report_narrative_cards_preview import (  # noqa: E402
    DEFAULT_CACHE_DIR,
    _build_knowledge_maintenance_summary,
    _find_cache_file,
)


DEFAULT_OUTPUT = Path("/tmp/periodic_narrative_cards_acceptance.md")
_SHORT_EXCERPT_CHARS = 32
_DANGLING_START_RE = re.compile(r"^[，,；;。)、）]")
_DANGLING_START_PREFIXES = (
    "优化等举措",
    "续研发",
    "力、众多",
    "安全规范、",
)
_TABLE_FRAGMENT_TOKENS = ("□适用", "适用", "□不适用", "不适用", "产品名称", "适用 不适用")


def analyze_cards_pack(
    *,
    stock_code: str,
    stock_name: str,
    cards_pack: dict,
    maintenance_summary: Optional[dict] = None,
) -> dict:
    """Return compact acceptance diagnostics for a card pack."""
    cards = [card for card in (cards_pack.get("cards") or []) if isinstance(card, dict)]
    candidate_cards = [
        card
        for card in (cards_pack.get("candidate_cards") or cards)
        if isinstance(card, dict)
    ]
    card_type_counts = Counter(str(card.get("card_type") or "unknown") for card in cards)
    excerpt_hash_counts = Counter(
        str(card.get("source_excerpt_hash") or "")
        for card in cards
        if str(card.get("source_excerpt_hash") or "")
    )
    duplicate_excerpt_hashes = sum(count - 1 for count in excerpt_hash_counts.values() if count > 1)
    short_excerpts = sum(1 for card in cards if len(str(card.get("source_excerpt") or "").strip()) < _SHORT_EXCERPT_CHARS)
    dangling_start_excerpts = sum(
        1 for card in cards if _looks_like_dangling_start(str(card.get("source_excerpt") or ""))
    )
    table_fragment_excerpts = sum(
        1 for card in cards if _looks_like_table_fragment(str(card.get("source_excerpt") or ""))
    )
    quality_flags = {
        "duplicate_excerpt_hashes": duplicate_excerpt_hashes,
        "short_excerpts": short_excerpts,
        "dangling_start_excerpts": dangling_start_excerpts,
        "table_fragment_excerpts": table_fragment_excerpts,
    }
    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "selected_cards": len(cards),
        "candidate_cards": len(candidate_cards),
        "card_type_counts": dict(sorted(card_type_counts.items())),
        "quality_flags": quality_flags,
        "quality_flag_total": sum(quality_flags.values()),
        "maintenance": maintenance_summary or {},
    }


def build_acceptance_markdown(
    *,
    stocks: Sequence[Tuple[str, str]],
    cache_dir: Union[str, Path] = DEFAULT_CACHE_DIR,
    report_type: str = "annual",
    report_year: int = 2025,
    knowledge_base_dir: Optional[Union[str, Path]] = None,
) -> str:
    """Build acceptance Markdown for a stock list from local caches."""
    summaries = []
    lines = [
        "# 定期报告 Narrative Cards Acceptance",
        "",
        "- dry_run_only：true",
        f"- cache_dir：`{Path(cache_dir)}`",
        f"- report_type：{report_type}",
        f"- report_year：{report_year}",
        "",
    ]

    for stock_code, stock_name in stocks:
        cache_path = _find_cache_file(
            cache_dir=cache_dir,
            stock_code=stock_code,
            stock_name=stock_name,
            report_type=report_type,
        )
        if not cache_path:
            summaries.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "selected_cards": 0,
                "candidate_cards": 0,
                "card_type_counts": {},
                "quality_flags": {"missing_cache": 1},
                "quality_flag_total": 1,
                "maintenance": {},
                "cache_path": "",
            })
            continue
        raw_text = cache_path.read_text(encoding="utf-8", errors="ignore")
        evidence_pack = build_periodic_report_evidence_pack(raw_text, report_type=report_type)
        cards_pack = build_periodic_report_narrative_evidence_cards(
            stock_code=stock_code,
            stock_name=stock_name or stock_code,
            report_year=report_year,
            report_type=report_type,
            evidence_pack=evidence_pack,
            raw_text=raw_text,
        )
        maintenance = {}
        if knowledge_base_dir:
            maintenance = _build_knowledge_maintenance_summary(
                cards_pack=cards_pack,
                knowledge_base_dir=knowledge_base_dir,
                stock_name=stock_name or stock_code,
            )
        summary = analyze_cards_pack(
            stock_code=stock_code,
            stock_name=stock_name,
            cards_pack=cards_pack,
            maintenance_summary=maintenance,
        )
        summary["cache_path"] = str(cache_path)
        summary["evidence_blocks"] = len(evidence_pack.get("blocks") or [])
        summaries.append(summary)

    lines.extend(_render_overview_table(summaries))
    for summary in summaries:
        lines.extend(_render_stock_summary(summary))
    return "\n".join(lines)


def _looks_like_table_fragment(excerpt: str) -> bool:
    compact = re.sub(r"\s+", " ", excerpt)
    marker_count = sum(1 for token in _TABLE_FRAGMENT_TOKENS if token in compact)
    checkbox_count = compact.count("□") + compact.count("")
    return marker_count >= 2 or checkbox_count >= 2


def _looks_like_dangling_start(excerpt: str) -> bool:
    text = str(excerpt or "").strip()
    return bool(_DANGLING_START_RE.search(text)) or any(
        text.startswith(prefix) for prefix in _DANGLING_START_PREFIXES
    )


def _render_overview_table(summaries: Sequence[dict]) -> list[str]:
    lines = [
        "## Overview",
        "",
        "| 股票 | selected | candidates | quality_flags | dangling | moved | new |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in summaries:
        maintenance = summary.get("maintenance") or {}
        label = f"{summary.get('stock_name') or summary.get('stock_code')} `{summary.get('stock_code')}`"
        lines.append(
            "| {label} | {selected} | {candidates} | {flags} | {dangling} | {moved} | {new} |".format(
                label=label,
                selected=summary.get("selected_cards", 0),
                candidates=summary.get("candidate_cards", 0),
                flags=summary.get("quality_flag_total", 0),
                dangling=maintenance.get("dangling_notes", "—"),
                moved=maintenance.get("moved_or_reindexed_notes", "—"),
                new=maintenance.get("new_candidate_notes", "—"),
            )
        )
    lines.append("")
    return lines


def _render_stock_summary(summary: dict) -> list[str]:
    title = summary.get("stock_name") or summary.get("stock_code") or "unknown"
    lines = [
        f"## {title} `{summary.get('stock_code', '')}`",
        "",
        f"- cache：`{summary.get('cache_path') or 'missing'}`",
        f"- evidence_blocks：{summary.get('evidence_blocks', 0)}",
        f"- selected_cards：{summary.get('selected_cards', 0)}",
        f"- candidate_cards：{summary.get('candidate_cards', 0)}",
        "",
        "### card_type distribution",
        "",
    ]
    card_type_counts = summary.get("card_type_counts") or {}
    if card_type_counts:
        for card_type, count in card_type_counts.items():
            lines.append(f"- {card_type}: {count}")
    else:
        lines.append("- none")
    lines.extend(["", "### quality flags", ""])
    for key, value in (summary.get("quality_flags") or {}).items():
        lines.append(f"- {key}: {value}")
    maintenance = summary.get("maintenance") or {}
    if maintenance:
        lines.extend([
            "",
            "### knowledge maintenance",
            "",
            f"- existing_notes: {maintenance.get('existing_notes', 0)}",
            f"- refreshable_notes: {maintenance.get('refreshable_notes', 0)}",
            f"- moved_or_reindexed_notes: {maintenance.get('moved_or_reindexed_notes', 0)}",
            f"- dangling_notes: {maintenance.get('dangling_notes', 0)}",
            f"- new_candidate_notes: {maintenance.get('new_candidate_notes', 0)}",
        ])
    lines.append("")
    return lines


def _parse_stock(value: str) -> Tuple[str, str]:
    if ":" in value:
        code, name = value.split(":", 1)
        return code.strip(), name.strip()
    return value.strip(), ""


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", action="append", default=[], help="Stock as CODE:NAME. Can be repeated.")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--knowledge-base-dir", default="")
    parser.add_argument("--report-type", default="annual")
    parser.add_argument("--report-year", type=int, default=2025)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parse_args(argv)
    stocks = [_parse_stock(value) for value in args.stock]
    if not stocks:
        print("At least one --stock CODE:NAME is required.", file=sys.stderr)
        return 2
    markdown = build_acceptance_markdown(
        stocks=stocks,
        cache_dir=args.cache_dir,
        report_type=args.report_type,
        report_year=args.report_year,
        knowledge_base_dir=args.knowledge_base_dir or None,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
