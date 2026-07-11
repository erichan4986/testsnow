"""Knowledge note writer for periodic-report narrative evidence cards.

This writer persists validated ``periodic_report_narrative_evidence`` cards
into standalone Knowledge Markdown notes. It is intentionally writer-only:
callers pass an already-built card pack and a base directory, and this module
only filters, sanitizes paths, and renders Markdown.
"""

from __future__ import annotations

import hashlib
import json
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

_V2_REQUIRED_FIELDS: Tuple[str, ...] = (
    "card_id",
    "schema_version",
    "selection_version",
    "argument_family",
    "argument_complete",
    "report_year",
    "report_type",
    "source_block_id",
    "source_unit_ids",
    "source_units",
    "source_excerpt",
)
V2_CARD_SCHEMA_VERSION = "periodic_report_narrative_evidence_card.v2"

_PLAIN_SCALAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")


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


def _source_text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _refresh_frontmatter_hashes(
    note_text: str,
    *,
    source_excerpt_hash: str,
    source_block_hash: str = "",
) -> str:
    if not note_text.startswith("---\n"):
        return note_text
    parts = note_text.split("---", 2)
    if len(parts) != 3:
        return note_text

    frontmatter = parts[1].strip("\n")
    body = parts[2]
    lines = [
        line
        for line in frontmatter.splitlines()
        if not line.startswith("source_excerpt_hash:")
        and not (source_block_hash and line.startswith("source_block_hash:"))
    ]
    insert_at = next(
        (idx for idx, line in enumerate(lines) if line.startswith("knowledge_fact_status:")),
        len(lines),
    )
    hash_lines = [f"source_excerpt_hash: {_yaml_scalar(source_excerpt_hash)}"]
    if source_block_hash:
        hash_lines.append(f"source_block_hash: {_yaml_scalar(source_block_hash)}")
    lines[insert_at:insert_at] = hash_lines
    return "---\n" + "\n".join(lines) + "\n---" + body


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
    required_fields = (
        _V2_REQUIRED_FIELDS
        if _is_v2_card(card)
        else _REQUIRED_FIELDS
    )
    for required in required_fields:
        value = card.get(required)
        if required in ("evidence_refs", "source_unit_ids", "source_units"):
            if not value or not isinstance(value, list):
                return required
            continue
        if value is None or value == "":
            return required
    return None


def _is_v2_card(card: Dict[str, Any]) -> bool:
    return str(card.get("schema_version") or "") == V2_CARD_SCHEMA_VERSION


