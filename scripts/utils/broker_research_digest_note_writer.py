"""Knowledge note writer for broker research digest cards.

Broker research remains professional analysis material.  This writer only
persists selected digest cards as reviewable notes; it never promotes them to
confirmed facts or scoring/risk inputs.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


BROKER_RESEARCH_SOURCE_TYPE = "broker_research"
BROKER_RESEARCH_FACT_STATUS = "professional_analysis"


@dataclass
class BrokerResearchDigestWritePlan:
    """Result of writing broker research digest cards."""

    written: List[Dict[str, Any]] = field(default_factory=list)
    skipped_existing: List[Dict[str, Any]] = field(default_factory=list)
    filtered: List[Dict[str, Any]] = field(default_factory=list)


def _safe_dir_segment(segment: str, *, fallback: str = "unknown") -> str:
    text = str(segment or "").replace("\x00", "")
    text = re.sub(r"[\\/]+", "-", text)
    text = re.sub(r"\.{2,}", "-", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-. ")
    return text or fallback


def _safe_filename_segment(segment: str, *, fallback: str = "unknown") -> str:
    text = str(segment or "").replace("\x00", "")
    text = re.sub(r"[\\/：:，,。；;（）()\[\]【】]+", "-", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-_. ")
    return text or fallback


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\-]*", text):
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _render_frontmatter(entries: List[tuple[str, Any]]) -> str:
    lines = ["---"]
    for key, value in entries:
        lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _source_text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _card_tail(card_id: str) -> str:
    tail = str(card_id or "").rsplit(":", 1)[-1]
    tail = tail.rsplit("-", 1)[-1] if ":" not in str(card_id or "") else tail
    return _safe_filename_segment(tail[:24], fallback="card")


def _target_filename(card: Dict[str, Any]) -> str:
    publish_date = str(card.get("publish_time", ""))[:10] or "unknown-date"
    institution = _safe_filename_segment(str(card.get("institution", "")), fallback="broker")
    card_type = _safe_filename_segment(str(card.get("card_type", ""))).replace("_", "-")
    tail = _card_tail(str(card.get("card_id", "")))
    return f"{publish_date}-{institution}-{card_type}-{tail}.md"


def _render_note(card: Dict[str, Any], *, stock_name: str, stock_code: str, collected_at: str) -> str:
    excerpt = str(card.get("source_excerpt", "")).strip()
    excerpt_hash = str(card.get("source_excerpt_hash") or _source_text_hash(excerpt))
    selection_reason = str(card.get("selection_reason", "")).strip()
    frontmatter = _render_frontmatter(
        [
            ("stock", stock_name),
            ("code", stock_code),
            ("source_type", BROKER_RESEARCH_SOURCE_TYPE),
            ("card_id", str(card.get("card_id", ""))),
            ("schema_version", str(card.get("schema_version", ""))),
            ("card_type", str(card.get("card_type", ""))),
            ("title", str(card.get("title", ""))),
            ("report_title", str(card.get("report_title", ""))),
            ("institution", str(card.get("institution", ""))),
            ("publish_time", str(card.get("publish_time", ""))),
            ("source_credit", 72),
            ("claim_status", BROKER_RESEARCH_FACT_STATUS),
            ("verification_status", "professional_observation"),
            ("knowledge_fact_status", BROKER_RESEARCH_FACT_STATUS),
            ("knowledge_eligible", True),
            ("knowledge_persisted", True),
            ("confirmed_fact", False),
            ("scoring_eligible", False),
            ("risk_score_eligible", False),
            ("display_only", False),
            ("source_excerpt_hash", excerpt_hash),
            ("source_pdf_path", str(card.get("source_pdf_path", ""))),
            ("source_url", str(card.get("source_url", ""))),
            ("source_heading", str(card.get("source_heading", ""))),
            ("selection_reason", selection_reason),
            ("viewpoint_cluster", str(card.get("viewpoint_cluster", ""))),
            ("report_length_class", str(card.get("report_length_class", ""))),
            ("collected_at", collected_at),
        ]
    )
    lines = [
        frontmatter,
        f"# {stock_name} broker research digest",
        "",
        "## Broker Research Excerpt",
        "",
        f"> {excerpt or '（无摘录）'}",
        "",
        "## Selection Diagnostics",
        "",
        f"- selection_reason: `{selection_reason or 'selected_by_digest_quality_score'}`",
    ]
    for entry in (card.get("selection_diagnostics") or [])[:8]:
        if not isinstance(entry, dict):
            continue
        lines.append(
            "- "
            f"heading=`{entry.get('heading', '')}` | "
            f"score=`{entry.get('score', '')}` | "
            f"status=`{entry.get('status', '')}` | "
            f"reason=`{entry.get('reason', '')}`"
        )
    lines.extend(
        [
            "",
            "## Source",
            "",
            f"- institution: {card.get('institution', '')}",
            f"- report_title: {card.get('report_title', '')}",
            f"- publish_time: {card.get('publish_time', '')}",
            f"- source_pdf_path: {card.get('source_pdf_path', '')}",
            "",
            "## Guardrails",
            "",
            "- Broker research is professional analysis, not confirmed fact.",
            "- It stays outside scoring, risk scoring, and automated fact confirmation.",
            "",
        ]
    )
    return "\n".join(lines)


def _has_current_diagnostics_note_shape(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return (
        re.search(r'(?m)^schema_version:\s*"?broker_research_digest_card\.v1"?\s*$', text) is not None
        and re.search(r"(?m)^selection_reason:", text) is not None
        and "## Selection Diagnostics" in text
    )


def _filter_reason(card: Dict[str, Any], stock_code: str) -> Optional[str]:
    if str(card.get("source_type", "")) != BROKER_RESEARCH_SOURCE_TYPE:
        return f"source_type not broker_research: {card.get('source_type') or '<empty>'}"
    if bool(card.get("display_only")) or not bool(card.get("knowledge_eligible", True)):
        return "display-only or not knowledge eligible"
    if not str(card.get("card_id", "")):
        return "missing required field: card_id"
    if not str(card.get("card_type", "")):
        return "missing required field: card_type"
    if not str(card.get("source_excerpt", "")).strip():
        return "missing required field: source_excerpt"
    card_stock_code = str(card.get("stock_code", ""))
    if card_stock_code and card_stock_code != str(stock_code):
        return f"stock_code mismatch: {card_stock_code} != {stock_code}"
    return None


def write_broker_research_digest_card_notes(
    *,
    stock_name: str,
    stock_code: str,
    cards: List[Dict[str, Any]],
    base_dir: Union[str, Path],
    collected_at: str = "",
    dry_run: bool = False,
) -> BrokerResearchDigestWritePlan:
    """Write selected broker research digest cards to Knowledge notes."""
    plan = BrokerResearchDigestWritePlan()
    notes_dir = Path(base_dir) / "10-Stocks" / _safe_dir_segment(stock_name) / "broker_research_digest"
    notes_dir_resolved = notes_dir.resolve()

    for card in cards:
        if not isinstance(card, dict):
            plan.filtered.append({"card_id": "", "reason": "malformed card entry"})
            continue
        card_id = str(card.get("card_id", ""))
        reason = _filter_reason(card, stock_code)
        if reason:
            plan.filtered.append({"card_id": card_id, "reason": reason})
            continue

        target = notes_dir / _target_filename(card)
        if target.resolve().parent != notes_dir_resolved:
            plan.filtered.append({"card_id": card_id, "reason": "path escape blocked"})
            continue
        meta = {"card_id": card_id, "planned_path": str(target)}
        if target.exists():
            if _has_current_diagnostics_note_shape(target):
                meta["reason"] = "note already exists"
                plan.skipped_existing.append(meta)
                continue
            meta["reason"] = "refreshed missing selection diagnostics"
        if not dry_run:
            notes_dir.mkdir(parents=True, exist_ok=True)
            target.write_text(
                _render_note(
                    card,
                    stock_name=stock_name,
                    stock_code=stock_code,
                    collected_at=collected_at,
                ),
                encoding="utf-8",
            )
        plan.written.append(meta)
    return plan
