#!/usr/bin/env python3
"""Read-only acceptance diagnostics for periodic narrative material packs."""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple, Union

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UTILS_DIR = PROJECT_ROOT / "scripts" / "utils"
for path in (PROJECT_ROOT, UTILS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from annual_report_material_pack import build_annual_report_material_pack  # noqa: E402
from periodic_report_evidence_pack import build_periodic_report_evidence_pack  # noqa: E402
from periodic_report_narrative_cards_preview import DEFAULT_CACHE_DIR, _find_cache_file  # noqa: E402
from periodic_report_narrative_evidence_cards import (  # noqa: E402
    build_periodic_report_narrative_evidence_cards,
)
from periodic_report_narrative_pack_store import (  # noqa: E402
    MANIFEST_FILENAME,
    PeriodicNarrativePackStorageError,
    load_validated_periodic_narrative_pack_set,
    periodic_narrative_stock_root,
)
from periodic_report_narrative_view_writer import (  # noqa: E402
    PeriodicNarrativeViewError,
    build_periodic_report_narrative_view,
)

DEFAULT_OUTPUT = Path("/tmp/periodic_narrative_cards_acceptance.md")
_SHORT_EXCERPT_CHARS = 32
_DANGLING_START_RE = re.compile(r"^[，,；;。)、）]")
_DANGLING_START_PREFIXES = ("优化等举措", "续研发", "力、众多", "安全规范、")
_TABLE_FRAGMENT_TOKENS = ("□适用", "适用", "□不适用", "不适用", "产品名称", "适用 不适用")
_PROJECTION_FIELDS = (
    "producer_pack_parity", "projection_deterministic", "pack_bytes_unchanged",
    "manifest_bytes_unchanged", "projection_cards_sha256_matches",
    "projection_total_cards", "projection_displayed_cards",
    "v1_actionable_needs_recovery_count", "v1_adapter_use_count",
)
_ARCHIVE_GATE_FIELDS = _PROJECTION_FIELDS[:5]


def analyze_cards_pack(*, stock_code: str, stock_name: str, cards_pack: dict) -> dict:
    """Return compact producer diagnostics without reading Knowledge."""
    cards = [card for card in cards_pack.get("cards") or [] if isinstance(card, dict)]
    candidates = [
        card for card in cards_pack.get("candidate_cards") or cards if isinstance(card, dict)
    ]
    families = Counter(
        str(card.get("argument_family") or card.get("card_type") or "unknown")
        for card in cards
    )
    hashes = Counter(
        str(card.get("source_excerpt_hash") or "")
        for card in cards if str(card.get("source_excerpt_hash") or "")
    )
    flags = {
        "duplicate_excerpt_hashes": sum(count - 1 for count in hashes.values() if count > 1),
        "short_excerpts": sum(
            len(str(card.get("source_excerpt") or "").strip()) < _SHORT_EXCERPT_CHARS
            for card in cards
        ),
        "dangling_start_excerpts": sum(
            _looks_like_dangling_start(str(card.get("source_excerpt") or ""))
            for card in cards
        ),
        "table_fragment_excerpts": sum(
            _looks_like_table_fragment(str(card.get("source_excerpt") or ""))
            for card in cards
        ),
    }
    return {
        "stock_code": stock_code, "stock_name": stock_name,
        "selected_cards": len(cards), "candidate_cards": len(candidates),
        "card_type_counts": dict(sorted(families.items())), "quality_flags": flags,
        "quality_flag_total": sum(flags.values()),
    }


def analyze_pack_projection(
    *, stock_code: str, stock_name: str, cards_pack: dict,
    knowledge_base_dir: Union[str, Path],
) -> dict:
    """Verify producer/pack parity and deterministic, read-only human projection."""
    loaded = load_validated_periodic_narrative_pack_set(
        stock_name=stock_name, stock_code=stock_code, base_dir=knowledge_base_dir,
    )
    year, report_type = cards_pack.get("report_year"), cards_pack.get("report_type")
    matches = [
        pack for pack in loaded["packs"]
        if pack["report_year"] == year and pack["report_type"] == report_type
    ]
    root = periodic_narrative_stock_root(knowledge_base_dir, stock_name)
    manifest_path = root / MANIFEST_FILENAME
    manifest_before = manifest_path.read_bytes()
    pack_paths = [root / entry["pack_path"] for entry in loaded["entries"]]
    packs_before = {path: path.read_bytes() for path in pack_paths}

    first = build_periodic_report_narrative_view(
        stock_name=stock_name, stock_code=stock_code, report_year=year,
        report_type=report_type, base_dir=knowledge_base_dir,
    )
    second = build_periodic_report_narrative_view(
        stock_name=stock_name, stock_code=stock_code, report_year=year,
        report_type=report_type, base_dir=knowledge_base_dir,
    )
    material = build_annual_report_material_pack(
        stock_name=stock_name, stock_code=stock_code, base_dir=knowledge_base_dir,
    )
    persisted = matches[0] if len(matches) == 1 else None
    diagnostics = material.get("diagnostics") or {}
    return {
        "producer_pack_parity": bool(
            persisted
            and persisted["producer_schema_version"] == cards_pack.get("schema_version")
            and persisted["selection_version"] == cards_pack.get("selection_version")
            and persisted["stock_code"] == str(cards_pack.get("stock_code") or "")
            and persisted["stock_name"] == cards_pack.get("stock_name")
            and persisted["report_year"] == cards_pack.get("report_year")
            and persisted["report_type"] == cards_pack.get("report_type")
            and persisted["cards"] == (cards_pack.get("cards") or [])
            and persisted["producer_diagnostics"] == (cards_pack.get("diagnostics") or {})
        ),
        "projection_deterministic": first.markdown == second.markdown,
        "pack_bytes_unchanged": all(path.read_bytes() == data for path, data in packs_before.items()),
        "manifest_bytes_unchanged": manifest_path.read_bytes() == manifest_before,
        "projection_cards_sha256_matches": bool(
            persisted and first.cards_sha256 == persisted["integrity"]["cards_sha256"]
        ),
        "projection_total_cards": first.total_cards,
        "projection_displayed_cards": first.displayed_cards,
        "v1_actionable_needs_recovery_count": diagnostics.get(
            "v1_actionable_needs_recovery_count", 0
        ),
        "v1_adapter_use_count": diagnostics.get("v1_adapter_use_count", 0),
    }


def build_archive_manifest(
    *, stocks: Sequence[Tuple[str, str]], knowledge_base_dir: Union[str, Path],
    projections: dict[str, dict],
) -> dict:
    """Build a deterministic dry-run inventory; never move or delete notes."""
    base = Path(knowledge_base_dir)
    stock_rows, all_notes = [], []
    for stock_code, stock_name in stocks:
        notes_dir = periodic_narrative_stock_root(
            base, stock_name
        ) / "periodic_narrative_cards"
        notes, invalid = [], 0
        for path in sorted(notes_dir.glob("*.md")) if notes_dir.exists() else []:
            text = path.read_text(encoding="utf-8", errors="replace")
            if "source_type: periodic_report_narrative_evidence" not in text:
                invalid += 1
                continue
            version = "v2" if re.search(
                r"(?m)^schema_version:\s*periodic_report_narrative_evidence_card\.v2\s*$",
                text,
            ) else "v1"
            notes.append({
                "path": str(path.relative_to(base)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "version": version,
            })
        projection = projections.get(stock_name) or {}
        gate_passed = (
            all(projection.get(field) is True for field in _ARCHIVE_GATE_FIELDS)
            and projection.get("v1_actionable_needs_recovery_count") == 0
            and projection.get("v1_adapter_use_count") == 0
            and invalid == 0
        )
        stock_rows.append({
            "stock_code": stock_code,
            "stock_name": stock_name,
            "gate_passed": gate_passed,
            "v1_note_count": sum(note["version"] == "v1" for note in notes),
            "v2_note_count": sum(note["version"] == "v2" for note in notes),
            "invalid_note_count": invalid,
            "notes": notes,
        })
        all_notes.extend(notes)
    all_passed = bool(stock_rows) and all(row["gate_passed"] for row in stock_rows)
    return {
        "schema_version": "periodic_narrative_archive_manifest.v1",
        "dry_run_only": True,
        "requires_explicit_confirmation": True,
        "all_stock_gates_passed": all_passed,
        "stocks": stock_rows,
        "archive_eligible": sorted(all_notes, key=lambda item: item["path"])
        if all_passed else [],
    }


def build_acceptance_markdown(
    *, stocks: Sequence[Tuple[str, str]], cache_dir: Union[str, Path] = DEFAULT_CACHE_DIR,
    report_type: str = "annual", report_year: int = 2025,
    knowledge_base_dir: Optional[Union[str, Path]] = None,
    pack_shadow: bool = False, pack_projection: bool = False,
) -> str:
    """Build acceptance Markdown from local caches without writing Knowledge."""
    summaries = []
    for stock_code, stock_name in stocks:
        cache_path = _find_cache_file(
            cache_dir=cache_dir, stock_code=stock_code, stock_name=stock_name,
            report_type=report_type,
        )
        if not cache_path:
            summaries.append({
                "stock_code": stock_code, "stock_name": stock_name,
                "selected_cards": 0, "candidate_cards": 0, "card_type_counts": {},
                "quality_flags": {"missing_cache": 1}, "quality_flag_total": 1,
                "cache_path": "", "evidence_blocks": 0,
            })
            continue
        raw_text = cache_path.read_text(encoding="utf-8", errors="ignore")
        evidence = build_periodic_report_evidence_pack(raw_text, report_type=report_type)
        cards_pack = build_periodic_report_narrative_evidence_cards(
            stock_code=stock_code, stock_name=stock_name or stock_code,
            report_year=report_year, report_type=report_type,
            evidence_pack=evidence, raw_text=raw_text,
        )
        summary = analyze_cards_pack(
            stock_code=stock_code, stock_name=stock_name, cards_pack=cards_pack,
        )
        summary.update(cache_path=str(cache_path), evidence_blocks=len(evidence.get("blocks") or []))
        if (pack_shadow or pack_projection) and knowledge_base_dir:
            try:
                summary["pack_projection"] = analyze_pack_projection(
                    stock_code=stock_code, stock_name=stock_name or stock_code,
                    cards_pack=cards_pack, knowledge_base_dir=knowledge_base_dir,
                )
            except (PeriodicNarrativePackStorageError, PeriodicNarrativeViewError) as exc:
                summary["pack_projection"] = {"projection_error": exc.code}
        summaries.append(summary)

    lines = [
        "# 定期报告 Narrative Cards Acceptance", "", "- dry_run_only：true",
        f"- cache_dir：`{Path(cache_dir)}`", f"- report_type：{report_type}",
        f"- report_year：{report_year}", "",
    ]
    lines.extend(_render_overview_table(summaries))
    for summary in summaries:
        lines.extend(_render_stock_summary(summary))
    return "\n".join(lines)


def _looks_like_table_fragment(excerpt: str) -> bool:
    compact = re.sub(r"\s+", " ", excerpt)
    return (
        sum(token in compact for token in _TABLE_FRAGMENT_TOKENS) >= 2
        or compact.count("□") + compact.count("") >= 2
    )


def _looks_like_dangling_start(excerpt: str) -> bool:
    text = str(excerpt or "").strip()
    return bool(_DANGLING_START_RE.search(text)) or any(
        text.startswith(prefix) for prefix in _DANGLING_START_PREFIXES
    )


def _render_overview_table(summaries: Sequence[dict]) -> list[str]:
    lines = [
        "## Overview", "", "| 股票 | selected | candidates | quality_flags |",
        "| --- | ---: | ---: | ---: |",
    ]
    for summary in summaries:
        label = f"{summary.get('stock_name') or summary.get('stock_code')} `{summary.get('stock_code')}`"
        lines.append(
            f"| {label} | {summary.get('selected_cards', 0)} | "
            f"{summary.get('candidate_cards', 0)} | {summary.get('quality_flag_total', 0)} |"
        )
    return lines + [""]


def _render_stock_summary(summary: dict) -> list[str]:
    title = summary.get("stock_name") or summary.get("stock_code") or "unknown"
    lines = [
        f"## {title} `{summary.get('stock_code', '')}`", "",
        f"- cache：`{summary.get('cache_path') or 'missing'}`",
        f"- evidence_blocks：{summary.get('evidence_blocks', 0)}",
        f"- selected_cards：{summary.get('selected_cards', 0)}",
        f"- candidate_cards：{summary.get('candidate_cards', 0)}", "",
        "### card_type distribution", "",
    ]
    counts = summary.get("card_type_counts") or {}
    lines.extend(f"- {key}: {value}" for key, value in counts.items())
    if not counts:
        lines.append("- none")
    lines.extend(("", "### quality flags", ""))
    lines.extend(f"- {key}: {value}" for key, value in (summary.get("quality_flags") or {}).items())
    projection = summary.get("pack_projection") or {}
    if projection:
        lines.extend(("", "### pack projection", ""))
        if projection.get("projection_error"):
            lines.append(f"- projection_error: {projection['projection_error']}")
        else:
            lines.extend(f"- {key}: {projection.get(key)}" for key in _PROJECTION_FIELDS)
    return lines + [""]


def _parse_stock(value: str) -> Tuple[str, str]:
    code, separator, name = value.partition(":")
    return code.strip(), name.strip() if separator else ""


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", action="append", default=[], help="Stock as CODE:NAME. Can be repeated.")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--knowledge-base-dir", default="")
    parser.add_argument("--report-type", default="annual")
    parser.add_argument("--report-year", type=int, default=2025)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--pack-projection", action="store_true", help="Run read-only pack projection audit")
    parser.add_argument("--pack-shadow", action="store_true", help="Deprecated alias for --pack-projection")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parse_args(argv)
    stocks = [_parse_stock(value) for value in args.stock]
    if not stocks:
        print("At least one --stock CODE:NAME is required.", file=sys.stderr)
        return 2
    markdown = build_acceptance_markdown(
        stocks=stocks, cache_dir=args.cache_dir, report_type=args.report_type,
        report_year=args.report_year, knowledge_base_dir=args.knowledge_base_dir or None,
        pack_shadow=args.pack_shadow, pack_projection=args.pack_projection,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
