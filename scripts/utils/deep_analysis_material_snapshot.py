"""Deep-analysis-only MaterialSnapshot read-model.

This module projects existing chapter-4 material fields into a deterministic
read model. It does not mutate ``ctx`` and must not feed executive summary,
scoring, risk, target price, or recommendation paths.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Dict, Iterable, Mapping, Tuple


SCHEMA = "deep_analysis_material_snapshot.v1"
DEEP_ANALYSIS_SCOPE = ("deep_analysis",)


@dataclass(frozen=True)
class MaterialRow:
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
    title: str = ""
    body: str = ""
    render_role: str = ""
    attribution: str = ""
    source_credit: str = ""
    diagnostics: Tuple[Tuple[str, str], ...] = ()


# Compatibility name for existing callers and tests. MaterialRow is the
# canonical Chapter 4 row contract from V2 onward.
EvidenceRow = MaterialRow


@dataclass(frozen=True)
class MaterialSnapshot:
    schema: str
    rows: Tuple[MaterialRow, ...]
    citations: Dict[int, Dict[str, Any]]
    diagnostics: Dict[str, Any]


@dataclass(frozen=True)
class Chapter4Section:
    section_id: str
    title: str
    rows: Tuple[MaterialRow, ...]
    disclaimer: str = ""


@dataclass(frozen=True)
class Chapter4ViewModel:
    profile: str
    sections: Tuple[Chapter4Section, ...]
    citations: Dict[int, Dict[str, Any]]
    diagnostics: Dict[str, Any]

    def section(self, section_id: str) -> Chapter4Section:
        for section in self.sections:
            if section.section_id == section_id:
                return section
        raise KeyError(section_id)


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


def build_chapter4_view_model(
    snapshot: MaterialSnapshot,
    profile: Mapping[str, Any] | str,
) -> Chapter4ViewModel:
    """Admit normalized rows into the formal-medium Chapter 4 layout."""
    profile_name = profile if isinstance(profile, str) else str((profile or {}).get("profile") or "")
    if profile_name != "formal_medium":
        raise ValueError(f"Chapter4ViewModel V1 only supports formal_medium, got {profile_name!r}")

    annual_rows = tuple(
        row for row in snapshot.rows
        if row.source_layer == "annual"
        and row.claim_status in {"formal_fact", "formal_explanation"}
        and row.text
        and row.citation_refs
    )
    broker_rows = tuple(
        row for row in snapshot.rows
        if row.source_layer == "broker"
        and row.text
        and row.citation_refs
        and row.attribution
    )
    external_rows = tuple(
        _dedupe_row_refs_by_citation_identity(row, snapshot.citations)
        for row in snapshot.rows
        if row.source_layer == "external"
        and row.text
        and row.citation_refs
        and not row.scoring_eligible
        and not row.risk_score_eligible
    )
    price_path_rows = tuple(
        row for row in (
            _first_row_by_role(annual_rows, (
                "product_business",
                "operation_update",
                "management_view",
                "competitiveness_rd",
                "financial_explanation",
            )),
            _first_row_by_role(broker_rows, ("broker_assumption", "broker_forecast")),
            external_rows[0] if external_rows else None,
        )
        if row is not None
    )
    sections = (
        Chapter4Section("4.1", "官方材料确认：业务与财务基座", annual_rows),
        Chapter4Section("4.2", "机构观点与盈利假设", broker_rows),
        Chapter4Section(
            "4.3",
            "外部观察与待验证变量（Preview，不参与评分）",
            external_rows,
            "以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或目标价。",
        ),
        Chapter4Section(
            "4.4",
            "上行 / 下行条件与股价推演",
            price_path_rows,
            "本节只做股价方向的条件推演，不直接修改目标价、评分、风险评分或最终推荐。",
        ),
    )
    visible_refs = {
        ref
        for section in sections
        for row in section.rows
        for ref in row.citation_refs
    }
    citations = {
        ref: dict(snapshot.citations.get(ref) or {})
        for ref in sorted(visible_refs)
        if ref in snapshot.citations
    }
    diagnostics = dict(snapshot.diagnostics)
    diagnostics.update({
        "profile": profile_name,
        "visible_rows_count": sum(len(section.rows) for section in sections[:3]),
        "visible_citation_count": len(citations),
    })
    return Chapter4ViewModel(
        profile=profile_name,
        sections=sections,
        citations=citations,
        diagnostics=diagnostics,
    )


def _annual_rows(memo: Mapping[str, Any], allocator: _CitationAllocator) -> list[MaterialRow]:
    if memo.get("status") not in {"ready", "deterministic_fallback"}:
        return []
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
                title=title,
                body=body,
                render_role=_annual_render_role(title, row.get("display_group")),
                source_credit="official",
                diagnostics=_row_diagnostics(row),
            ))
    return result


def _broker_rows(memo: Mapping[str, Any], allocator: _CitationAllocator) -> list[MaterialRow]:
    if memo.get("status") not in {"ready", "single_institution"}:
        return []
    citations = memo.get("citations") or {}
    result = []
    for section in ("sections", "forecast_ranges", "risks"):
        for idx, row in enumerate(memo.get(section) or []):
            if not isinstance(row, dict):
                continue
            text = _broker_row_text(section, row)
            title, body = _broker_title_body(section, row)
            refs = allocator.map_refs(row.get("citation_refs") or [], citations)
            result.append(_make_row(
                row_id=f"broker:{section}:{idx}",
                text=text,
                source_layer="broker",
                claim_status="professional_analysis",
                citation_refs=refs,
                source_ref_ids=row.get("source_ref_ids") or [],
                section_hint="broker_memo",
                title=title,
                body=body,
                render_role={
                    "sections": "broker_assumption",
                    "forecast_ranges": "broker_forecast",
                    "risks": "broker_risk",
                }[section],
                attribution=_broker_attribution(row, refs, allocator.citations),
                source_credit="professional",
                diagnostics=_row_diagnostics(row),
            ))
    return result


def _external_rows(display: Mapping[str, Any], allocator: _CitationAllocator, profile: Mapping[str, Any]) -> list[MaterialRow]:
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
            title=str(card.get("heading") or "外部变量").strip(),
            body=text,
            render_role="external_variable",
            source_credit="external_low_credit",
            diagnostics=_row_diagnostics(card),
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
                title=heading or "外部变量",
                body=body,
                render_role="external_variable",
                source_credit="external_low_credit",
                diagnostics=_row_diagnostics(row),
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
            title=heading or "外部变量",
            body=body,
            render_role="external_variable",
            source_credit="external_low_credit",
            diagnostics=_row_diagnostics(paragraph),
        ))
    return result


def _broker_row_text(section: str, row: Mapping[str, Any]) -> str:
    if section == "forecast_ranges":
        return " ".join(str(row.get(key) or "").strip() for key in ("metric", "period", "range") if row.get(key))
    title = str(row.get("title") or "").strip()
    body = str(row.get("body") or "").strip()
    return f"{title}：{body}" if title and body else title or body


def _broker_title_body(section: str, row: Mapping[str, Any]) -> tuple[str, str]:
    if section == "forecast_ranges":
        title = "".join(str(row.get(key) or "").strip() for key in ("metric", "period"))
        return title or "盈利预测", str(row.get("range") or "").strip()
    title = str(row.get("title") or ("反方约束" if section == "risks" else "机构核心观点")).strip()
    return title, str(row.get("body") or "").strip()


def _make_row(
    *,
    row_id: str,
    text: str,
    source_layer: str,
    claim_status: str,
    citation_refs: Iterable[int],
    source_ref_ids: Iterable[Any],
    section_hint: str,
    title: str = "",
    body: str = "",
    render_role: str = "",
    attribution: str = "",
    source_credit: str = "",
    diagnostics: Iterable[tuple[str, str]] = (),
) -> MaterialRow:
    return MaterialRow(
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
        title=str(title or "").strip(),
        body=str(body or "").strip(),
        render_role=str(render_role or "").strip(),
        attribution=str(attribution or "").strip(),
        source_credit=str(source_credit or "").strip(),
        diagnostics=tuple((str(key), str(value)) for key, value in diagnostics),
    )


def _annual_render_role(title: str, configured_group: Any = "") -> str:
    configured = str(configured_group or "").strip()
    if configured:
        return configured
    if any(term in title for term in ("收入", "利润", "费用", "现金流", "存货", "减值", "毛利率")):
        return "financial_explanation"
    if any(term in title for term in ("研发", "技术", "竞争")):
        return "competitiveness_rd"
    if any(term in title for term in ("主营", "产品", "业务")):
        return "product_business"
    if any(term in title for term in ("经营", "进展", "更新")):
        return "operation_update"
    if any(term in title for term in ("管理层", "市场", "行业", "前景")):
        return "management_view"
    return "other"


def _broker_attribution(
    row: Mapping[str, Any],
    refs: Iterable[int],
    citations: Mapping[int, Any],
) -> str:
    for ref in refs:
        meta = citations.get(ref) or {}
        author = str(meta.get("author") or "").strip() if isinstance(meta, Mapping) else ""
        if author:
            return author
    body = str(row.get("body") or row.get("range") or "").strip()
    match = re.match(r"^([^：:，,]{2,12}?)(?:研报)?(?:认为|预计|提示)", body)
    if match and match.group(1) not in {"券商", "机构", "研报"}:
        return match.group(1).strip()
    return "研报"


def _row_diagnostics(row: Mapping[str, Any]) -> Tuple[Tuple[str, str], ...]:
    keys = ("selection_reason", "source_heading", "score", "status", "excerpt_cleaner_version")
    return tuple((key, str(row.get(key))) for key in keys if row.get(key) not in (None, ""))


def _first_row_by_role(
    rows: Iterable[MaterialRow],
    roles: Iterable[str],
) -> MaterialRow | None:
    row_list = tuple(rows)
    for role in roles:
        for row in row_list:
            if row.render_role == role:
                return row
    return row_list[0] if row_list else None


def _dedupe_row_refs_by_citation_identity(
    row: MaterialRow,
    citations: Mapping[int, Any],
) -> MaterialRow:
    refs = []
    seen = set()
    for ref in row.citation_refs:
        meta = citations.get(ref) or {}
        identity = _citation_identity(meta, ref)
        if identity in seen:
            continue
        seen.add(identity)
        refs.append(ref)
    return replace(row, citation_refs=tuple(refs))


def _citation_identity(meta: Any, fallback_ref: int) -> tuple:
    if not isinstance(meta, Mapping):
        return ("ref", fallback_ref)
    url = str(meta.get("url") or "").strip()
    if url:
        return ("url", url)
    identity = tuple(
        str(meta.get(key) or "").strip()
        for key in ("source", "author", "title")
    )
    return ("meta",) + identity if any(identity) else ("ref", fallback_ref)


def _diagnostics(ctx: Mapping[str, Any], rows: list[MaterialRow]) -> Dict[str, Any]:
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