def _json_fence(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _render_note(
    card: Dict[str, Any],
    collected_at: str,
    *,
    stock_name: str,
    stock_code: str,
) -> str:
    if _is_v2_card(card):
        return _render_v2_note(
            card,
            collected_at,
            stock_name=stock_name,
            stock_code=stock_code,
        )

    report_year = card.get("report_year", "")
    report_type = str(card.get("report_type", ""))
    card_type = str(card.get("card_type", ""))
    evidence_refs = [str(ref) for ref in (card.get("evidence_refs") or [])]
    excerpt = str(card.get("source_excerpt", "")).strip() or "（无摘录）"
    source_excerpt_hash = str(card.get("source_excerpt_hash") or _source_text_hash(excerpt))
    source_block_hash = str(card.get("source_block_hash") or "")

    frontmatter_entries = [
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
        ("source_excerpt_hash", source_excerpt_hash),
        ("knowledge_fact_status", KNOWLEDGE_FACT_STATUS),
        ("knowledge_eligible", False),
        ("knowledge_persisted", True),
        ("synthesis_eligible", False),
        ("experimental", True),
        ("collected_at", collected_at),
    ]
    if source_block_hash:
        frontmatter_entries.insert(
            next(i for i, entry in enumerate(frontmatter_entries) if entry[0] == "knowledge_fact_status"),
            ("source_block_hash", source_block_hash),
        )
    frontmatter = _render_frontmatter(frontmatter_entries)

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


def _render_v2_note(
    card: Dict[str, Any],
    collected_at: str,
    *,
    stock_name: str,
    stock_code: str,
) -> str:
    report_year = card.get("report_year", "")
    report_type = str(card.get("report_type", ""))
    family = str(card.get("argument_family", ""))
    source_excerpt = str(card.get("source_excerpt", "")).strip() or "（无摘录）"
    source_excerpt_hash = str(
        card.get("source_excerpt_hash") or _source_text_hash(source_excerpt)
    )
    source_block_hash = str(card.get("source_block_hash") or "")
    source_unit_ids = [str(item) for item in (card.get("source_unit_ids") or [])]
    fact_anchors = [str(item) for item in (card.get("fact_anchors") or [])]
    secondary_signals = [str(item) for item in (card.get("secondary_signals") or [])]
    source_units = card.get("source_units") or []
    diagnostics = {
        "score_parts": card.get("score_parts") or {},
        "selection_reason": str(card.get("selection_reason") or ""),
    }

    frontmatter_entries = [
        ("stock", stock_name),
        ("code", stock_code),
        ("source_type", NARRATIVE_CARD_SOURCE_TYPE),
        ("card_id", str(card.get("card_id", ""))),
        ("schema_version", str(card.get("schema_version", ""))),
        ("selection_version", str(card.get("selection_version", ""))),
        ("argument_family", family),
        ("argument_complete", bool(card.get("argument_complete"))),
        ("title", str(card.get("title", ""))),
        ("report_year", _coerce_int(report_year)),
        ("report_type", report_type),
        ("source_credit", 75),
        ("source_block_id", str(card.get("source_block_id", ""))),
        ("source_unit_ids", source_unit_ids),
        ("fact_anchors", fact_anchors),
        ("secondary_signals", secondary_signals),
        ("quality_score", card.get("quality_score", 0)),
        ("source_excerpt_hash", source_excerpt_hash),
        ("knowledge_fact_status", KNOWLEDGE_FACT_STATUS),
        ("knowledge_eligible", False),
        ("knowledge_persisted", True),
        ("synthesis_eligible", False),
        ("experimental", True),
        ("collected_at", collected_at),
    ]
    if source_block_hash:
        frontmatter_entries.insert(
            next(i for i, entry in enumerate(frontmatter_entries) if entry[0] == "knowledge_fact_status"),
            ("source_block_hash", source_block_hash),
        )

    body = [
        _render_frontmatter(frontmatter_entries),
        f"# {stock_name} {report_year} {report_type} {family}",
        "",
        "## Narrative Evidence",
        "",
        f"> {source_excerpt}",
        "",
        "## Source Units",
        "",
        "```json",
        _json_fence(source_units),
        "```",
        "",
        "## Selection Diagnostics",
        "",
        "```json",
        _json_fence(diagnostics),
        "```",
        "",
        "## Source",
        "",
        f"- card_id: {card.get('card_id', '')}",
        f"- source_block_id: {card.get('source_block_id', '')}",
        f"- source_unit_ids: {', '.join(source_unit_ids)}",
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
    refresh_frontmatter_only: bool = False,
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

        family_or_type = (
            card.get("argument_family")
            if _is_v2_card(card)
            else card.get("card_type")
        )
        filename = "{year}-{rtype}-{family}-{idx}.md".format(
            year=_coerce_int(card.get("report_year")),
            rtype=_safe_filename_segment(str(card.get("report_type", ""))) or "unknown",
            family=_safe_filename_segment(str(family_or_type or "")) or "unknown",
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
                if refresh_frontmatter_only:
                    excerpt = str(card.get("source_excerpt", "")).strip() or "（无摘录）"
                    refreshed_text = _refresh_frontmatter_hashes(
                        target.read_text(encoding="utf-8"),
                        source_excerpt_hash=str(
                            card.get("source_excerpt_hash") or _source_text_hash(excerpt)
                        ),
                        source_block_hash=str(card.get("source_block_hash") or ""),
                    )
                    target.write_text(refreshed_text, encoding="utf-8")
                else:
                    target.write_text(
                        _render_note(
                            card,
                            collected,
                            stock_name=stock_name,
                            stock_code=stock_code,
                        ),
                        encoding="utf-8",
                    )
            meta["reason"] = "refreshed_frontmatter_hashes" if refresh_frontmatter_only else "refreshed_existing"
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
