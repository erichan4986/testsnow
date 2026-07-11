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
    display_scope: Tuple[str, ...] = DEEP_ANALYSIS_SCOPE
    scoring_eligible: bool = False
    risk_score_eligible: bool = False
    section_hint: str = ""
    title: str = ""
    body: str = ""
    render_role: str = ""
    argument_complete: bool = False
    attribution: str = ""
    source_credit: str = ""
    diagnostics: Tuple[Tuple[str, str], ...] = ()

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
    profile = ctx.get("deep_analysis_evidence_profile") or {}
    rows = [
        *_annual_rows(ctx.get("annual_report_memo") or {}, allocator),
        *_broker_rows(ctx.get("broker_research_memo") or {}, allocator),
        *_external_rows(ctx.get("deep_analysis_display") or {}, allocator, profile),
    ]
    return MaterialSnapshot(
        schema=SCHEMA,
        rows=tuple(rows),
        citations=allocator.citations,
        diagnostics=_diagnostics(ctx, rows),
    )


def build_chapter4_view_model(
    snapshot: MaterialSnapshot,
    profile: Mapping[str, Any] | str,
) -> Chapter4ViewModel:
    """Admit normalized rows into the formal-medium Chapter 4 layout."""
    profile_name = profile if isinstance(profile, str) else str((profile or {}).get("profile") or "")
    if profile_name != "formal_medium":
        raise ValueError(f"Chapter4ViewModel V1 only supports formal_medium, got {profile_name!r}")

    usable_rows = tuple(row for row in snapshot.rows if row.text and row.citation_refs)
    annual_rows = tuple(
        row for row in usable_rows
        if row.source_layer == "annual" and row.claim_status in {"formal_fact", "formal_explanation"}
    )
    broker_rows = tuple(row for row in usable_rows if row.source_layer == "broker" and row.attribution)
    external_rows = tuple(
        _dedupe_row_refs_by_citation_identity(row, snapshot.citations)
        for row in usable_rows
        if row.source_layer == "external"
        and not row.scoring_eligible
        and not row.risk_score_eligible
    )
    complete_annual_rows = tuple(row for row in annual_rows if row.argument_complete)
    price_path_rows = tuple(
        row for row in (
            _first_row_by_role(complete_annual_rows, (
                "business_structure",
                "operating_progress",
                "market_competition_outlook",
                "technology_product_progress",
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
    visible_refs = sorted({
        ref
        for section in sections
        for row in section.rows
        for ref in row.citation_refs
    })
    citations = {
        ref: dict(snapshot.citations.get(ref) or {})
        for ref in visible_refs
        if ref in snapshot.citations
    }
    diagnostics = dict(snapshot.diagnostics)
    diagnostics.update({
        "profile": profile_name,
        "visible_rows_count": sum(len(section.rows) for section in sections[:3]),
        "visible_citation_count": len(citations),
    })
    return Chapter4ViewModel(profile_name, sections, citations, diagnostics)


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
            result.append(_adapt_material_row(
                row,
                allocator,
                citations,
                f"annual:{section}:{idx}",
                source_layer="annual",
                claim_status=claim_status,
                section_hint="annual_memo",
                title=title,
                render_role=str(row.get("argument_family") or row.get("display_group") or "").strip(),
                argument_complete=bool(row.get("argument_complete", False)),
                source_credit="official",
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
            title, body = _broker_title_body(section, row)
            material_row = _adapt_material_row(
                row,
                allocator,
                citations,
                f"broker:{section}:{idx}",
                source_layer="broker",
                claim_status="professional_analysis",
                section_hint="broker_memo",
                title=title,
                body=body,
                render_role={
                    "sections": "broker_assumption",
                    "forecast_ranges": "broker_forecast",
                    "risks": "broker_risk",
                }[section],
                source_credit="professional",
            )
            result.append(replace(
                material_row,
                attribution=_broker_attribution(row, material_row.citation_refs, allocator.citations),
            ))
    return result


def _external_rows(display: Mapping[str, Any], allocator: _CitationAllocator, profile: Mapping[str, Any]) -> list[MaterialRow]:
    citations = display.get("citations") or {}
    result = []
    section_hint = "external_map" if profile.get("profile") == "formal_thin_external_rich" else "external_addendum"
    sources = [("reasoning_cards", display.get("_curated_external_reasoning_cards") or [])]
    sources.extend(
        (f"topic_groups:{name}", rows)
        for name, rows in (display.get("_curated_external_topic_groups") or {}).items()
        if isinstance(rows, list)
    )
    sources.append(("narrative_paragraphs", display.get("_curated_external_narrative_paragraphs") or []))
    for bucket, source_rows in sources:
        for idx, row in enumerate(source_rows):
            if not isinstance(row, dict):
                continue
            body = (
                str(row.get("claim") or row.get("verification_need") or "")
                if bucket == "reasoning_cards"
                else str(row.get("text") or "")
            ).strip()
            result.append(_adapt_material_row(
                row,
                allocator,
                citations,
                f"external:{bucket}:{idx}",
                source_layer="external",
                claim_status="external_observation",
                section_hint=section_hint,
                title=str(row.get("heading") or "外部变量").strip(),
                body=body,
                render_role="external_variable",
                source_credit="external_low_credit",
            ))
    return result


def _broker_title_body(section: str, row: Mapping[str, Any]) -> tuple[str, str]:
    if section == "forecast_ranges":
        title = "".join(str(row.get(key) or "").strip() for key in ("metric", "period"))
        return title or "盈利预测", str(row.get("range") or "").strip()
    title = str(row.get("title") or ("反方约束" if section == "risks" else "机构核心观点")).strip()
    return title, str(row.get("body") or "").strip()


def _adapt_material_row(
    source: Mapping[str, Any],
    allocator: _CitationAllocator,
    citations: Mapping[Any, Any],
    row_id: str,
    *,
    source_layer: str,
    claim_status: str,
    section_hint: str,
    title: str | None = None,
    body: str | None = None,
    render_role: str = "",
    argument_complete: bool = False,
    attribution: str = "",
    source_credit: str = "",
) -> MaterialRow:
    title = str(source.get("title") if title is None else title).strip()
    body = str(source.get("body") if body is None else body).strip()
    return MaterialRow(
        row_id=row_id,
        text=f"{title}：{body}" if title and body else title or body,
        source_layer=source_layer,
        claim_status=claim_status,
        citation_refs=allocator.map_refs(source.get("citation_refs") or (), citations),
        source_ref_ids=tuple(str(ref) for ref in (source.get("source_ref_ids") or ()) if str(ref)),
        section_hint=section_hint,
        title=title,
        body=body,
        render_role=str(render_role or "").strip(),
        argument_complete=bool(argument_complete),
        attribution=str(attribution or "").strip(),
        source_credit=str(source_credit or "").strip(),
        diagnostics=_row_diagnostics(source),
    )


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


def _first_row_by_role(rows: Iterable[MaterialRow], roles: Iterable[str]) -> MaterialRow | None:
    row_list = tuple(rows)
    return next(
        (row for role in roles for row in row_list if row.render_role == role),
        row_list[0] if row_list else None,
    )


def _dedupe_row_refs_by_citation_identity(
    row: MaterialRow,
    citations: Mapping[int, Any],
) -> MaterialRow:
    refs = []
    seen = set()
    for ref in row.citation_refs:
        meta = citations.get(ref) or {}
        identity = citation_identity(meta, fallback_ref=ref)
        if identity in seen:
            continue
        seen.add(identity)
        refs.append(ref)
    return replace(row, citation_refs=tuple(refs))


def citation_identity(meta: Any, fallback_ref: int | None = None) -> tuple:
    if not isinstance(meta, Mapping):
        return ("ref", fallback_ref) if fallback_ref is not None else ()
    url = str(meta.get("url") or "").strip()
    if url:
        return ("url", url)
    identity = tuple(
        str(meta.get(key) or "").strip()
        for key in ("source", "author", "title")
    )
    if any(identity):
        return ("meta",) + identity
    return ("ref", fallback_ref) if fallback_ref is not None else ()


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
