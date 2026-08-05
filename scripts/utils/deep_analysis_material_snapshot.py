"""Deep-analysis-only MaterialSnapshot read-model.

This module projects existing chapter-4 material fields into a deterministic
read model. It does not mutate ``ctx`` and must not feed executive summary,
scoring, risk, target price, or recommendation paths.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from difflib import SequenceMatcher
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
    "operating_progress": 4,
    "market_competition_outlook": 3,
    "technology_product_progress": 3,
    "financial_quality_explanation": 6,
}
_ANNUAL_ROLE_ORDER = tuple(_ANNUAL_ROLE_BUDGETS)
_PORTRAIT_ROLES = ("business_structure", "operating_progress", "technology_product_progress")
_EVIDENCE_SIGNAL_TERMS = (
    "主要系", "所致", "同比", "环比", "报告期内", "客户", "订单", "量产", "导入",
    "推出", "发布", "验证", "交付", "研发", "收入", "营收", "利润", "毛利率", "现金流",
)
_ANNUAL_FINANCIAL_METRIC_TERMS = (
    "收入", "营收", "營收", "利润", "利潤", "亏损", "虧損", "毛利", "毛利率",
    "费用", "費用", "销售成本", "銷售成本", "现金流", "現金流", "存货", "存貨",
    "减值", "減值", "应收", "應收", "负债", "負債", "借款",
)
_ANNUAL_FINANCIAL_QUALITY_TERMS = (
    "现金流", "現金流", "存货", "存貨", "减值", "減值", "应收", "應收",
    "负债", "負債", "借款", "汇兑", "匯兌", "研发费用", "研發開支", "无形资产", "無形資產",
)
_ANNUAL_FINANCIAL_EXPLANATION_TERMS = (
    "主要系", "所致", "导致", "導致", "变动原因", "變動原因", "变化原因", "變化原因",
    "得益于", "得益於", "受益于", "受益於", "随着", "隨著", "由于上述原因", "由於上述原因",
)
_FINANCIAL_FACT_ALIASES = (
    ("operating_cash_flow", ("经营活动产生的现金流量净额", "经营现金流量净额", "经营现金流", "經營活動所用現金淨額", "經營現金流")),
    ("net_profit", ("归属于上市公司股东的净利润", "归属于上市公司股东净利润", "归母净利润", "本公司權益持有人應佔年內", "年內虧損")),
    ("revenue", ("营业收入", "營業收入", "营收", "營收")),
    ("gross_margin", ("毛利率",)),
)
_ANNUAL_BUSINESS_HEADING_RE = re.compile(
    r"^(?:[一二三四五六七八九十]+[、.]\s*)?报告期内公司所从事的主要业务、经营模式、行业情况说明\s*"
    r"(?:\([一二三四五六七八九十\d]+\)\s*)?(?:主要业务、主要产品或服务情况\s*)?"
    r"(?:\d+[、.]\s*主要业务\s*)?"
)


def _select_annual_editorial_rows(rows: Iterable[MaterialRow]) -> tuple[Tuple[MaterialRow, ...], Dict[str, int]]:
    row_list = tuple(rows)
    portrait = _select_annual_portrait(row_list)
    selected_ids = {portrait.row_id} if portrait else set()
    selected = [replace(portrait, editorial_slot="portrait")] if portrait else []
    hidden_by_role: Dict[str, int] = {}
    for role in _ANNUAL_ROLE_ORDER:
        ranked = _rank_annual_rows(row for row in row_list if row.render_role == role)
        budget = _ANNUAL_ROLE_BUDGETS[role] - int(portrait is not None and portrait.render_role == role)
        available = [row for row in ranked if row.row_id not in selected_ids]
        visible = (
            _select_financial_editorial_rows(available, budget)
            if role == "financial_quality_explanation"
            else available[:budget]
        )
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
    has_scope = bool(re.search(
        r"(?:主营业务|主要业务|增长主线|是一家从事|公司.{0,12}(?:从事|建立|开发)|报告期内，公司|本公司.{0,30}(?:平台|供應商|供应商|業務|业务))",
        compact,
    )) or any(term in compact for term in ("双主业", "雙主業", "双引擎", "雙引擎"))
    complete = bool(
        re.search(r"[。！？；;]$", compact)
        or re.search(r"(?:客户|市场|领域|需求|解决方案|产品线|业务|公司|供应商|供應商|格局)$", compact)
        or re.search(r"完成.{0,8}[从從].{0,50}(?:供应商|供應商)", compact)
    )
    return has_scope and complete


def _portrait_score(body: str) -> int:
    compact = re.sub(r"\s+", "", body)
    weighted = {"主营业务": 5, "从事": 4, "公司": 3, "产品线": 2, "客户": 2, "应用": 2, "行业": 2, "市场": 2}
    score = sum(weight for term, weight in weighted.items() if term in compact)
    score += min(5, sum(term in compact for term in ("设计", "开发", "研发", "制造", "生产", "测试", "系统解决方案")))
    score += 12 * int("是一家从事" in compact or bool(re.search(r"完成.{0,8}[从從].{0,50}(?:供应商|供應商)", compact)))
    score += 14 * int(any(term in compact for term in ("双主业", "雙主業", "双引擎", "雙引擎")))
    return score - (3 if "介绍" in compact and len(compact) < 60 else 0)


def _rank_annual_rows(rows: Iterable[MaterialRow]) -> list[MaterialRow]:
    return [row for _, row in sorted(enumerate(rows), key=lambda pair: (
        -_annual_editorial_score(pair[1]),
        _annual_length_penalty(pair[1].body),
        pair[0],
    ))]


def _annual_editorial_score(row: MaterialRow) -> int:
    compact = re.sub(r"\s+", "", row.body)
    score = 2 * _annual_evidence_signal_score(compact)
    score += 2 * int(row.argument_complete) + int(bool(row.citation_refs))
    score += 3 * int(bool(re.search(r"\d", compact)))
    score += 2 * sum(term in compact for term in (
        "定点", "批量", "出货", "交付", "订单", "客户", "量产", "验证", "导入", "合作", "收入", "营收", "毛利率", "同比", "环比",
    ))
    score += 2 * int(bool(re.search(r"(?:[A-Za-z]+\d+|\d+(?:\.\d+)?[GT])", compact)))
    score += 3 * int(any(term in compact for term in ("长期稳定的合作关系", "市场份额持续", "市场份额的持续")))
    generic_plan = any(term in compact for term in ("持续关注", "提升核心竞争力", "稳步推进", "把握发展机遇"))
    concrete = bool(re.search(r"\d", compact)) or any(term in compact for term in ("客户", "订单", "定点", "量产", "出货", "收入", "利润", "毛利率"))
    return score - 8 * int(generic_plan and not concrete)


def _annual_evidence_signal_score(body: str) -> int:
    compact = re.sub(r"\s+", "", body)
    return sum(term in compact for term in _EVIDENCE_SIGNAL_TERMS) + int(bool(re.search(r"\d", compact)))


def _annual_length_penalty(body: str) -> int:
    length = len(re.sub(r"\s+", "", body))
    return 0 if 24 <= length <= 320 else abs(min(max(length, 24), 320) - length)


def _financial_dimensions(body: str) -> tuple[str, ...]:
    compact = re.sub(r"\s+", "", body)
    dimensions = []
    if re.search(r"\d", compact) and any(term in compact for term in _ANNUAL_FINANCIAL_METRIC_TERMS) and any(term in compact for term in ("同比", "环比", "增长", "增長", "下降", "增加", "减少", "減少")):
        dimensions.append("performance")
    if any(term in compact for term in _ANNUAL_FINANCIAL_QUALITY_TERMS):
        dimensions.append("quality")
    if any(term in compact for term in _ANNUAL_FINANCIAL_EXPLANATION_TERMS) and any(term in compact for term in ("需求", "销售", "銷售", "价格", "價格", "客户", "客戶", "产品结构", "產品結構", "规模", "規模", "汇率", "匯率", "补助", "補助", "税收", "稅收", "研发项目", "研發項目", "原材料", "无形资产", "無形資產", "减值", "減值")):
        dimensions.append("driver")
    return tuple(dimensions)


def _financial_insight_score(row: MaterialRow) -> int:
    compact = re.sub(r"\s+", "", row.body)
    score = 4 * len(_financial_dimensions(compact)) + 2 * int(bool(re.search(r"\d", compact)))
    score += 10 if any(term in compact for term in ("归母净利润", "归属于上市公司股东的净利润", "归属于上市公司股东净利润", "本公司權益持有人應佔年內")) else 5 if any(term in compact for term in ("利润", "利潤", "亏损", "虧損", "毛利")) else 0
    score += min(3, sum(any(alias in compact for alias in aliases) for _, aliases in _FINANCIAL_FACT_ALIASES))
    score += 4 if any(term in compact for term in _ANNUAL_FINANCIAL_QUALITY_TERMS) else 0
    score += int(
        any(term in compact for term in ("减值", "減值"))
        and any(term in compact for term in ("销售未达预期", "銷售未達預期", "需求结构变化", "需求結構變化", "未达到预期收益", "未達到預期收益"))
    )
    score += int(bool(re.search(r"\d", compact)) and any(term in compact for term in ("减值损失", "減值損失")))
    mechanical = (
        "营业成本变动原因说明" in compact and "营业收入增加" in compact
    ) or (
        "现金流量净额变动原因说明" in compact and not re.search(r"\d", compact)
    )
    return score + int(row.argument_complete) - 8 * int(mechanical)


def _select_financial_editorial_rows(rows: Iterable[MaterialRow], budget: int) -> list[MaterialRow]:
    row_list = list(rows)
    core_facts = [row for row in row_list if row.claim_status == "formal_fact" and _core_financial_metric(row)]
    overview = None
    if len(core_facts) >= 2:
        row_list = [row for row in row_list if row not in core_facts]
        overview = _merge_core_financial_facts(core_facts)
    ranked = sorted(
        (row for row in row_list if _financial_insight_score(row) >= 0),
        key=_financial_insight_score,
        reverse=True,
    )
    selected = [overview] if overview is not None else []
    for dimension in ("performance", "quality", "driver"):
        row = next((item for item in ranked if item not in selected and dimension in _financial_dimensions(item.body)), None)
        if row is not None:
            selected.append(row)
        if len(selected) == budget:
            return selected
    selected.extend(row for row in ranked if row not in selected)
    return selected[:budget]


def _core_financial_metric(row: MaterialRow) -> str:
    text = f"{row.title}{row.body}"
    return next((metric for metric in ("营业收入", "归母净利润", "经营现金流量净额") if metric in text), "")


def _merge_core_financial_facts(rows: Iterable[MaterialRow]) -> MaterialRow:
    order = ("营业收入", "归母净利润", "经营现金流量净额")
    by_metric = {_core_financial_metric(row): row for row in rows}
    first = next(by_metric[metric] for metric in order if metric in by_metric)
    parts = []
    refs = []
    source_refs = []
    for metric in order:
        row = by_metric.get(metric)
        if row is None:
            continue
        value = re.sub(rf"^(?:{re.escape(metric)})?[：:]?", "", re.sub(r"\s+", "", row.body))
        parts.append(f"{metric}{value}")
        refs.extend(ref for ref in row.citation_refs if ref not in refs)
        source_refs.extend(ref for ref in row.source_ref_ids if ref not in source_refs)
    body = "；".join(parts) + "。"
    return replace(
        first,
        row_id="annual:core-financial-overview",
        title="核心财务指标",
        body=body,
        text=f"核心财务指标：{body}",
        citation_refs=tuple(refs),
        source_ref_ids=tuple(source_refs),
    )


def _project_annual_display_row(row: MaterialRow) -> tuple[MaterialRow | None, str]:
    if not row.body or not row.citation_refs:
        return None, "empty"
    if (
        row.claim_status == "formal_fact"
        and "0.00亿元" in row.body
        and any(term in row.title for term in ("营收", "营业收入", "收入", "利润", "净利润", "现金流"))
    ):
        return None, "suspicious_zero_financial_fact"
    kept = []
    reasons = []
    for segment in re.split(r"(?<=[。！？；;])", row.body):
        segment = _ANNUAL_BUSINESS_HEADING_RE.sub("", segment).strip()
        segment = re.sub(
            r"^\d+\s+\d{4}\s*年年度報告.{0,60}?管理層討論及分析\s*（續）\s*",
            "",
            segment,
        )
        segment = re.sub(r"^毛利及毛利率\s*(?=由於|由于)", "", segment)
        segment = re.sub(r"^(?:由於|由于)上述原因[，,]?", "", segment)
        segment = re.sub(r"^（\d+）[^，。；]{1,20}(?=公司)", "", segment)
        segment = re.sub(r"^(.{2,20}?(?:解决方案|解決方案))\1", r"\1", segment)
        segment = re.sub(
            r"^(.{2,20}?(?:解决方案|解決方案))(?=(?:我们|我們)的\1)",
            "",
            segment,
        )
        segment = re.sub(r"^(?:\d+[、.]\s*(?:主要业务|主要产品及服务情况)\s*|\d+(?:\.\d+)+\s*[^，。；;\d]{1,20}\s+(?=\S)|（?[^）]{1,20}）?芯片\s*\d+[、.]\s*|(?:报告期内公司从事的主要业务)?公司需遵守《[^》]+》[^。；，,]*披露要求[，,]*(?=公司(?:主营|主要业务|产品)))", "", segment)
        segment = re.sub(r"^并(?=在业界.{0,20}(?:推出|发布|量产))", "", segment)
        segment = _strip_annual_self_comparison(segment)
        if not segment:
            reasons.append("disclosure_or_governance")
            continue
        routine_marker = next((term for term in ("采购模式", "生产模式", "经营模式", "销售模式", "代理销售", "认证程序", "生产流程") if term in segment), None)
        if routine_marker:
            prefix = segment.split(routine_marker, 1)[0].strip(" ，,；;。")
            if prefix and any(term in prefix for term in ("主营业务", "产品", "客户", "设备", "服务", "研发")):
                segment = prefix
        admission_role = _annual_display_role(row.render_role, segment)
        if admission_role != "financial_quality_explanation" and row.render_role != "financial_quality_explanation":
            admission_role = row.render_role
        reason = _annual_segment_rejection_reason(segment, admission_role)
        compact_segment = re.sub(r"\s+", "", segment)
        is_titled_financial_fact = (
            row.claim_status == "formal_fact"
            and any(term in row.title for term in ("收入", "营收", "利润", "毛利率", "费用", "现金流", "存货"))
            and bool(re.search(r"\d[\d,，.]*(?:%|％|亿元|万元|亿|万)", compact_segment))
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
    projected_role = _annual_display_role(row.render_role, projected_body)
    projected_title = row.title if projected_role == row.render_role else {
        "technology_product_progress": "技术与产品进展",
        "market_competition_outlook": "市场与竞争",
        "financial_quality_explanation": "分部财务信息",
    }.get(projected_role, row.title)
    if projected_body == row.body and projected_role == row.render_role and projected_title == row.title:
        return row, ""
    return replace(
        row,
        body=projected_body,
        title=projected_title,
        text=f"{projected_title}：{projected_body}" if projected_title else projected_body,
        render_role=projected_role,
    ), ""


def _strip_annual_self_comparison(segment: str) -> str:
    trimmed = re.sub(
        r"^(?:在业界|在業界)?率先(?=(?:推出|发布|發佈|量产|量產))",
        "",
        segment,
    )
    trimmed = re.sub(
        r"^(?:(?:公司|本公司)(?:是|为|為)|作为|作為)(?:国内|國內|全球|行业|行業)?"
        r"(?:领先|領先|唯一)[^，,。；;]{0,100}[，,]\s*",
        "",
        trimmed,
    )
    trimmed = re.sub(
        r"^(?:公司|本公司)是(?:国内|國內)[^，,。；;]{0,60}(?:产品线|產品線)(?:较|較)广的企业[，,]\s*",
        "公司",
        trimmed,
    )
    trimmed = re.sub(
        r"^(.{2,40}?(?:平台|产品|產品))以[^，,。；;]{1,80}(?:引领|引領)"
        r"[^，,。；;]{1,80}[，,](?=(?:通过|通過))",
        r"\1",
        trimmed,
    )
    trimmed = re.sub(
        r"^(.{1,40}?)(?:因|凭借|憑藉)(?:良好|稳定|穩定|优异|優異|强大|強大)"
        r"[^，,]{1,60}[，,]",
        r"\1",
        trimmed,
    )
    trimmed = re.sub(
        r"[，,](?:公司)?(?:产品|產品)竞争力(?:明显|明顯|强|強|较强|較強)[，,]"
        r"(?:得到|获得|獲得)(?:客户|客戶)(?:高度)?认可[。]?$",
        "。",
        trimmed,
    )
    trimmed = re.sub(
        r"(?:公司)?(?:产品|產品)竞争力(?:明显|明顯|强|強|较强|較強)[，,]?",
        "",
        trimmed,
    )
    trimmed = re.sub(
        r"[、，,](?:保持|維持)(?:公司|本公司)在(?:行业|行業)内的(?:竞争优势|競爭優勢)(?=奠定)",
        "",
        trimmed,
    )
    trimmed = re.sub(
        r"[，,](?:为|為)(?:客户|客戶)提供[^。；;]{0,120}(?:多元产品矩阵|多元產品矩陣)"
        r"[，,](?:全面)?匹配[^。；;]{1,80}[。]?$",
        "。",
        trimmed,
    )
    return re.sub(
        r"[，,](?:在(?:行业|行業)内)?(?:保持了?|具备|具備|拥有|擁有)"
        r"[^。；;]{0,100}(?:领先|領先)[^。；;]{0,24}[。]?$",
        "。",
        trimmed,
    )


def _annual_display_role(role: str, body: str) -> str:
    compact = re.sub(r"\s+", "", body)
    if (
        role == "financial_quality_explanation"
        and not any(term in compact for term in _ANNUAL_FINANCIAL_METRIC_TERMS)
        and any(term in compact for term in ("产能", "產能", "产线", "產線", "产业园", "產業園"))
        and any(term in compact for term in ("实施完毕", "實施完畢", "建成", "投产", "投產", "结项", "結項", "提升", "扩产", "擴產"))
    ):
        return "operating_progress"
    if role == "business_structure" and re.search(r"(?:销售成本|銷售成本|毛利率|现金流|現金流).{0,18}\d", compact):
        return "financial_quality_explanation"
    if role == "market_competition_outlook" and not any(term in compact for term in ("行业地位", "市場地位", "市场份额", "市占率", "竞争", "競爭", "领先", "領先")):
        if re.search(r"(?:开发|研發|研发|推出|发布|量产|验证).{0,40}(?:产品|芯片|平台|工具)", compact) or re.search(r"(?:产品|芯片|平台).{0,40}(?:开发|研發|研发|推出|发布|量产|验证)", compact):
            return "technology_product_progress"
    if role == "technology_product_progress" and any(term in compact for term in ("行业地位", "市場地位", "市场地位", "领先", "領先", "主要供应商", "主要供應商")):
        return "market_competition_outlook"
    return role


def _annual_segment_rejection_reason(segment: str, role: str) -> str:
    compact = re.sub(r"\s+", "", segment)
    if not compact:
        return "empty"
    if any(term in compact for term in ("领先", "領先", "领军者", "領軍者", "唯一", "显著优于", "顯著優於", "全面占优", "全面佔優")):
        return "unsupported_self_comparison"
    if "我们认为" in compact and "财务报表" in compact and "公允反映" in compact:
        return "audit_boilerplate"
    if (
        "公司需遵守" in compact
        or "披露要求" in compact
        or "机构独立情况" in compact
        or any(term in compact for term in ("供应商遴选", "本承诺函", "同业竞争", "保证独立性", "自主经营能力", "香港联交所", "无从事与本公司相同或相近的业务", "反贿赂", "反賄賂", "反腐败政策", "反腐敗政策", "商业道德", "商業道德"))
        or (any(term in compact for term in ("同业竞争", "关联交易", "资金占用")) and "承诺" in compact)
    ):
        return "disclosure_or_governance"
    if compact.startswith(">") or "|" in compact or "年度报告全文" in compact or "http://" in compact or "https://" in compact or re.match(r"^\d+[、.]\s*.{0,24}(?:风险|关税政策变化)", compact):
        return "document_or_heading_noise"
    if compact.count("•") >= 2 and len(compact) >= 70:
        return "catalog_without_business_value"
    if compact.endswith(("、", ":", "：", "…", "...")) or re.search(r"(?:公司|股权|股權|事项|事項)(?:经|經)$", compact) or compact.startswith(("方面，", "其中，", "此外，", "核心竞争力，", "并在", "与世界")) or ("知识产权列表" in compact and "申请数" in compact):
        return "document_or_heading_noise"
    if re.search(r"(?:与|和)?截至(?:\d{4}年\d{1,2}月\d{1,2}日止|\d{4}年?)$", compact):
        return "document_or_heading_noise"
    if role == "financial_quality_explanation" and re.search(r"(?:分别为|分別為).{0,50}(?:及|与|與)$", compact):
        return "document_or_heading_noise"
    if (
        role == "financial_quality_explanation"
        and len(re.findall(r"-?\d[\d,，]*(?:\.\d+)?", compact)) >= 8
        and (
            len(compact) >= 120
            or sum(term in compact for term in _ANNUAL_FINANCIAL_METRIC_TERMS) >= 4
        )
    ):
        return "financial_table_dump"
    if len(compact) <= 16 and not any(term in compact for term in ("公司", "产品", "客户", "收入", "增长", "研发")):
        return "document_or_heading_noise"
    if re.search(r"(?:主营业务|主要业务|主要产品|经营模式|业务模式).{0,18}(?:未|没有)发生(?:重大)?变化", compact):
        return "no_incremental_change"
    if sum(term in compact for term in ("产品系列", "产品外观", "产品特性", "应用场景")) >= 3:
        return "catalog_without_business_value"
    if re.match(r"^\d+[、.].{0,24}(?:产品线|芯片|业务)", compact) and not any(term in compact for term in ("客户", "量产", "出货", "增长", "下降", "导入", "推出")):
        return "document_or_heading_noise"
    if compact.startswith("主要应用于") and not any(term in compact for term in ("公司", "客户", "订单", "量产", "推出", "收入")):
        return "catalog_without_business_value"
    if (
        role == "market_competition_outlook"
        and re.match(r"^\d+[、.]?公司行业地位", compact)
        and not any(term in compact for term in ("市场份额", "排名", "领先", "竞争优势", "客户认可"))
    ):
        return "duplicate_business_profile"
    if (
        any(term in compact for term in ("持续关注", "提升核心竞争力", "稳步推进", "把握发展机遇"))
        and not re.search(r"\d", compact)
        and not any(term in compact for term in ("客户", "订单", "定点", "量产", "出货", "收入", "利润", "毛利率"))
    ):
        return "generic_management_statement"
    if (
        any(term in compact for term in ("避免技术流失", "避免技術流失", "技术保护措施", "技術保護措施"))
        and not re.search(r"\d", compact)
    ):
        return "generic_management_statement"
    if (
        role == "technology_product_progress"
        and not re.search(r"\d", compact)
        and (
            "始终重视技术创新" in compact
            or "力争保持技术领先" in compact
            or bool(re.search(r"持续.{0,12}研发投入", compact))
        )
    ):
        return "generic_management_statement"

    progress = ("报告期内", "实现", "增长", "下降", "出货", "交付", "导入", "进入", "量产", "拓展", "提升", "改善", "推出", "发布", "验证", "新增", "覆盖")
    linked = ("公司", "本集团", "管理层", "报告期内", "营收", "出货", "销量", "客户导入", "销售增长", "销售下滑")
    if any(term in compact for term in ("采购模式", "生产模式", "经营模式", "销售模式", "代理销售", "认证程序", "生产流程")):
        if "没有发生变化" in compact or not any(term in compact for term in progress + ("竞争优势", "财务", "利润", "毛利率")):
            return "routine_process"
    if any(term in compact for term in ("供应商认证", "客户认证", "供应商选择", "采购控制程序", "产品代码")) and not any(term in compact for term in progress):
        return "routine_process"

    spec_tokens = re.findall(r"(?:IEEE|MSA|QSFP|OSFP|CMIS|\b\d+(?:\.\d+)?[GMTK]?\b)", segment)
    if role != "financial_quality_explanation" and len(spec_tokens) >= 3 and not any(term in compact for term in progress + ("客户", "应用", "技术路线")):
        return "catalog_without_business_value"

    generic_industry = ("预测", "市场规模", "年均复合", "行业发展", "技术门槛", "技术壁垒", "全球市场", "全球宏观经济", "中国半导体", "海关总署", "国内互联网厂商", "国内芯片设计企业", "中国企业")
    if (role == "market_competition_outlook" or any(term in compact for term in generic_industry)) and not any(term in compact for term in linked):
        return "generic_industry_context"

    if role == "financial_quality_explanation":
        has_metric = any(term in compact for term in _ANNUAL_FINANCIAL_METRIC_TERMS)
        has_amount = has_metric and bool(re.search(r"\d", compact))
        has_explanation = has_metric and any(term in compact for term in _ANNUAL_FINANCIAL_EXPLANATION_TERMS)
        has_quality_fact = any(term in compact for term in _ANNUAL_FINANCIAL_QUALITY_TERMS)
        if not (has_amount or has_explanation or has_quality_fact):
            return "role_mismatch"
        return ""

    terms = {
        "business_structure": ("公司", "主营", "主要业务", "产品", "客户", "应用", "服务于", "从事", "平台", "增长"),
        "operating_progress": progress,
        "market_competition_outlook": ("公司", "管理层", "竞争", "战略", "需求", "行业地位", "市场份额", "产品", "应用"),
        "technology_product_progress": ("研发", "研發", "推出", "发布", "發佈", "量产", "量產", "验证", "驗證", "定点", "定點", "技术", "技術", "平台", "产品", "產品", "投入", "迭代"),
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
            same_role = previous.render_role == row.render_role
            if not body_key:
                continue
            if body_key == previous_key:
                reason = "duplicate_exact"
            elif same_role and (body_key in previous_key or previous_key in body_key):
                reason = "duplicate_contained"
            elif (
                same_role
                and row.render_role == "financial_quality_explanation"
                and _financial_fact_keys(row.body) & _financial_fact_keys(previous.body)
            ):
                reason = "duplicate_financial_fact"
            else:
                continue
            reasons[reason] = reasons.get(reason, 0) + 1
            if (
                reason == "duplicate_financial_fact"
                and _financial_insight_score(row) > _financial_insight_score(previous)
            ) or (reason != "duplicate_financial_fact" and len(body_key) > len(previous_key)):
                kept[index] = row
            break
        else:
            kept.append(row)
    return tuple(kept), sum(reasons.values()), reasons


def _financial_fact_keys(body: str) -> set[tuple[str, str]]:
    compact = re.sub(r"\s+", "", body)
    metric = next((name for name, aliases in _FINANCIAL_FACT_ALIASES if any(alias in compact for alias in aliases)), "")
    if not metric:
        return set()
    return {
        (metric, f"{value.replace(',', '').replace('，', '')}{unit.replace('億', '亿').replace('萬', '万')}")
        for value, unit in re.findall(r"(-?\d[\d,，]*(?:\.\d+)?)\s*(亿元|億元|万元|萬元|百万元|百萬元|千元|元)", compact)
    }


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
        snapshot.external_topic_narratives, external_rows, (*annual_rows, *broker_rows),
    )
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
                       visible_rows_count=sum(len(section.rows) for section in sections),
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
_OWNER_FACT_POLARITY_TERMS = ("未", "不", "没有", "无", "不及", "低于", "放缓", "受限", "风险", "瓶颈")
_OWNER_FACT_RELATION_TERMS = ("合作", "客户", "供应商", "竞争对手", "绑定", "长协")
_OWNER_FACT_PUNCTUATION = str.maketrans("，；：！？。", ",;:!?.")
_TIME_ANCHOR_RE = re.compile(
    r"20\d{2}(?:Q[1-4]|H[12])?|(?:20\d{2}年)?(?:上半年|下半年|[一二三四]季度)|\d{1,2}月\d{1,2}日",
    re.I,
)
_FINANCIAL_FACT_METRICS = (
    ("扣非净利润", ("扣非净利润",)),
    ("归母净利润", ("归母净利润",)),
    ("营业收入", ("营业收入", "营收")),
    ("经营现金流", ("经营现金流",)),
    ("毛利率", ("毛利率",)),
    ("净利润", ("净利润",)),
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
    owner_rows: Iterable[MaterialRow] = (),
) -> Tuple[ExternalTopicNarrative, ...]:
    selected = tuple(rows)
    owner_units = _owner_fact_units(owner_rows)
    result = []
    for narrative in narratives:
        scoped = tuple(row for row in selected if (
            _external_scope_bucket(row.entity_scope) == narrative.scope_bucket
            and row.external_family == narrative.primary_family
        ))
        expected = [(row.argument_key, unit_id) for row in scoped for unit_id in row.external_unit_ids]
        keys = {row.argument_key for row in scoped}
        parts = tuple(part for part in narrative.parts if part.argument_key in keys)
        received = [(part.argument_key, part.unit_id) for part in parts]
        if expected and sorted(received) == sorted(expected):
            parts = _dedupe_external_narrative_parts(parts)
            if narrative.scope_bucket == "target" and owner_units:
                parts = tuple(part for part in parts if not any(
                    _same_owner_fact(part.quote, owner) for owner in owner_units
                ))
            if parts:
                parts = (replace(parts[0], relation="first"), *parts[1:])
            result.append(replace(narrative, parts=parts))
    return tuple(result)


def _dedupe_external_narrative_parts(
    parts: Iterable[ExternalNarrativePart],
) -> Tuple[ExternalNarrativePart, ...]:
    result = []
    for part in parts:
        duplicate = next((index for index, kept in enumerate(result) if _same_external_fact(kept.quote, part.quote)), None)
        if duplicate is None:
            result.append(part)
            continue
        kept = result[duplicate]
        representative = max((kept, part), key=lambda item: len(_normalized_claim_body(item.quote)))
        result[duplicate] = replace(
            representative,
            relation=kept.relation,
            citation_refs=tuple(dict.fromkeys((*kept.citation_refs, *part.citation_refs))),
        )
    return tuple(result)


def _same_external_fact(left: str, right: str) -> bool:
    left_key = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", left).lower()
    right_key = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", right).lower()
    if not left_key or not right_key:
        return False
    left_metric = _financial_fact_metric(left)
    right_metric = _financial_fact_metric(right)
    if (left_metric or right_metric) and left_metric != right_metric:
        return False
    ratio = SequenceMatcher(None, left_key, right_key).ratio()
    left_numbers = tuple(float(value) for value in re.findall(r"\d+(?:\.\d+)?", left))
    right_numbers = tuple(float(value) for value in re.findall(r"\d+(?:\.\d+)?", right))
    if not left_numbers and not right_numbers:
        return ratio >= 0.88
    if not left_numbers or not right_numbers or ratio < 0.58:
        return False
    shorter, longer = sorted((left_numbers, right_numbers), key=len)
    unmatched = list(longer)
    for value in shorter:
        match = next((item for item in unmatched if abs(item - value) <= max(0.02, abs(value) * 0.002)), None)
        if match is None:
            return False
        unmatched.remove(match)
    return True


def _owner_fact_units(rows: Iterable[MaterialRow]) -> Tuple[str, ...]:
    return tuple(
        unit.strip()
        for row in rows
        for unit in re.split(r"(?<=[。！？!?；;])", row.body or "")
        if _normalized_claim_body(unit)
    )


def _same_owner_fact(external: str, owner: str) -> bool:
    external_key = _normalized_claim_body(external).translate(_OWNER_FACT_PUNCTUATION)
    owner_key = _normalized_claim_body(owner).translate(_OWNER_FACT_PUNCTUATION)
    if not external_key or not owner_key:
        return False
    external_metric, owner_metric = _financial_fact_metric(external), _financial_fact_metric(owner)
    if (external_metric or owner_metric) and external_metric != owner_metric:
        return False
    external_times = set(_TIME_ANCHOR_RE.findall(external))
    owner_times = set(_TIME_ANCHOR_RE.findall(owner))
    if external_times and owner_times and external_times != owner_times:
        return False
    if _concrete_anchors(external) - _concrete_anchors(owner):
        return False
    for terms in (_EXTERNAL_EVENT_TERMS, _OWNER_FACT_POLARITY_TERMS, _OWNER_FACT_RELATION_TERMS):
        if {term for term in terms if term in external} - {term for term in terms if term in owner}:
            return False
    if external_key == owner_key:
        return True
    if len(external_key) >= 24 and external_key in owner_key:
        return True
    length_compatible = len(external_key) <= len(owner_key) * 1.1
    return length_compatible and (
        (len(owner_key) >= 24 and owner_key in external_key)
        or SequenceMatcher(None, external_key, owner_key).ratio() >= 0.92
    )


def _financial_fact_metric(text: str) -> str:
    return next((metric for metric, aliases in _FINANCIAL_FACT_METRICS if any(alias in text for alias in aliases)), "")


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
