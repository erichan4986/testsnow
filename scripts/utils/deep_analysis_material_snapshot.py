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


def select_annual_display_rows(
    rows: Iterable[MaterialRow],
) -> tuple[Tuple[MaterialRow, ...], Dict[str, Any]]:
    """Project complete annual rows into the Chapter 4 display subset."""
    candidates = tuple(row for row in rows if row.source_layer == "annual" and row.claim_status in {"formal_fact", "formal_explanation"})
    selected = []
    rejected: Dict[str, int] = {}
    for row in candidates:
        projected, reason = _project_annual_display_row(row)
        if projected is None:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        selected.append(projected)

    deduped, deduped_count, dedupe_reasons = _dedupe_annual_display_rows(selected)
    for reason, count in dedupe_reasons.items():
        rejected[reason] = rejected.get(reason, 0) + count
    return deduped, {
        "annual_candidates_count": len(candidates),
        "annual_selected_count": len(deduped),
        "annual_rejected_by_reason": rejected,
        "annual_deduped_count": deduped_count,
    }


def _project_annual_display_row(row: MaterialRow) -> tuple[MaterialRow | None, str]:
    if not row.body or not row.citation_refs:
        return None, "empty"
    kept = []
    reasons = []
    for segment in re.split(r"(?<=[。！？；;])", row.body):
        segment = re.sub(r"^(?:\d+[、.]\s*(?:主要业务|主要产品及服务情况)\s*|\d+(?:\.\d+)+\s*[^，。；;\d]{1,20}\s+(?=\S)|（?[^）]{1,20}）?芯片\s*\d+[、.]\s*|(?:报告期内公司从事的主要业务)?公司需遵守《[^》]+》[^。；，,]*披露要求[，,]*(?=公司(?:主营|主要业务|产品)))", "", segment)
        if not segment:
            reasons.append("disclosure_or_governance")
            continue
        routine_marker = next((term for term in ("采购模式", "生产模式", "经营模式", "销售模式", "代理销售", "认证程序", "生产流程") if term in segment), None)
        if routine_marker:
            prefix = segment.split(routine_marker, 1)[0].strip(" ，,；;。")
            if prefix and any(term in prefix for term in ("主营业务", "产品", "客户", "设备", "服务", "研发")):
                segment = prefix
        reason = _annual_segment_rejection_reason(segment, row.render_role)
        is_titled_financial_fact = (
            row.claim_status == "formal_fact"
            and re.fullmatch(r"\d[\d,，.]*(?:%|％|亿元|万元|亿|万)", re.sub(r"\s+", "", segment))
            and any(term in row.title for term in ("收入", "营收", "利润", "毛利率", "费用", "现金流", "存货"))
        )
        if reason and not is_titled_financial_fact:
            reasons.append(reason)
            continue
        if re.sub(r"\s+", "", segment) not in {re.sub(r"\s+", "", part) for part in kept}:
            kept.append(segment)
    if not kept:
        return None, reasons[0] if reasons else "role_mismatch"
    projected_body = "".join(part if not index or kept[index - 1][-1:] in "。！？；;" else f"。{part}" for index, part in enumerate(kept)).strip()
    if not projected_body:
        return None, "empty"
    if projected_body == row.body:
        return row, ""
    return replace(row, body=projected_body, text=f"{row.title}：{projected_body}" if row.title else projected_body), ""


