"""Knowledge note writer for broker research digest cards.

Broker research remains professional analysis material.  This writer only
persists selected digest cards as reviewable notes; it never promotes them to
confirmed facts or scoring/risk inputs.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

if __name__.startswith("utils."):
    from .broker_research_digest import (
        build_broker_research_digest_cards,
        clean_broker_research_excerpt_text,
        deduplicate_broker_digest_cards_by_viewpoint,
        extract_pdf_text,
    )
    from .source_adapter import SynthesisItem
else:
    from broker_research_digest import (
        build_broker_research_digest_cards,
        clean_broker_research_excerpt_text,
        deduplicate_broker_digest_cards_by_viewpoint,
        extract_pdf_text,
    )
    from source_adapter import SynthesisItem


BROKER_RESEARCH_SOURCE_TYPE = "broker_research"
BROKER_RESEARCH_FACT_STATUS = "professional_analysis"
BROKER_EXCERPT_CLEANER_VERSION = "broker_ocr_v2"


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
    excerpt = clean_broker_research_excerpt_text(
        str(card.get("source_excerpt", "")).strip(),
        repair_legacy_artifacts=True,
    )
    excerpt_hash = _source_text_hash(excerpt)
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
            ("excerpt_cleaner_version", BROKER_EXCERPT_CLEANER_VERSION),
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
        and re.search(rf"(?m)^excerpt_cleaner_version:\s*\"?{BROKER_EXCERPT_CLEANER_VERSION}\"?\s*$", text) is not None
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


def refresh_broker_research_digest_card_notes_from_manifest(
    *,
    stock_name: str,
    stock_code: str,
    manifest_path: Union[str, Path],
    base_dir: Union[str, Path],
    max_pdfs: int = 8,
    max_cards_per_pdf: int = 5,
    collected_at: str = "",
    extractor: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    """Build broker digest cards from cached PDFs and refresh Knowledge notes."""
    manifest = Path(manifest_path)
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "unreadable_manifest", "error": str(exc)}

    reports = payload.get("reports") if isinstance(payload, dict) else []
    if not isinstance(reports, list):
        reports = []
    resolved_stock_code = str(stock_code or payload.get("stock_code") or "").strip()
    read_pdf = extractor or extract_pdf_text
    cards: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    processed = 0
    for report in reports[:max_pdfs]:
        if not isinstance(report, dict):
            continue
        pdf_path = _resolve_manifest_pdf_path(report, manifest)
        if pdf_path is None:
            continue
        try:
            pdf_text = read_pdf(str(pdf_path))
        except Exception as exc:
            errors.append({"path": str(pdf_path), "error": str(exc)})
            continue
        item = _research_item_from_manifest_report(
            report,
            pdf_path=pdf_path,
            pdf_text=pdf_text,
            stock_name=stock_name,
            stock_code=resolved_stock_code,
        )
        cards.extend(build_broker_research_digest_cards(item, pdf_text, max_cards=max_cards_per_pdf))
        processed += 1
    if not cards:
        return {"status": "no_cards", "processed_pdf_count": processed, "errors": errors}

    cards = deduplicate_broker_digest_cards_by_viewpoint(cards)
    plan = write_broker_research_digest_card_notes(
        stock_name=stock_name,
        stock_code=resolved_stock_code,
        cards=cards,
        base_dir=base_dir,
        collected_at=collected_at,
    )
    return {
        "status": "ok",
        "processed_pdf_count": processed,
        "cards_count": len(cards),
        "written_count": len(plan.written),
        "skipped_existing_count": len(plan.skipped_existing),
        "filtered_count": len(plan.filtered),
        "errors": errors,
    }


def _resolve_manifest_pdf_path(report: Dict[str, Any], manifest_path: Path) -> Optional[Path]:
    raw_path = str(report.get("path") or report.get("pdf_local_path") or "").strip()
    if not raw_path:
        return None
    path = Path(raw_path)
    project_root = Path(__file__).resolve().parents[2]
    candidates = [path] if path.is_absolute() else [manifest_path.parent / path, project_root / path]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def _research_item_from_manifest_report(
    report: Dict[str, Any],
    *,
    pdf_path: Path,
    pdf_text: str,
    stock_name: str,
    stock_code: str,
) -> SynthesisItem:
    institution = str(report.get("institution") or report.get("orgName") or "券商研报")
    return SynthesisItem(
        title=str(report.get("title") or pdf_path.stem),
        content=str(report.get("title") or pdf_path.stem),
        author=institution,
        source_platform="研报",
        url=str(report.get("url") or ""),
        publish_time=str(report.get("publish_time") or "")[:10],
        interaction_score=0,
        extra={
            "source_type": BROKER_RESEARCH_SOURCE_TYPE,
            "source_credit": 72,
            "verification_status": "professional_observation",
            "institution": institution,
            "stock_name": stock_name,
            "stock_code": stock_code,
            "pdf_local_path": str(pdf_path),
            "pdf_page_count": _infer_pdf_page_count(pdf_text),
        },
    )


def _infer_pdf_page_count(pdf_text: str) -> int:
    return len(re.findall(r"\f", pdf_text or "")) + 1 if "\f" in (pdf_text or "") else 0
