"""Knowledge note writer for periodic-report narrative evidence cards.

This writer persists validated ``periodic_report_narrative_evidence`` cards
into standalone Knowledge Markdown notes. It is intentionally writer-only:
callers pass an already-built card pack and a base directory, and this module
only filters, sanitizes paths, and renders Markdown.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


NARRATIVE_CARD_SOURCE_TYPE = "periodic_report_narrative_evidence"
KNOWLEDGE_FACT_STATUS = "narrative_evidence"

_REQUIRED_FIELDS: Tuple[str, ...] = (
    "card_id",
    "schema_version",
    "card_type",
    "report_year",
    "report_type",
    "source_block_id",
    "evidence_refs",
    "source_excerpt",
)

_PLAIN_SCALAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]*$")


@dataclass
class NarrativeCardWritePlan:
    """Result of :func:`write_periodic_report_narrative_card_notes`."""

    written: List[Dict[str, Any]] = field(default_factory=list)
    skipped_existing: List[Dict[str, Any]] = field(default_factory=list)
    refreshed: List[Dict[str, Any]] = field(default_factory=list)
    filtered: List[Dict[str, Any]] = field(default_factory=list)


def _safe_filename_segment(segment: str) -> str:
    if not segment:
        return ""
    segment = str(segment).lower()
    segment = re.sub(r"[^a-z0-9\-]", "-", segment)
    segment = re.sub(r"-+", "-", segment)
    return segment.strip("-")


def _safe_dir_segment(segment: str, *, fallback: str = "unknown") -> str:
    seg = str(segment or "").replace("\x00", "")
    seg = re.sub(r"[\\/]+", "-", seg)
    seg = re.sub(r"\.{2,}", "-", seg)
    seg = re.sub(r"\s+", "-", seg)
    seg = re.sub(r"-+", "-", seg)
    seg = seg.strip("-. ")
    return seg or fallback


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    if _PLAIN_SCALAR_RE.match(text):
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _render_frontmatter(entries: List[Tuple[str, Any]]) -> str:
    lines = ["---"]
    for key, value in entries:
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {_yaml_scalar(item)}")
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _coerce_int(value: Any) -> Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _card_index(card: Dict[str, Any], fallback: int) -> str:
    card_id = str(card.get("card_id", ""))
    tail = card_id.rsplit(":", 1)[-1]
    if re.fullmatch(r"\d+", tail):
        return tail
    return str(fallback)


def _missing_required_field(card: Dict[str, Any]) -> Optional[str]:
    for required in _REQUIRED_FIELDS:
        value = card.get(required)
        if required == "evidence_refs":
            if not value or not isinstance(value, list):
                return required
            continue
        if value is None or value == "":
            return required
    return None


def _render_note(
    card: Dict[str, Any],
    collected_at: str,
    *,
    stock_name: str,
    stock_code: str,
) -> str:
    report_year = card.get("report_year", "")
    report_type = str(card.get("report_type", ""))
    card_type = str(card.get("card_type", ""))
    evidence_refs = [str(ref) for ref in (card.get("evidence_refs") or [])]

    frontmatter = _render_frontmatter([
        ("stock", stock_name),
        ("code", stock_code),
        ("source_type", NARRATIVE_CARD_SOURCE_TYPE),
        ("card_id", str(card.get("card_id", ""))),
        ("schema_version", str(card.get("schema_version", ""))),
        ("card_type", card_type),
        ("title", str(card.get("title", ""))),
        ("report_year", _coerce_int(report_year)),
        ("report_type", report_type),
        ("source_credit", 75),
        ("source_block_id", str(card.get("source_block_id", ""))),
        ("evidence_refs", evidence_refs),
        ("knowledge_fact_status", KNOWLEDGE_FACT_STATUS),
        ("knowledge_eligible", False),
        ("knowledge_persisted", True),
        ("synthesis_eligible", False),
        ("experimental", True),
        ("collected_at", collected_at),
    ])

    excerpt = str(card.get("source_excerpt", "")).strip() or "（无摘录）"
    body = [
        frontmatter,
        f"# {stock_name} {report_year} {report_type} {card_type}",
        "",
        "## Narrative Evidence",
        "",
        f"> {excerpt}",
        "",
        "## Source",
        "",
        f"- card_id: {card.get('card_id', '')}",
        f"- source_block_id: {card.get('source_block_id', '')}",
        f"- evidence_refs: {', '.join(evidence_refs)}",
        "- source_credit: 75",
        "",
        "## Guardrails",
        "",
        "- This note is original periodic-report narrative evidence, not a generated summary.",
        "- It stays outside automated claim promotion and scoring paths.",
        "",
    ]
    return "\n".join(body)


def write_periodic_report_narrative_card_notes(
    stock_name: str,
    stock_code: str,
    card_pack: Dict[str, Any],
    base_dir: Union[str, Path],
    collected_at: Optional[str] = None,
    dry_run: bool = False,
    refresh_existing: bool = False,
) -> NarrativeCardWritePlan:
    """Write narrative evidence cards to Knowledge notes.

    Only ``card_pack["cards"]`` is read, and every item is re-asserted to have
    ``source_type == "periodic_report_narrative_evidence"``.
    """
    plan = NarrativeCardWritePlan()
    collected = collected_at or ""

    cards_dir = (
        Path(base_dir)
        / "10-Stocks"
        / _safe_dir_segment(stock_name)
        / "periodic_narrative_cards"
    )
    cards_dir_resolved = cards_dir.resolve()

    cards = card_pack.get("cards") or []
    for index, card in enumerate(cards):
        if not isinstance(card, dict):
            plan.filtered.append({
                "card_id": "",
                "reason": "malformed entry is not a periodic_report_narrative_evidence dict",
            })
            continue

        card_id = str(card.get("card_id", ""))
        source_type = str(card.get("source_type", ""))
        if source_type != NARRATIVE_CARD_SOURCE_TYPE:
            plan.filtered.append({
                "card_id": card_id,
                "reason": f"source_type not periodic_report_narrative_evidence: {source_type or '<empty>'}",
            })
            continue

        missing = _missing_required_field(card)
        if missing:
            plan.filtered.append({
                "card_id": card_id,
                "reason": f"missing required field: {missing}",
            })
            continue

        card_stock_code = str(card.get("stock_code", ""))
        if card_stock_code and card_stock_code != str(stock_code):
            plan.filtered.append({
                "card_id": card_id,
                "reason": f"stock_code mismatch: {card_stock_code} != {stock_code}",
            })
            continue

        filename = "{year}-{rtype}-{ctype}-{idx}.md".format(
            year=_coerce_int(card.get("report_year")),
            rtype=_safe_filename_segment(str(card.get("report_type", ""))) or "unknown",
            ctype=_safe_filename_segment(str(card.get("card_type", ""))) or "unknown",
            idx=_card_index(card, index),
        )
        target = cards_dir / filename

        if target.resolve().parent != cards_dir_resolved:
            plan.filtered.append({
                "card_id": card_id,
                "reason": "path escape blocked",
            })
            continue

        meta = {"card_id": card_id, "planned_path": str(target)}

        if target.exists():
            if not refresh_existing:
                meta["reason"] = "note already exists"
                plan.skipped_existing.append(meta)
                continue
            if not dry_run:
                target.write_text(
                    _render_note(
                        card,
                        collected,
                        stock_name=stock_name,
                        stock_code=stock_code,
                    ),
                    encoding="utf-8",
                )
            meta["reason"] = "refreshed_existing"
            plan.refreshed.append(meta)
            continue

        if not dry_run:
            cards_dir.mkdir(parents=True, exist_ok=True)
            target.write_text(
                _render_note(
                    card,
                    collected,
                    stock_name=stock_name,
                    stock_code=stock_code,
                ),
                encoding="utf-8",
            )

        meta["reason"] = "written"
        plan.written.append(meta)

    return plan
