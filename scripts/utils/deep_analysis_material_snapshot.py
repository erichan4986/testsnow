"""Deep-analysis-only MaterialSnapshot read-model.

This module projects existing chapter-4 material fields into a deterministic
read model. It does not mutate ``ctx`` and must not feed executive summary,
scoring, risk, target price, or recommendation paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Tuple


SCHEMA = "deep_analysis_material_snapshot.v1"
DEEP_ANALYSIS_SCOPE = ("deep_analysis",)


@dataclass(frozen=True)
class EvidenceRow:
    row_id: str
    text: str
    source_layer: str
    claim_status: str
    citation_refs: Tuple[int, ...]
    source_ref_ids: Tuple[str, ...]
    display_scope: Tuple[str, ...]
    scoring_eligible: bool
    risk_score_eligible: bool
    section_hint: str = ""


@dataclass(frozen=True)
class MaterialSnapshot:
    schema: str
    rows: Tuple[EvidenceRow, ...]
    citations: Dict[int, Dict[str, Any]]
    diagnostics: Dict[str, Any]


class _CitationAllocator:
    def __init__(self) -> None:
        self._next_ref = 1
        self.citations: Dict[int, Dict[str, Any]] = {}
        self._offset_by_source: Dict[int, int] = {}

    def map_refs(self, local_refs: Iterable[Any], local_citations: Mapping[Any, Any]) -> Tuple[int, ...]:
        source_key = id(local_citations)
        if source_key not in self._offset_by_source:
            self._offset_by_source[source_key] = self._next_ref - 1
        offset = self._offset_by_source[source_key]
        mapped = []
        for ref in local_refs or ():
            try:
                local_ref = int(ref)
            except (TypeError, ValueError):
                continue
            meta = local_citations.get(local_ref) or local_citations.get(str(local_ref)) or {}
            global_ref = offset + local_ref
            self._next_ref = max(self._next_ref, global_ref + 1)
            self.citations[global_ref] = dict(meta) if isinstance(meta, dict) else {}
            mapped.append(global_ref)
        return tuple(mapped)


def build_deep_analysis_material_snapshot(ctx: Mapping[str, Any]) -> MaterialSnapshot:
    """Project current chapter-4 material fields into a deterministic snapshot."""
    allocator = _CitationAllocator()
    rows = []

    annual_memo = ctx.get("annual_report_memo") or {}
    rows.extend(_annual_rows(annual_memo, allocator))

    broker_memo = ctx.get("broker_research_memo") or {}
    rows.extend(_broker_rows(broker_memo, allocator))

    external_display = ctx.get("deep_analysis_display") or {}
    rows.extend(_external_rows(external_display, allocator, ctx.get("deep_analysis_evidence_profile") or {}))

    diagnostics = _diagnostics(ctx, rows)
    return MaterialSnapshot(
        schema=SCHEMA,
        rows=tuple(rows),
        citations=allocator.citations,
        diagnostics=diagnostics,
    )


def _annual_rows(memo: Mapping[str, Any], allocator: _CitationAllocator) -> list[EvidenceRow]:
    sections = memo.get("sections") or {}
    citations = memo.get("citations") or {}
    result = []
    section_status = {
        "confirmed": "formal_fact",
        "annual_report_explanation": "formal_explanation",
        "not_disclosed": "disclosure_boundary",
        "inconclusive": "disclosure_boundary",
    }
    for section, claim_status in section_status.items():
        for idx, row in enumerate(sections.get(section) or []):
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            body = str(row.get("body") or "").strip()
            text = f"{title}：{body}" if title and body else title or body
            result.append(_make_row(
                row_id=f"annual:{section}:{idx}",
                text=text,
                source_layer="annual",
                claim_status=claim_status,
                citation_refs=allocator.map_refs(row.get("citation_refs") or [], citations),
                source_ref_ids=row.get("source_ref_ids") or [],
                section_hint="annual_memo",
            ))
    return result


def _broker_rows(memo: Mapping[str, Any], allocator: _CitationAllocator) -> list[EvidenceRow]:
    citations = memo.get("citations") or {}
    result = []
    for section in ("sections", "forecast_ranges", "risks"):
        for idx, row in enumerate(memo.get(section) or []):
            if not isinstance(row, dict):
                continue
            text = _broker_row_text(section, row)
            result.append(_make_row(
                row_id=f"broker:{section}:{idx}",
                text=text,
                source_layer="broker",
                claim_status="professional_analysis",
                citation_refs=allocator.map_refs(row.get("citation_refs") or [], citations),
                source_ref_ids=row.get("source_ref_ids") or [],
                section_hint="broker_memo",
            ))
    return result


def _external_rows(display: Mapping[str, Any], allocator: _CitationAllocator, profile: Mapping[str, Any]) -> list[EvidenceRow]:
    citations = display.get("citations") or {}
    result = []
    section_hint = "external_map" if profile.get("profile") == "formal_thin_external_rich" else "external_addendum"

    for idx, card in enumerate(display.get("_curated_external_reasoning_cards") or []):
        if not isinstance(card, dict):
            continue
        text = str(card.get("claim") or card.get("verification_need") or "").strip()
        result.append(_make_row(
            row_id=f"external:reasoning_cards:{idx}",
            text=text,
            source_layer="external",
            claim_status="external_observation",
            citation_refs=allocator.map_refs(card.get("citation_refs") or [], citations),
            source_ref_ids=card.get("source_ref_ids") or [],
            section_hint=section_hint,
        ))

    for group_name, group_rows in (display.get("_curated_external_topic_groups") or {}).items():
        if not isinstance(group_rows, list):
            continue
        for idx, row in enumerate(group_rows):
            if not isinstance(row, dict):
                continue
            heading = str(row.get("heading") or "").strip()
            body = str(row.get("text") or "").strip()
            text = f"{heading}：{body}" if heading and body else heading or body
            result.append(_make_row(
                row_id=f"external:topic_groups:{group_name}:{idx}",
                text=text,
                source_layer="external",
                claim_status="external_observation",
                citation_refs=allocator.map_refs(row.get("citation_refs") or [], citations),
                source_ref_ids=row.get("source_ref_ids") or [],
                section_hint=section_hint,
            ))

    for idx, paragraph in enumerate(display.get("_curated_external_narrative_paragraphs") or []):
        if not isinstance(paragraph, dict):
            continue
        heading = str(paragraph.get("heading") or "").strip()
        body = str(paragraph.get("text") or "").strip()
        text = f"{heading}：{body}" if heading and body else heading or body
        result.append(_make_row(
            row_id=f"external:narrative_paragraphs:{idx}",
            text=text,
            source_layer="external",
            claim_status="external_observation",
            citation_refs=allocator.map_refs(paragraph.get("citation_refs") or [], citations),
            source_ref_ids=paragraph.get("source_ref_ids") or [],
            section_hint=section_hint,
        ))
    return result


def _broker_row_text(section: str, row: Mapping[str, Any]) -> str:
    if section == "forecast_ranges":
        return " ".join(str(row.get(key) or "").strip() for key in ("metric", "period", "range") if row.get(key))
    title = str(row.get("title") or "").strip()
    body = str(row.get("body") or "").strip()
    return f"{title}：{body}" if title and body else title or body


def _make_row(
    *,
    row_id: str,
    text: str,
    source_layer: str,
    claim_status: str,
    citation_refs: Iterable[int],
    source_ref_ids: Iterable[Any],
    section_hint: str,
) -> EvidenceRow:
    return EvidenceRow(
        row_id=row_id,
        text=str(text or "").strip(),
        source_layer=source_layer,
        claim_status=claim_status,
        citation_refs=tuple(int(ref) for ref in citation_refs),
        source_ref_ids=tuple(str(ref) for ref in (source_ref_ids or ()) if str(ref)),
        display_scope=DEEP_ANALYSIS_SCOPE,
        scoring_eligible=False,
        risk_score_eligible=False,
        section_hint=section_hint,
    )


def _diagnostics(ctx: Mapping[str, Any], rows: list[EvidenceRow]) -> Dict[str, Any]:
    fundflow = ctx.get("fundflow_material_pack") or {}
    peer = ctx.get("peer_comparison_material") or {}
    peer_rows = [row for row in (peer.get("rows") or []) if isinstance(row, dict)]
    return {
        "rows_count": len(rows),
        "annual_rows_count": sum(1 for row in rows if row.source_layer == "annual"),
        "broker_rows_count": sum(1 for row in rows if row.source_layer == "broker"),
        "external_rows_count": sum(1 for row in rows if row.source_layer == "external"),
        "fundflow_rows_count": len(fundflow.get("rows") or []),
        "fundflow_summary_signal": (fundflow.get("summary") or {}).get("signal", ""),
        "fundflow_has_sidecar_material": bool(fundflow.get("rows")),
        "peer_rows_count": len(peer_rows),
        "peer_high_confidence_rows": sum(1 for row in peer_rows if _to_float(row.get("confidence")) >= 0.7),
        "peer_has_social_leak": any(_has_social_ref(row.get("source_refs") or []) for row in peer_rows),
    }


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _has_social_ref(refs: Iterable[Any]) -> bool:
    tokens = ("雪球", "知乎", "微信", "精选外部", "社区", "xueqiu", "zhihu", "wechat")
    return any(any(token in str(ref) for token in tokens) for ref in refs or ())
