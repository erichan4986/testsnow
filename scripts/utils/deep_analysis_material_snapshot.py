"""Deep-analysis-only MaterialSnapshot read-model.

This module projects existing chapter-4 material fields into a deterministic
read model. It does not mutate ``ctx`` and must not feed executive summary,
scoring, risk, target price, or recommendation paths.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Dict, Iterable, Mapping, Tuple

try:
    from .external_evidence import external_family_title
    from .deep_analysis_topic_ownership import matching_topic_families
    from .synthesis_credit import citation_identity
except ImportError:
    from external_evidence import external_family_title
    from deep_analysis_topic_ownership import matching_topic_families
    from synthesis_credit import citation_identity


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
    editorial_slot: str = ""
    external_claim: str = ""
    external_evidence: str = ""
    evidence_status: str = ""
    entity_scope: str = ""
    owner_relation: str = ""
    argument_key: str = ""
    diagnostics: Tuple[Tuple[str, str], ...] = ()
    external_family: str = ""
    external_unit_ids: Tuple[str, ...] = ()

@dataclass(frozen=True)
class ExternalNarrativePart:
    argument_key: str
    unit_id: str
    quote: str
    relation: str
    citation_refs: Tuple[int, ...]


@dataclass(frozen=True)
class ExternalTopicNarrative:
    scope_bucket: str
    primary_family: str
    parts: Tuple[ExternalNarrativePart, ...]


@dataclass(frozen=True)
class MaterialSnapshot:
    schema: str
    rows: Tuple[MaterialRow, ...]
    citations: Dict[int, Dict[str, Any]]
    diagnostics: Dict[str, Any]
    external_topic_narratives: Tuple[ExternalTopicNarrative, ...] = ()


@dataclass(frozen=True)
class Chapter4Section:
    section_id: str
    title: str
    rows: Tuple[MaterialRow, ...]
    disclaimer: str = ""
    narratives: Tuple[ExternalTopicNarrative, ...] = ()


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
    display = ctx.get("deep_analysis_display") or {}
    rows = [
        *_annual_rows(ctx.get("annual_report_memo") or {}, allocator),
        *_broker_rows(ctx.get("broker_research_memo") or {}, allocator),
        *_external_rows(display, allocator, profile),
    ]
    return MaterialSnapshot(
        schema=SCHEMA,
        rows=tuple(rows),
        citations=allocator.citations,
        diagnostics=_diagnostics(ctx, rows),
        external_topic_narratives=_external_narratives(display, allocator),
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
    editorial_rows, hidden_by_role = _select_annual_editorial_rows(deduped)
    return editorial_rows, {
        "annual_candidates_count": len(candidates),
        "annual_selected_count": len(deduped),
        "annual_rejected_by_reason": rejected,
        "annual_deduped_count": deduped_count,
        "annual_display_count": len(editorial_rows),
        "annual_hidden_count": len(deduped) - len(editorial_rows),
        "annual_hidden_by_role": hidden_by_role,
    }


_ANNUAL_ROLE_BUDGETS = {
    "business_structure": 3,
    "operating_progress": 2,
    "market_competition_outlook": 1,
    "technology_product_progress": 2,
    "financial_quality_explanation": 3,
}
_ANNUAL_ROLE_ORDER = tuple(_ANNUAL_ROLE_BUDGETS)
_PORTRAIT_ROLES = ("business_structure", "operating_progress", "technology_product_progress")
_EVIDENCE_SIGNAL_TERMS = (
    "主要系", "所致", "同比", "环比", "报告期内", "客户", "订单", "量产", "导入",
    "推出", "发布", "验证", "研发", "收入", "营收", "利润", "毛利率", "现金流",
)


def _select_annual_editorial_rows(rows: Iterable[MaterialRow]) -> tuple[Tuple[MaterialRow, ...], Dict[str, int]]:
    row_list = tuple(rows)
    portrait = _select_annual_portrait(row_list)
    selected_ids = {portrait.row_id} if portrait else set()
    selected = [replace(portrait, editorial_slot="portrait")] if portrait else []
    hidden_by_role: Dict[str, int] = {}
    for role in _ANNUAL_ROLE_ORDER:
        ranked = _rank_annual_rows(row for row in row_list if row.render_role == role)
        visible = [row for row in ranked if row.row_id not in selected_ids][:_ANNUAL_ROLE_BUDGETS[role] - int(portrait is not None and portrait.render_role == role)]
        selected.extend(visible)
        selected_ids.update(row.row_id for row in visible)
        hidden = len(ranked) - len(visible) - int(portrait is not None and portrait.render_role == role)
        if hidden > 0:
            hidden_by_role[role] = hidden
    return tuple(selected), hidden_by_role


def _select_annual_portrait(rows: Iterable[MaterialRow]) -> MaterialRow | None:
    candidates = [row for row in rows if row.render_role in _PORTRAIT_ROLES and _is_portrait_candidate(row.body)]
    if not candidates:
        return None
    return max(candidates, key=lambda row: _portrait_score(row.body))


def _is_portrait_candidate(body: str) -> bool:
    compact = re.sub(r"\s+", "", body)
    has_scope = bool(re.search(r"(?:主营业务|主要业务|增长主线|是一家从事|公司.{0,12}(?:从事|建立|开发)|报告期内，公司)", compact))
    complete = bool(re.search(r"[。！？；;]$", compact) or re.search(r"(?:客户|市场|领域|需求|解决方案|产品线|业务)$", compact))
    return has_scope and complete


def _portrait_score(body: str) -> int:
    compact = re.sub(r"\s+", "", body)
    weighted = {"主营业务": 5, "从事": 4, "公司": 3, "产品线": 2, "客户": 2, "应用": 2, "行业": 2, "市场": 2}
    score = sum(weight for term, weight in weighted.items() if term in compact)
    score += min(5, sum(term in compact for term in ("设计", "开发", "研发", "制造", "生产", "测试", "系统解决方案")))
    return score - (3 if "介绍" in compact and len(compact) < 60 else 0)


def _rank_annual_rows(rows: Iterable[MaterialRow]) -> list[MaterialRow]:
    return [row for _, row in sorted(enumerate(rows), key=lambda pair: (
        -int(pair[1].argument_complete),
        -int(bool(pair[1].citation_refs)),
        -_annual_evidence_signal_score(pair[1].body),
        _annual_length_penalty(pair[1].body),
        pair[0],
    ))]


def _annual_evidence_signal_score(body: str) -> int:
    compact = re.sub(r"\s+", "", body)
    return sum(term in compact for term in _EVIDENCE_SIGNAL_TERMS) + int(bool(re.search(r"\d", compact)))


def _annual_length_penalty(body: str) -> int:
    length = len(re.sub(r"\s+", "", body))
    return 0 if 24 <= length <= 320 else abs(min(max(length, 24), 320) - length)


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
    broker_rows = _select_broker_display_rows(usable_rows)
    external_rows, external_selection_diagnostics = select_incremental_external_display_rows(
        usable_rows,
        snapshot.citations,
        (*annual_rows, *broker_rows),
    )
    external_narratives = select_external_topic_narratives(
        snapshot.external_topic_narratives, external_rows,
    )
    price_path_rows = _select_price_path_rows(annual_rows, broker_rows, external_rows)
    sections = (
        Chapter4Section("4.1", "官方材料确认：业务与财务基座", annual_rows),
        Chapter4Section("4.2", "机构观点与盈利假设", broker_rows),
        Chapter4Section(
            "4.3",
            "外部观察与待验证变量（Preview，不参与评分）",
            external_rows,
            "以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或目标价。",
            external_narratives,
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
    } | {ref for narrative in external_narratives for part in narrative.parts for ref in part.citation_refs})
    citations = {
        ref: dict(snapshot.citations.get(ref) or {})
        for ref in visible_refs
        if ref in snapshot.citations
    }
    diagnostics = dict(snapshot.diagnostics)
    diagnostics.update(annual_selection_diagnostics,
                       **external_selection_diagnostics,
                       profile=profile_name,
                       visible_rows_count=sum(len(section.rows) for section in sections[:3]),
                       visible_citation_count=len(citations))
    return Chapter4ViewModel(profile_name, sections, citations, diagnostics)


def _select_broker_display_rows(rows: Iterable[MaterialRow]) -> Tuple[MaterialRow, ...]:
    candidates = _dedupe_exact_body(row for row in rows if row.source_layer == "broker" and row.attribution)
    non_risk = [row for row in candidates if row.render_role != "broker_risk"]
    risk = [row for row in candidates if row.render_role == "broker_risk"]
    selected = []
    seen_attribution = set()
    for row in non_risk:
        if row.attribution in seen_attribution:
            continue
        selected.append(row)
        seen_attribution.add(row.attribution)
        if len(selected) == 5:
            break
    if len(selected) < 5:
        selected.extend(row for row in non_risk if row not in selected)
    return tuple(selected[:5] + risk[:2])


def _dedupe_exact_body(rows: Iterable[MaterialRow]) -> list[MaterialRow]:
    seen = set()
    selected = []
    for row in rows:
        key = re.sub(r"\s+", "", row.body).strip("。；;")
        if not key or key in seen:
            continue
        seen.add(key)
        selected.append(row)
    return selected


_EXTERNAL_ATTRIBUTION_RE = re.compile(r"^(?:外部材料|外部文章|外部信息|外部观点|文章|材料)(?:称|认为|指出|显示|提示|讨论)?[：:,，\s]*")
_CONCRETE_ANCHOR_RE = re.compile(
    r"(?i:20\d{2}(?:Q[1-4])?|\d+(?:\.\d+)?(?:%|个百分点|亿元|万元|万|亿|元|倍|万片|万只|万台|台|片|套|项|家|个月|月|年)|[A-Z]+\d+(?:\.\d+)?|\d+(?:\.\d+)?[A-Z]+)|(?<![A-Z])[A-Z]{2,8}(?![A-Z])"
)
_EXTERNAL_EVENT_TERMS = (
    "传言", "否认", "回应", "下调", "上调", "短缺", "紧张", "瓶颈", "缺口", "供应链", "交付", "订单",
    "认证", "验证", "量产", "制裁", "政策", "停产", "延期", "延后", "提前", "调整", "替代", "降价", "涨价", "分歧", "唯一", "首家", "率先",
)


def select_incremental_external_display_rows(
    rows: Iterable[MaterialRow],
    citations: Mapping[int, Any],
    owner_rows: Iterable[MaterialRow],
) -> tuple[Tuple[MaterialRow, ...], Dict[str, Any]]:
    """Select external rows that add a visible, testable variable to owner rows."""
    candidates = [
        _dedupe_row_refs_by_citation_identity(row, citations)
        for row in rows
        if row.source_layer == "external" and _is_external_display_eligible(row, citations)
    ]
    owners = tuple(row for row in owner_rows if row.body)
    rejected: Dict[str, int] = {}
    selected = []
    for row in _dedupe_external_display_rows(candidates, citations):
        reason = _external_incremental_reason(row, owners)
        if not reason:
            rejected["owner_theme_without_delta"] = rejected.get("owner_theme_without_delta", 0) + 1
            continue
        if reason == "owner_text_duplicate":
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        selected.append(replace(
            row,
            owner_relation="outside_owner" if reason == "new_topic_context" else "owner_delta",
            diagnostics=(*row.diagnostics, ("external_incremental_reason", reason)),
        ))
    return tuple(selected), _external_selection_diagnostics(candidates, selected, rejected)


def _external_selection_diagnostics(candidates, selected, rejected) -> Dict[str, Any]:
    return {
        "external_incremental_candidates_count": len(candidates),
        "external_incremental_selected_count": len(selected),
        "external_incremental_rejected_by_reason": dict(rejected),
    }


def _external_incremental_reason(row: MaterialRow, owners: Tuple[MaterialRow, ...]) -> str:
    external_body = _normalized_claim_body(row.external_claim or row.body)
    owner_bodies = tuple(_normalized_claim_body(owner.body) for owner in owners)
    if any(
        external_body == owner_body
        or (len(external_body) >= 24 and external_body in owner_body)
        for owner_body in owner_bodies
        if owner_body
    ):
        return "owner_text_duplicate"

    external_families = _topic_family_names(row.external_claim or row.body)
    external_anchors = _concrete_anchors(row.external_claim or row.body)
    comparable = tuple(
        owner for owner in owners
        if external_families & _topic_family_names(owner.body)
        or external_anchors & _concrete_anchors(owner.body)
    )
    if not comparable:
        return "new_topic_context"
    owner_anchors = set().union(*(_concrete_anchors(owner.body) for owner in comparable))
    if external_anchors - owner_anchors:
        return "new_concrete_anchor"
    owner_event_text = "".join(_normalized_claim_body(owner.body) for owner in comparable)
    if any(term in external_body and term not in owner_event_text for term in _EXTERNAL_EVENT_TERMS):
        return "new_event_variable"
    return ""


def _normalized_claim_body(text: str) -> str:
    body = re.sub(r"\[\^\d+\]", "", str(text or "").strip())
    body = _EXTERNAL_ATTRIBUTION_RE.sub("", body)
    return re.sub(r"\s+", "", body).strip("。；;，,：:！!？?").lower()


def _topic_family_names(text: str) -> set[str]:
    return {str(family.get("family")) for family in matching_topic_families(text or "")}


def _concrete_anchors(text: str) -> set[str]:
    return {
        re.sub(r"\s+", "", match.group(0)).lower()
        for match in _CONCRETE_ANCHOR_RE.finditer(str(text or ""))
    }


def _is_external_display_eligible(row: MaterialRow, citations: Mapping[int, Any]) -> bool:
    return bool(row.body and row.citation_refs and not row.scoring_eligible and not row.risk_score_eligible and any(citations.get(ref) for ref in row.citation_refs))


def external_display_key(row: MaterialRow, citations: Mapping[int, Any]) -> tuple:
    if row.argument_key:
        return ("argument", row.argument_key)
    return (
        re.sub(r"\s+", "", row.body).strip("。；;"),
        tuple(sorted({citation_identity(citations.get(ref), fallback_ref=ref) for ref in row.citation_refs})),
    )


def _dedupe_external_display_rows(rows: Iterable[MaterialRow], citations: Mapping[int, Any]) -> list[MaterialRow]:
    seen = set()
    selected = []
    for row in rows:
        key = external_display_key(row, citations)
        if not key[0] or key in seen:
            continue
        seen.add(key)
        selected.append(row)
    return selected


_NON_INFORMATIVE_VARIABLE_TITLES = {
    "", "外部变量", "外部观察", "主营业务与产品", "产业与产品判断", "机构核心观点", "券商核心观点", "盈利预测", "盈利预测与估值假设", "反方约束", "反方风险", "风险提示", "业务覆盖 / 产品线", "经营变化", "市场与竞争", "管理层判断与行业展望", "研发与产品进展", "技术与产品进展", "财务质量", "财务质量与变化原因", "产品放量 / 盈利弹性", "供应链 / 技术路线",
}

def is_informative_variable_title(title: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(title or "")).strip(" ：:，,；;。")
    return normalized not in _NON_INFORMATIVE_VARIABLE_TITLES


def _select_price_path_rows(
    annual_rows: Iterable[MaterialRow],
    broker_rows: Iterable[MaterialRow],
    external_rows: Iterable[MaterialRow],
) -> Tuple[MaterialRow, ...]:
    annual = _select_price_row(annual_rows, ("operating_progress", "financial_quality_explanation", "technology_product_progress", "market_competition_outlook", "business_structure"), exclude_portrait=True)
    broker = _select_price_row(broker_rows, ("broker_assumption", "broker_forecast"))
    if broker is None:
        broker = _generic_broker_price_row(broker_rows)
    external = next((row for row in external_rows if is_informative_variable_title(row.title)), None)
    return tuple(row for row in (annual, broker, external) if row is not None)


def _select_price_row(rows: Iterable[MaterialRow], roles: Iterable[str], *, exclude_portrait: bool = False) -> MaterialRow | None:
    filtered = [row for row in rows if is_informative_variable_title(row.title) and not (exclude_portrait and row.editorial_slot == "portrait")]
    for role in roles:
        matches = [row for row in filtered if row.render_role == role]
        complete = next((row for row in matches if row.argument_complete), None)
        if complete or matches:
            return complete or matches[0]
    return None


def _generic_broker_price_row(rows: Iterable[MaterialRow]) -> MaterialRow | None:
    eligible = tuple(row for row in rows if row.body and row.citation_refs)
    row = next((row for role in ("broker_assumption", "broker_forecast") for row in eligible if row.render_role == role), None)
    if row is None:
        return None
    attribution = row.attribution if row.attribution and row.attribution != "研报" else ""
    return replace(row, title=f"{attribution}研报核心假设")


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
                render_role=_annual_render_role(section, row),
                argument_complete=bool(row.get("argument_complete", False)),
                source_credit="official",
            ))
    return result


def _annual_render_role(section: str, row: Mapping[str, Any]) -> str:
    role = str(row.get("argument_family") or row.get("display_group") or "").strip()
    if role:
        return role
    text = f"{row.get('title') or ''}{row.get('body') or ''}"
    if any(term in text for term in ("主营", "产品", "客户", "应用", "业务")):
        return "business_structure"
    if section == "confirmed" or any(term in text for term in ("收入", "营收", "利润", "毛利率", "现金流", "费用", "存货")):
        return "financial_quality_explanation"
    return "operating_progress"


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
    cards = sorted(
        display.get("_curated_external_argument_cards") or [],
        key=lambda row: isinstance(row, Mapping) and str(row.get("entity_scope") or "") == "peer_or_industry",
    )
    for idx, row in enumerate(cards):
        if not isinstance(row, dict):
            continue
        evidence_units = [unit for unit in row.get("evidence_units") or [] if isinstance(unit, Mapping)]
        body = "\n\n".join(str(unit.get("text") or "").strip() for unit in evidence_units if str(unit.get("text") or "").strip())
        if not body:
            continue
        material_row = _adapt_material_row(
            row,
            allocator,
            citations,
            f"external:argument_cards:{idx}",
            source_layer="external",
            claim_status="external_observation",
            section_hint=section_hint,
            title=external_family_title(row.get("primary_family")),
            body=body,
            render_role="external_variable",
            source_credit="external_low_credit",
        )
        result.append(replace(
            material_row,
            external_claim=body,
            external_evidence=body,
            evidence_status=str((evidence_units[0] if evidence_units else {}).get("evidence_status") or "source_unit_verified"),
            entity_scope=str(row.get("entity_scope") or ""),
            argument_key=str(row.get("argument_key") or ""),
            external_family=str(row.get("primary_family") or ""),
            external_unit_ids=tuple(str(unit.get("unit_id") or "") for unit in evidence_units),
        ))
    return result


def _external_narratives(display: Mapping[str, Any], allocator: _CitationAllocator) -> Tuple[ExternalTopicNarrative, ...]:
    citations = display.get("citations") or {}
    units = _external_units_by_key(display.get("_curated_external_argument_cards") or [])
    narratives = []
    for group in display.get("_curated_external_topic_narratives") or []:
        if not isinstance(group, Mapping):
            continue
        parts = []
        for part in group.get("parts") or []:
            key = _external_unit_key(part.get("argument_key"), part.get("unit_id"))
            unit = units.get(key)
            if unit:
                parts.append(ExternalNarrativePart(
                    *key, str(part.get("quote") or ""), str(part.get("relation") or ""),
                    allocator.map_refs(unit.get("citation_refs") or (), citations),
                ))
        if parts:
            narratives.append(ExternalTopicNarrative(
                str(group.get("scope_bucket") or ""), str(group.get("primary_family") or ""), tuple(parts),
            ))
    return tuple(narratives)


def select_external_topic_narratives(
    narratives: Iterable[ExternalTopicNarrative], rows: Iterable[MaterialRow],
) -> Tuple[ExternalTopicNarrative, ...]:
    selected = tuple(rows)
    result = []
    for narrative in narratives:
        scoped = tuple(row for row in selected if (
            _external_scope_bucket(row.entity_scope) == narrative.scope_bucket
            and row.external_family == narrative.primary_family
        ))
        expected = [(row.argument_key, unit_id) for row in scoped for unit_id in row.external_unit_ids]
        keys = {row.argument_key for row in scoped}
        parts = tuple(part for part in narrative.parts if part.argument_key in keys)
        if expected and [(part.argument_key, part.unit_id) for part in parts] == expected:
            result.append(replace(narrative, parts=(replace(parts[0], relation="first"), *parts[1:])))
    return tuple(result)


def _external_scope_bucket(entity_scope: object) -> str:
    return "peer_or_industry" if entity_scope == "peer_or_industry" else "target"


def _external_unit_key(argument_key: object, unit_id: object) -> tuple[str, str]:
    return str(argument_key or "").strip(), str(unit_id or "").strip()


def _external_units_by_key(cards: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        _external_unit_key(card.get("argument_key"), unit.get("unit_id")): unit
        for card in cards
        if isinstance(card, Mapping)
        for unit in card.get("evidence_units") or []
        if isinstance(unit, Mapping)
    }


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