def _annual_segment_rejection_reason(segment: str, role: str) -> str:
    compact = re.sub(r"\s+", "", segment)
    if not compact:
        return "empty"
    if "我们认为" in compact and "财务报表" in compact and "公允反映" in compact:
        return "audit_boilerplate"
    if (
        "公司需遵守" in compact
        or "披露要求" in compact
        or "机构独立情况" in compact
        or any(term in compact for term in ("供应商遴选", "本承诺函", "同业竞争", "保证独立性", "自主经营能力", "香港联交所", "无从事与本公司相同或相近的业务"))
        or (any(term in compact for term in ("同业竞争", "关联交易", "资金占用")) and "承诺" in compact)
    ):
        return "disclosure_or_governance"
    if compact.startswith(">") or "|" in compact or "年度报告全文" in compact or "http://" in compact or "https://" in compact or re.match(r"^\d+[、.]\s*.{0,24}(?:风险|关税政策变化)", compact):
        return "document_or_heading_noise"
    if compact.endswith(("、", ":", "：", "…", "...")) or compact.startswith(("方面，", "其中，", "此外，", "核心竞争力，", "并在", "与世界")) or ("知识产权列表" in compact and "申请数" in compact):
        return "document_or_heading_noise"
    if len(compact) <= 16 and not any(term in compact for term in ("公司", "产品", "客户", "收入", "增长", "研发")):
        return "document_or_heading_noise"

    progress = ("报告期内", "实现", "增长", "下降", "出货", "导入", "进入", "量产", "拓展", "提升", "改善", "推出", "发布", "验证", "新增", "覆盖")
    linked = ("公司", "本集团", "管理层", "报告期内", "营收", "出货", "销量", "客户导入", "销售增长", "销售下滑")
    if any(term in compact for term in ("采购模式", "生产模式", "经营模式", "销售模式", "代理销售", "认证程序", "生产流程")):
        if "没有发生变化" in compact or not any(term in compact for term in progress + ("竞争优势", "财务", "利润", "毛利率")):
            return "routine_process"
    if any(term in compact for term in ("供应商认证", "客户认证", "供应商选择", "采购控制程序", "产品代码")) and not any(term in compact for term in progress):
        return "routine_process"

    spec_tokens = re.findall(r"(?:IEEE|MSA|QSFP|OSFP|CMIS|\b\d+(?:\.\d+)?[GMTK]?\b)", segment)
    if len(spec_tokens) >= 3 and not any(term in compact for term in progress + ("客户", "应用", "技术路线")):
        return "catalog_without_business_value"

    generic_industry = ("预测", "市场规模", "年均复合", "行业发展", "技术门槛", "技术壁垒", "全球市场", "全球宏观经济", "中国半导体", "海关总署", "国内互联网厂商", "国内芯片设计企业", "中国企业")
    if (role == "market_competition_outlook" or any(term in compact for term in generic_industry)) and not any(term in compact for term in linked):
        return "generic_industry_context"

    terms = {
        "business_structure": ("公司", "主营", "主要业务", "产品", "客户", "应用", "服务于", "从事", "平台", "增长"),
        "operating_progress": progress,
        "market_competition_outlook": ("公司", "管理层", "竞争", "战略", "需求", "行业地位", "市场份额", "产品", "应用"),
        "technology_product_progress": ("研发", "推出", "发布", "量产", "验证", "技术", "平台", "产品", "投入", "迭代"),
        "financial_quality_explanation": ("收入", "营收", "利润", "毛利率", "费用", "现金流", "存货", "主要系", "变化原因", "所致"),
    }.get(str(role or ""), linked + ("收入", "营收", "利润", "毛利率", "费用", "现金流", "存货"))
    return "" if any(term in compact for term in terms) else "role_mismatch"


def _dedupe_annual_display_rows(
    rows: Iterable[MaterialRow],
) -> tuple[Tuple[MaterialRow, ...], int, Dict[str, int]]:
    kept = []
    reasons: Dict[str, int] = {}
    for row in rows:
        body_key = re.sub(r"\s+", "", row.body).strip("。；;")
        for index, previous in enumerate(kept):
            previous_key = re.sub(r"\s+", "", previous.body).strip("。；;")
            if not body_key or not (body_key == previous_key or (previous.render_role == row.render_role and (body_key in previous_key or previous_key in body_key))):
                continue
            reason = "duplicate_exact" if body_key == previous_key else "duplicate_contained"
            reasons[reason] = reasons.get(reason, 0) + 1
            if len(body_key) > len(previous_key):
                kept[index] = row
            break
        else:
            kept.append(row)
    return tuple(kept), sum(reasons.values()), reasons


def build_chapter4_view_model(
    snapshot: MaterialSnapshot,
    profile: Mapping[str, Any] | str,
) -> Chapter4ViewModel:
    """Admit normalized rows into the formal-medium Chapter 4 layout."""
    profile_name = profile if isinstance(profile, str) else str((profile or {}).get("profile") or "")
    if profile_name != "formal_medium":
        raise ValueError(f"Chapter4ViewModel V1 only supports formal_medium, got {profile_name!r}")

    usable_rows = tuple(row for row in snapshot.rows if row.text and row.citation_refs)
    annual_rows, annual_selection_diagnostics = select_annual_display_rows(usable_rows)
    broker_rows = tuple(row for row in usable_rows if row.source_layer == "broker" and row.attribution)
    external_rows = tuple(
        _dedupe_row_refs_by_citation_identity(row, snapshot.citations)
        for row in usable_rows
        if row.source_layer == "external"
        and not row.scoring_eligible
        and not row.risk_score_eligible
    )
    complete_annual_rows = tuple(row for row in annual_rows if row.argument_complete)
    annual_roles = (
            "business_structure",
            "operating_progress",
            "market_competition_outlook",
            "technology_product_progress",
            "financial_quality_explanation",
        )
    annual_price_row = _first_row_by_role(complete_annual_rows, annual_roles, fallback=False)
    annual_price_row = annual_price_row or _first_row_by_role(annual_rows, annual_roles, fallback=False)
    price_path_rows = tuple(
        row for row in (
            annual_price_row,
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
    diagnostics.update(annual_selection_diagnostics,
                       profile=profile_name,
                       visible_rows_count=sum(len(section.rows) for section in sections[:3]),
                       visible_citation_count=len(citations))
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


def _first_row_by_role(
    rows: Iterable[MaterialRow],
    roles: Iterable[str],
    *,
    fallback: bool = True,
) -> MaterialRow | None:
    row_list = tuple(rows)
    match = next((row for role in roles for row in row_list if row.render_role == role), None)
    return match or (row_list[0] if fallback and row_list else None)


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
