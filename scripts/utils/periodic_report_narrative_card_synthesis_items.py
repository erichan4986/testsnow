"""Load persisted periodic-report narrative cards as display-only synthesis items."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

if __name__.startswith("utils."):
    from .source_adapter import SynthesisItem
    from .annual_report_material_pack import (
        build_annual_report_material_pack,
        selected_cards_to_synthesis_items,
    )
else:
    from source_adapter import SynthesisItem
    from annual_report_material_pack import (
        build_annual_report_material_pack,
        selected_cards_to_synthesis_items,
    )


NARRATIVE_CARD_SOURCE_TYPE = "periodic_report_narrative_evidence"

def load_periodic_narrative_card_synthesis_items(
    *,
    stock_name: str,
    base_dir: str | Path,
    max_cards: int = 12,
    use_pack: bool = False,
    **_legacy_options: Any,
) -> List[SynthesisItem]:
    """Read narrative-card Knowledge notes and convert them to display items.

    The reader is intentionally read-only. It parses current note-writer output:
    metadata comes from frontmatter, while source excerpts come from the
    ``## Narrative Evidence`` blockquote in the note body.

    When ``use_pack`` is True, selection is delegated to
    ``annual_report_material_pack`` for deterministic quality ranking,
    deduplication, and card-type balancing. The legacy path (False) preserves
    filename ordering for compatibility.
    """
    del _legacy_options
    if use_pack:
        try:
            pack = build_annual_report_material_pack(
                stock_name=stock_name,
                base_dir=base_dir,
            )
            items = selected_cards_to_synthesis_items(pack["selected_narrative_cards"])
            return items[: max(0, int(max_cards))]
        except Exception:
            return []

    notes_dir = (
        Path(base_dir)
        / "10-Stocks"
        / _safe_dir_segment(stock_name)
        / "periodic_narrative_cards"
    )
    if not notes_dir.exists():
        return []

    items: List[SynthesisItem] = []
    for path in sorted(notes_dir.glob("*.md")):
        item = _read_note_as_item(path)
        if item is None:
            continue
        items.append(item)
        if len(items) >= max_cards:
            break
    return items


def _read_note_as_item(path: Path) -> Optional[SynthesisItem]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    frontmatter = _parse_frontmatter(text)
    if frontmatter.get("source_type") != NARRATIVE_CARD_SOURCE_TYPE:
        return None

    excerpt = _extract_narrative_evidence_excerpt(text)
    if not excerpt:
        return None

    is_v2 = str(frontmatter.get("schema_version") or "") == (
        "periodic_report_narrative_evidence_card.v2"
    )
    card_type = str(frontmatter.get("card_type") or "").strip()
    title = str(frontmatter.get("title") or "年报叙事卡片")
    report_year = str(frontmatter.get("report_year") or "").strip()
    report_type = str(frontmatter.get("report_type") or "").strip()
    source_credit = _as_int(frontmatter.get("source_credit"), 75)

    extra = {
        "source_type": NARRATIVE_CARD_SOURCE_TYPE,
        "source_credit": source_credit,
        "verification_status": "professional_analysis",
        "claim_status": "professional_analysis",
        "knowledge_eligible": False,
        "report_eligible": False,
        "synthesis_eligible": False,
        "synthesis_display_only": True,
        "experimental": True,
        "card_id": str(frontmatter.get("card_id") or ""),
        "source_block_id": str(frontmatter.get("source_block_id") or ""),
        "report_year": _as_int(report_year, report_year),
        "report_type": report_type,
    }
    if is_v2:
        source_units = _extract_json_section(text, "Source Units")
        diagnostics = _extract_json_section(text, "Selection Diagnostics")
        if not isinstance(source_units, list) or not isinstance(diagnostics, dict):
            return None
        extra.update({
            "argument_family": str(frontmatter.get("argument_family") or ""),
            "argument_complete": frontmatter.get("argument_complete"),
            "schema_version": frontmatter.get("schema_version"),
            "selection_version": frontmatter.get("selection_version"),
            "source_unit_ids": list(frontmatter.get("source_unit_ids") or []),
            "source_units": source_units,
            "fact_anchors": list(frontmatter.get("fact_anchors") or []),
            "secondary_signals": list(frontmatter.get("secondary_signals") or []),
            "score_parts": diagnostics.get("score_parts") or {},
            "quality_score": frontmatter.get("quality_score"),
            "selection_reason": diagnostics.get("selection_reason") or "",
            "selection_diagnostics": diagnostics,
        })
    else:
        extra["card_type"] = card_type

    return SynthesisItem(
        title=f"{report_year} {report_type} | {title}".strip(),
        content=excerpt,
        author="公司年报",
        source_platform="定期报告叙事卡片",
        url="",
        publish_time=report_year,
        interaction_score=0,
        extra=extra,
    )


def _parse_frontmatter(text: str) -> Dict[str, Any]:
    match = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        return {}

    data: Dict[str, Any] = {}
    lines = match.group(1).splitlines()
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        if not raw_line or raw_line.startswith(" ") or ":" not in raw_line:
            index += 1
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            index += 1
            continue
        if value == "":
            items: List[Any] = []
            cursor = index + 1
            while cursor < len(lines) and lines[cursor].startswith("  - "):
                items.append(_clean_scalar(lines[cursor][4:].strip()))
                cursor += 1
            data[key] = items
            index = cursor
            continue
        data[key] = _clean_scalar(value)
        index += 1
    return data


def _extract_json_section(text: str, heading: str) -> Any:
    match = re.search(
        rf"(?ms)^## {re.escape(heading)}\s*\n+```(?:json)?\s*\n?(?P<body>.*?)\n```",
        text,
    )
    if not match:
        return None
    try:
        return json.loads(match.group("body"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _extract_narrative_evidence_excerpt(text: str) -> str:
    match = re.search(
        r"(?ms)^## Narrative Evidence\s*\n+(?P<body>.*?)(?:\n## |\Z)",
        text,
    )
    if not match:
        return ""

    lines = []
    for line in match.group("body").splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            lines.append(stripped.lstrip(">").strip())
        elif lines and stripped:
            break
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def _clean_scalar(value: str) -> Any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    ):
        value = value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    return value


def _as_int(value: Any, default: Any) -> Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_dir_segment(value: str) -> str:
    cleaned = re.sub(r"[\\/:\*\?\"<>\|\r\n\t]+", "_", str(value or "")).strip(" ._")
    return cleaned or "unknown"
