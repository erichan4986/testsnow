"""Load persisted periodic-report narrative cards as display-only synthesis items."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

if __name__.startswith("utils."):
    from .source_adapter import SynthesisItem
    from .annual_report_material_pack import (
        build_annual_report_material_pack,
        read_periodic_narrative_card_note,
        selected_cards_to_synthesis_items,
    )
    from .periodic_report_narrative_pack_store import PeriodicNarrativePackStorageError
    from .periodic_report_narrative_card_note_writer import narrative_cards_dir
else:
    from source_adapter import SynthesisItem
    from annual_report_material_pack import (
        build_annual_report_material_pack,
        read_periodic_narrative_card_note,
        selected_cards_to_synthesis_items,
    )
    from periodic_report_narrative_pack_store import PeriodicNarrativePackStorageError
    from periodic_report_narrative_card_note_writer import narrative_cards_dir


NARRATIVE_CARD_SOURCE_TYPE = "periodic_report_narrative_evidence"


def load_periodic_narrative_card_synthesis_items(
    *,
    stock_name: str,
    base_dir: str | Path,
    stock_code: str = "",
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
                stock_code=stock_code,
                base_dir=base_dir,
            )
            items = selected_cards_to_synthesis_items(pack["selected_narrative_cards"])
            return items[: max(0, int(max_cards))]
        except PeriodicNarrativePackStorageError:
            raise
        except Exception:
            return []

    notes_dir = narrative_cards_dir(stock_name=stock_name, base_dir=base_dir)
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
    card = read_periodic_narrative_card_note(path)
    if card is None:
        return None

    is_v2 = str(card.get("schema_version") or "") == (
        "periodic_report_narrative_evidence_card.v2"
    )
    card_type = str(card.get("card_type") or "").strip()
    title = str(card.get("title") or "年报叙事卡片")
    report_year = str(card.get("report_year") or "").strip()
    report_type = str(card.get("report_type") or "").strip()
    source_credit = _as_int(card.get("source_credit"), 75)

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
        "card_id": str(card.get("card_id") or ""),
        "source_block_id": str(card.get("source_block_id") or ""),
        "report_year": _as_int(report_year, report_year),
        "report_type": report_type,
    }
    if is_v2:
        extra.update({
            "argument_family": str(card.get("argument_family") or ""),
            "argument_complete": card.get("argument_complete"),
            "schema_version": card.get("schema_version"),
            "selection_version": card.get("selection_version"),
            "source_unit_ids": list(card.get("source_unit_ids") or []),
            "source_units": list(card.get("source_units") or []),
            "fact_anchors": list(card.get("fact_anchors") or []),
            "secondary_signals": list(card.get("secondary_signals") or []),
            "score_parts": card.get("score_parts") or {},
            "quality_score": card.get("quality_score"),
            "selection_reason": card.get("selection_reason") or "",
            "selection_diagnostics": card.get("selection_diagnostics") or {
                "score_parts": card.get("score_parts") or {},
                "selection_reason": card.get("selection_reason") or "",
            },
        })
    else:
        extra["card_type"] = card_type

    return SynthesisItem(
        title=f"{report_year} {report_type} | {title}".strip(),
        content=str(card.get("source_excerpt") or ""),
        author="公司年报",
        source_platform="定期报告叙事卡片",
        url="",
        publish_time=report_year,
        interaction_score=0,
        extra=extra,
    )


def _as_int(value: Any, default: Any) -> Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
