#!/usr/bin/env python3
"""Render local periodic-report narrative evidence cards from cached report text.

This is a standalone helper-only preview entrypoint. It reads local cache files,
does not call LLMs, does not access the network, and does not write to reports/
or knowledge/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
from periodic_report_narrative_card_note_writer import (  # noqa: E402
    write_periodic_report_narrative_card_notes,
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
    knowledge_base_dir: Optional[Union[str, Path]] = None,
    write_knowledge: bool = False,
    refresh_existing: bool = False,
    refresh_frontmatter_only: bool = False,
    existing_only: bool = False,
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
    write_plan = None
    maintenance_summary = None
    if knowledge_base_dir:
        maintenance_summary = _build_knowledge_maintenance_summary(
            cards_pack=cards_pack,
            knowledge_base_dir=knowledge_base_dir,
            stock_name=title_name,
        )
        write_cards_pack = cards_pack
        if existing_only:
            existing_cards = [
                card
                for card in (cards_pack.get("cards") or [])
                if _card_note_path(
                    knowledge_base_dir=knowledge_base_dir,
                    stock_name=title_name,
                    card=card,
                ).exists()
            ]
            write_cards_pack = {**cards_pack, "cards": existing_cards}
        write_plan = write_periodic_report_narrative_card_notes(
            title_name,
            stock_code,
            write_cards_pack,
            knowledge_base_dir,
            dry_run=not write_knowledge,
            refresh_existing=refresh_existing,
            refresh_frontmatter_only=refresh_frontmatter_only,
        )

    lines = header + [
        f"- 缓存文件：`{cache_path}`",
        f"- evidence blocks：{len(evidence_pack.get('blocks') or [])}",
        f"- cards：{len(cards_pack.get('cards') or [])}",
        "",
    ]
    if write_plan is not None:
        if maintenance_summary is not None:
            lines.extend(_render_maintenance_summary(maintenance_summary))
        lines.extend(_render_knowledge_plan(
            write_plan,
            knowledge_base_dir,
            write_knowledge,
            refresh_existing=refresh_existing,
            refresh_frontmatter_only=refresh_frontmatter_only,
            existing_only=existing_only,
        ))
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


def _build_knowledge_maintenance_summary(
    *,
    cards_pack: dict,
    knowledge_base_dir: Union[str, Path],
    stock_name: str,
) -> dict:
    cards = [card for card in (cards_pack.get("cards") or []) if isinstance(card, dict)]
    note_candidate_cards = [
        card
        for card in (cards_pack.get("candidate_cards") or cards)
        if isinstance(card, dict)
    ]
    generated_hashes = {
        str(card.get("source_excerpt_hash", "")).strip()
        for card in note_candidate_cards
        if str(card.get("source_excerpt_hash", "")).strip()
    }
    generated_paths = {
        _card_note_path(
            knowledge_base_dir=knowledge_base_dir,
            stock_name=stock_name,
            card=card,
        )
        for card in note_candidate_cards
    }
    notes_dir = Path(knowledge_base_dir) / "10-Stocks" / _safe_dir_segment(stock_name) / "periodic_narrative_cards"
    existing_paths = set(notes_dir.glob("*.md")) if notes_dir.exists() else set()

    refreshable_paths = sorted(existing_paths & generated_paths)
    moved_or_reindexed_paths = []
    dangling_paths = []
    for path in sorted(existing_paths - generated_paths):
        note_hash = _read_note_source_excerpt_hash(path)
        if note_hash and note_hash in generated_hashes:
            moved_or_reindexed_paths.append(path)
        else:
            dangling_paths.append(path)
    new_candidate_paths = sorted(generated_paths - existing_paths)
    return {
        "generated_cards": len(cards),
        "generated_note_candidates": len(generated_paths),
        "existing_notes": len(existing_paths),
        "refreshable_notes": len(refreshable_paths),
        "moved_or_reindexed_notes": len(moved_or_reindexed_paths),
        "dangling_notes": len(dangling_paths),
        "new_candidate_notes": len(new_candidate_paths),
        "moved_or_reindexed_paths": moved_or_reindexed_paths,
        "dangling_paths": dangling_paths,
    }


def _render_maintenance_summary(summary: dict) -> list[str]:
    lines = [
        "## Knowledge maintenance summary",
        "",
        f"- generated_cards：{summary.get('generated_cards', 0)}",
        f"- generated_note_candidates：{summary.get('generated_note_candidates', 0)}",
        f"- existing_notes：{summary.get('existing_notes', 0)}",
        f"- refreshable_notes：{summary.get('refreshable_notes', 0)}",
        f"- moved_or_reindexed_notes：{summary.get('moved_or_reindexed_notes', 0)}",
        f"- dangling_notes：{summary.get('dangling_notes', 0)}",
        f"- new_candidate_notes：{summary.get('new_candidate_notes', 0)}",
    ]
    moved_or_reindexed_paths = summary.get("moved_or_reindexed_paths") or []
    if moved_or_reindexed_paths:
        lines.extend(["", "### Moved or reindexed existing notes", ""])
        lines.extend(f"- `{path.name}`" for path in moved_or_reindexed_paths[:20])
        if len(moved_or_reindexed_paths) > 20:
            lines.append(f"- ... and {len(moved_or_reindexed_paths) - 20} more")
    dangling_paths = summary.get("dangling_paths") or []
    if dangling_paths:
        lines.extend(["", "### Dangling existing notes", ""])
        lines.extend(f"- `{path.name}`" for path in dangling_paths[:20])
        if len(dangling_paths) > 20:
            lines.append(f"- ... and {len(dangling_paths) - 20} more")
    lines.append("")
    return lines


def _read_note_source_excerpt_hash(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    match = re.search(r"(?m)^source_excerpt_hash:\s*['\"]?([0-9a-f]{64})['\"]?\s*$", text)
    if match:
        return match.group(1)
    legacy_excerpt = _extract_legacy_note_excerpt(text)
    if legacy_excerpt:
        return _source_text_hash(legacy_excerpt)
    return ""


def _extract_legacy_note_excerpt(text: str) -> str:
    match = re.search(
        r"(?ms)^## Narrative Evidence\s*\n+(?P<body>.*?)(?:\n## |\Z)",
        text,
    )
    if not match:
        return ""
    lines = []
    for line in match.group("body").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            lines.append(stripped.lstrip("> ").strip())
    return " ".join(lines).strip()


def _source_text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _render_knowledge_plan(
    write_plan: object,
    base_dir: Union[str, Path],
    write_knowledge: bool,
    *,
    refresh_existing: bool = False,
    refresh_frontmatter_only: bool = False,
    existing_only: bool = False,
) -> list[str]:
    written = getattr(write_plan, "written", [])
    skipped = getattr(write_plan, "skipped_existing", [])
    refreshed = getattr(write_plan, "refreshed", [])
    filtered = getattr(write_plan, "filtered", [])
    return [
        "## Knowledge note plan",
        "",
        f"- base_dir：`{Path(base_dir)}`",
        f"- dry_run：`{str(not write_knowledge).lower()}`",
        f"- refresh_existing：`{str(refresh_existing).lower()}`",
        f"- refresh_frontmatter_only：`{str(refresh_frontmatter_only).lower()}`",
        f"- existing_only：`{str(existing_only).lower()}`",
        f"- written：{len(written)}",
        f"- skipped_existing：{len(skipped)}",
        f"- refreshed：{len(refreshed)}",
        f"- filtered：{len(filtered)}",
        "",
    ]


def _card_note_path(
    *,
    knowledge_base_dir: Union[str, Path],
    stock_name: str,
    card: dict,
) -> Path:
    card_id = str(card.get("card_id", ""))
    tail = card_id.rsplit(":", 1)[-1]
    index = tail if tail.isdigit() else "0"
    filename = "{year}-{rtype}-{ctype}-{idx}.md".format(
        year=card.get("report_year", ""),
        rtype=_safe_filename_segment(str(card.get("report_type", ""))) or "unknown",
        ctype=_safe_filename_segment(str(card.get("card_type", ""))) or "unknown",
        idx=index,
    )
    return (
        Path(knowledge_base_dir)
        / "10-Stocks"
        / _safe_dir_segment(stock_name)
        / "periodic_narrative_cards"
        / filename
    )


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


def _safe_filename_segment(segment: str) -> str:
    if not segment:
        return ""
    segment = str(segment).lower()
    segment = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in segment)
    while "--" in segment:
        segment = segment.replace("--", "-")
    return segment.strip("-")


def _safe_dir_segment(segment: str, *, fallback: str = "unknown") -> str:
    seg = str(segment or "").replace("\x00", "")
    for char in ("\\", "/"):
        seg = seg.replace(char, "-")
    while ".." in seg:
        seg = seg.replace("..", "-")
    seg = "-".join(seg.split())
    while "--" in seg:
        seg = seg.replace("--", "-")
    seg = seg.strip("-. ")
    return seg or fallback


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
    parser.add_argument("--knowledge-base-dir", help="Optional Knowledge base dir for note plan/write")
    parser.add_argument("--write-knowledge", action="store_true", help="Write Knowledge notes; default is dry-run")
    parser.add_argument("--refresh-existing", action="store_true", help="Refresh existing notes instead of skipping them")
    parser.add_argument("--refresh-frontmatter-only", action="store_true", help="Only update hash frontmatter when refreshing existing notes")
    parser.add_argument("--existing-only", action="store_true", help="Only plan/write cards whose note file already exists")
    args = parser.parse_args(argv)

    markdown = build_preview_markdown(
        stock_code=args.stock_code,
        stock_name=args.stock_name,
        cache_dir=args.cache_dir,
        report_type=args.report_type,
        report_year=args.report_year,
        include_json=args.include_json,
        knowledge_base_dir=args.knowledge_base_dir,
        write_knowledge=args.write_knowledge,
        refresh_existing=args.refresh_existing,
        refresh_frontmatter_only=args.refresh_frontmatter_only,
        existing_only=args.existing_only,
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
