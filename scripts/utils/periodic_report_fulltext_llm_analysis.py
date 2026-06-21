"""Experimental full-text periodic report LLM analysis path.

This module intentionally runs in parallel to the deterministic evidence-pack
path. It keeps larger annual-report chunks for LLM reading, while shared
validation helpers keep outputs grounded by evidence refs.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

if __name__.startswith("utils."):
    from .periodic_report_evidence_pack import build_periodic_report_evidence_pack
    from .periodic_report_product_project_evidence import (
        _customer_org_tokens,
        build_company_profile_backfill,
        build_rd_progress_backfill,
        extract_product_project_evidence,
    )
    from .periodic_report_required_metrics import _normalize_numeric
    from .periodic_report_validation import (
        check_fidelity,
        has_citation_markers,
        has_raw_url,
        normalize_confidence,
        sanitize_text,
    )
else:
    from periodic_report_evidence_pack import build_periodic_report_evidence_pack
    from periodic_report_product_project_evidence import (
        _customer_org_tokens,
        build_company_profile_backfill,
        build_rd_progress_backfill,
        extract_product_project_evidence,
    )
    from periodic_report_required_metrics import _normalize_numeric
    from periodic_report_validation import (
        check_fidelity,
        has_citation_markers,
        has_raw_url,
        normalize_confidence,
        sanitize_text,
    )


FULLTEXT_SCHEMA_VERSION = "periodic_report_fulltext_pack.v1"
FULLTEXT_ANALYSIS_SCHEMA_VERSION = "periodic_report_fulltext_analysis.v1"
FIXED_ANALYSIS_SECTION_TITLES = (
    "公司画像",
    "主营业务表现",
    "客户与订单结构",
    "研发与技术进展",
    "管理层市场判断",
    "财务风险与跟踪指标",
)
FINANCIAL_RISK_CANDIDATE_TYPES = (
    "profit_quality",
    "revenue_recognition",
    "customer_concentration",
    "supplier_concentration",
    "inventory_impairment",
    "receivables_collection",
    "cash_flow_quality",
    "capex_capacity",
    "asset_impairment",
    "rd_conversion",
    "government_grant_dependency",
    "financial_asset_dependency",
    "goodwill_impairment",
    "fx_overseas_exposure",
    "related_party_governance",
    "audit_internal_control",
    "litigation_contingency",
    "other_material_risk",
)
_ALLOWED_RISK_IMPORTANCE = frozenset({"high", "medium", "low"})

_DEFAULT_CHUNK_CHARS = 8000
_DEFAULT_MAX_TOTAL_CHARS = 120000
_DEFAULT_MAX_CHUNKS = 18
_DEFAULT_MAX_PROMPT_CHARS = 140000

_HK_SECTION_HEADINGS = (
    "主要摘要",
    "董事長致辭",
    "主席報告",
    "管理層討論及分析",
    "企業管治報告",
    "董事會報告",
    "環境、社會及管治報告",
    "獨立核數師報告",
    "綜合全面（虧損）╱收益表",
    "綜合全面收益表",
    "綜合損益表",
    "綜合財務狀況表",
    "綜合權益變動表",
    "綜合現金流量表",
    "綜合財務報表附註",
    "釋義",
)
_HK_SECTION_HEADING_PATTERN = "|".join(re.escape(heading) for heading in _HK_SECTION_HEADINGS)
_SECTION_HEADING_RE = re.compile(
    rf"(?m)^\s*(?:#\s*)?"
    rf"((?:第[一二三四五六七八九十]+[节章节][^\n\r]{{0,60}})|(?:{_HK_SECTION_HEADING_PATTERN}))"
    rf"(?:\s|$)[^\n\r]{{0,80}}"
)
_CITATION_RE = re.compile(r"\[\^?\w+\]")
_URL_RE = re.compile(r"https?://\S+")
_SPACE_RE = re.compile(r"\s+")
_GROUND_TRUTH_SKIP_KEYS = frozenset({
    "id",
    "source_block_id",
    "source_block_ids",
    "source_excerpt",
    "evidence_ref",
    "evidence_refs",
    "fact_id",
    "card_id",
    "schema_version",
    "diagnostics",
})


class PeriodicReportFulltextError(Exception):
    """Raised when full-text LLM analysis output is invalid."""


def build_periodic_report_fulltext_pack(
    text: str,
    *,
    report_type: str = "auto",
    chunk_chars: int = _DEFAULT_CHUNK_CHARS,
    max_total_chars: int = _DEFAULT_MAX_TOTAL_CHARS,
    max_chunks: int = _DEFAULT_MAX_CHUNKS,
) -> Dict[str, Any]:
    """Build larger section-aware evidence chunks from a periodic report text."""
    if not text:
        return {
            "schema_version": FULLTEXT_SCHEMA_VERSION,
            "report_type": "unknown" if report_type == "auto" else report_type,
            "audit_status": "unknown",
            "blocks": [],
            "experimental": True,
        }

    metadata = build_periodic_report_evidence_pack(text, report_type=report_type)
    cleaned = _clean_fulltext(text)
    sections = _split_major_sections(cleaned)
    if not sections:
        sections = [("全文", cleaned)]

    blocks: List[Dict[str, Any]] = []
    used_chars = 0
    for section_index, (heading, content) in enumerate(sections):
        if used_chars >= max_total_chars or len(blocks) >= max_chunks:
            break
        remaining = max_total_chars - used_chars
        if remaining <= 0:
            break
        for chunk_index, chunk in enumerate(_chunk_text(content, min(chunk_chars, remaining))):
            if used_chars >= max_total_chars or len(blocks) >= max_chunks:
                break
            chunk = chunk[: max_total_chars - used_chars]
            usage = _usage_for_fulltext_heading(heading)
            blocks.append({
                "id": f"fulltext-{section_index}-{chunk_index}",
                "usage": usage,
                "section": _clean_line(heading),
                "title": _clean_line(heading),
                "text": chunk,
                "source_span": {"start": 0, "end": 0},
            })
            used_chars += len(chunk)

    return {
        "schema_version": FULLTEXT_SCHEMA_VERSION,
        "report_type": metadata.get("report_type", "unknown"),
        "audit_status": metadata.get("audit_status", "unknown"),
        "blocks": blocks,
        "experimental": True,
        "max_total_chars": max_total_chars,
        "chunk_chars": chunk_chars,
    }


def build_periodic_report_fulltext_item_map(
    fulltext_pack: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Build an id -> block map for public callers that need ref validation."""
    return _build_item_map(fulltext_pack)


def build_empty_periodic_report_fulltext_analysis(
    fulltext_pack: Dict[str, Any],
    *,
    include_fixed_sections: bool = False,
) -> Dict[str, Any]:
    """Build the default analysis envelope without invoking an LLM."""
    analysis = _empty_fulltext_analysis(fulltext_pack)
    if include_fixed_sections:
        analysis["sections"] = [
            {"title": title, "judgments": []}
            for title in FIXED_ANALYSIS_SECTION_TITLES
        ]
    return analysis


def backfill_periodic_report_fulltext_analysis_sections(
    sections: List[Dict[str, Any]],
    item_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Add deterministic product/project/customer judgments to section data."""
    return _deduplicate_section_judgments(
        _backfill_sections_from_product_project_evidence(sections, item_map)
    )


def _build_ground_truth_prompt_block(
    required_metrics: Dict[str, Any] | None,
    required_financial_metrics: Dict[str, Any] | None,
) -> str:
    values = _collect_ground_truth_values(required_metrics, required_financial_metrics)
    if not values:
        return ""
    lines = [
        "## 财报关键数字 Ground Truth",
        "以下数字来自确定性表格/财务指标摘录，仅用于数值校验；evidence_refs 仍只能引用 fulltext-* id。",
    ]
    for value in values[:80]:
        lines.append(f"- {value}")
    if len(values) > 80:
        lines.append(f"- ... 另有 {len(values) - 80} 个确定性数字未展开。")
    return "\n".join(lines)


def _collect_ground_truth_values(
    required_metrics: Dict[str, Any] | None,
    required_financial_metrics: Dict[str, Any] | None,
) -> List[str]:
    values: List[str] = []
    seen = set()

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if not text or not re.search(r"\d", text):
            return
        normalized = _normalize_numeric(text)
        for candidate in (text, normalized):
            candidate = str(candidate or "").strip()
            if not candidate or not re.search(r"\d", candidate):
                continue
            if candidate not in seen:
                seen.add(candidate)
                values.append(candidate)

    def walk(obj: Any, key: str = "") -> None:
        if isinstance(obj, dict):
            normalized = obj.get("normalized")
            text = obj.get("text")
            unit = obj.get("unit")
            if normalized:
                add(normalized)
            if text:
                add(f"{text}{unit}" if unit and not str(text).endswith(str(unit)) else text)
            for child_key, child_value in obj.items():
                if child_key in _GROUND_TRUTH_SKIP_KEYS:
                    continue
                if child_key in {"normalized", "text", "unit"}:
                    continue
                walk(child_value, child_key)
            return
        if isinstance(obj, list):
            for item in obj:
                walk(item, key)
            return
        if key in {"normalized_values", "derived_financial_metrics"}:
            add(obj)

    walk(required_metrics or {})
    walk(required_financial_metrics or {})
    return values


def _ground_truth_fidelity_text(
    required_metrics: Dict[str, Any] | None,
    required_financial_metrics: Dict[str, Any] | None,
) -> str:
    return "；".join(_collect_ground_truth_values(required_metrics, required_financial_metrics))


def build_periodic_report_fulltext_prompt(
    fulltext_pack: Dict[str, Any],
    *,
    required_metrics: Dict[str, Any] | None = None,
    required_financial_metrics: Dict[str, Any] | None = None,
    max_prompt_chars: int = _DEFAULT_MAX_PROMPT_CHARS,
) -> Dict[str, Any]:
    """Build a large-context prompt for the experimental full-text path."""
    blocks = fulltext_pack.get("blocks") or []
    schema_example = {
        "schema_version": FULLTEXT_ANALYSIS_SCHEMA_VERSION,
        "sections": [
            {
                "title": "管理层市场判断",
                "judgments": [
                    {
                        "judgment": "管理层认为下游...，这意味着...",
                        "evidence_refs": ["fulltext-2-0"],
                        "confidence": 80,
                    }
                ],
            }
        ],
        "financial_risks": [
            {
                "risk_type": "inventory_impairment",
                "importance": "high",
                "summary": "存货...，资产减值...",
                "mechanism": "若需求转弱，可能继续计提跌价并压制毛利率。",
                "tracking_indicators": ["存货余额", "跌价准备", "毛利率"],
                "evidence_refs": ["fulltext-7-0"],
                "confidence": 85,
            },
            {
                "risk_type": "other_material_risk",
                "custom_label": "型号批产节奏风险",
                "importance": "high",
                "summary": "年报称...",
                "mechanism": "该风险不在候选池内，但会影响收入确认和产能利用率。",
                "tracking_indicators": ["订单节奏", "产能利用率"],
                "evidence_refs": ["fulltext-2-0"],
                "confidence": 80,
            },
        ],
    }
    section_names = " / ".join(FIXED_ANALYSIS_SECTION_TITLES)
    system = (
        "你是一个保守但有判断力的定期报告分析助手。当前使用的是全文/大块年报实验路径："
        "输入不是关键词摘录，而是年报较大章节块。目标是产出最终股票报告可复用的六段判断摘要，"
        "不是简单事实列表，也不是最终投资报告。\n\n"
        "允许在证据范围内做判断：你可以写“这意味着/说明/需要跟踪/形成压力/构成支撑”等分析，"
        "但每个判断必须绑定 evidence_refs，且判断中的数字、日期、产品名、客户名、供应商名必须来自对应证据块。"
        "不得补充外部事实，不得给出买卖建议、仓位建议或估值结论。\n\n"
        "HARD RULE：财务数字只能来自 Ground Truth 或 fulltext-* 证据原文。"
        "如果一个收入、利润、现金流、毛利率、客户占比、存货、应收、减值、capex、金融资产、政府补助等数字"
        "无法在 Ground Truth 或所引用 fulltext-* 块中定位，必须删除该数字或删除整条判断/风险。"
        "禁止引用训练数据、旧报告或外部记忆中的数字。\n\n"
        "必须输出严格 JSON，不要 Markdown 代码块，不要解释。schema_version 必须为 "
        f"{FULLTEXT_ANALYSIS_SCHEMA_VERSION}。允许顶层字段只有：schema_version、sections、financial_risks。\n\n"
        f"schema 示例：{schema_example}\n\n"
        "如果用户消息中提供 required_business_metrics，它是确定性表格摘录，只能作为写作覆盖清单和数值校验参考；"
        "不得把 required_business_metrics 作为 LLM 输出顶层字段，也不得把其中的 evidence-pack id "
        "（例如 segment_margin_table-0、production_sales_inventory_table-0、customer_supplier_table-0）写入 evidence_refs。"
        "evidence_refs 只能引用 fulltext-* id。\n\n"
        "如果用户消息中提供 required_financial_risk_metrics，它是确定性财务风险指标摘录，"
        "用于保证现金流、存货跌价、应收、capex、金融资产、商誉、审计/治理等关键数字不遗漏；"
        "不得把 required_financial_risk_metrics 作为 LLM 输出顶层字段，也不得把其中任何 evidence-pack id 写入 evidence_refs。\n\n"
        f"sections 必须且只能按以下 6 段输出，顺序也必须一致：{section_names}。"
        "每段必须包含 title 和 judgments。judgments 是对象数组，每项只允许字段：judgment、evidence_refs、confidence。"
        "每段建议 2-5 条 judgment；证据不足时可以为空数组，但不得新增第七段。\n\n"
        "六段写法要求：\n"
        "1. 公司画像：写公司做什么、产品/服务边界、经营模式、行业位置，并解释这些特征对分析有什么意义。"
        "如果证据块中出现产品系列、覆盖频段、终端客户/品牌客户/ODM/模组厂商、销售模式（经销/直销/买断式经销）等内容，"
        "必须在画像中体现，说明客户结构、渠道模式和覆盖范围对收入的潜在影响。\n"
        "2. 主营业务表现：写收入、利润、分产品/分地区/分渠道、毛利率、产销存变化，并解释增长质量或压力点。\n"
        "3. 客户与订单结构：写客户集中、供应商集中、经销/直销、订单节奏、回款敏感性，并解释依赖或韧性。"
        "如果证据中出现终端品牌客户、ODM 厂商、模组厂商、买断式经销、导入/认证/量产等客户导入状态，"
        "必须至少形成 1 条 judgment，避免只写前五名客户占比。\n"
        "销售模式占比要和客户/产品描述分开写：如果只引用销售模式表，只写“直销收入占比 X%”这类判断；"
        "不要把客户定性、产品描述和销售模式表数字混在同一条 judgment。"
        "若要写客户/产品描述，必须引用包含该描述的 fulltext 块，单独成句。\n"
        "4. 研发与技术进展：写研发费用、研发强度、资本化、研发人员、专利、新产品/项目进展，并解释技术路线和转化风险。"
        "如果证据中出现具体产品/技术名称（如高集成模组、射频前端方案等）及项目状态（量产、规模商用、预量产、"
        "验证、导入、通过认证等），必须至少形成 1 条 judgment，说明这些项目对收入转化和毛利率修复的意义。\n"
        "5. 管理层市场判断：保留下游行业、市场规模、CAGR、供需结构、价格趋势、竞争格局等年报中的关键数字和表述；"
        "必须写成“年报称/管理层认为”，不得升级为外部确认事实。\n"
        "6. 财务风险与跟踪指标：写存货跌价、收入确认、现金流、应收/票据、capex、商誉、金融资产、汇率、政府补助、治理信号，"
        "并给出后续要跟踪的指标。\n\n"
        "不要只摘事实。每条 judgment 应包含“事实/数据 + 分析含义/风险/跟踪意义”。"
        "如果证据块中出现“前五名客户/前五大客户/客户A/供应商/经销/直销/采购计划/订单节奏/应收账款前五名”等内容，"
        "“客户与订单结构”这一段不得为空，必须至少形成 1 条 judgment。"
        "financial_risks 是开放式财务风险排查：候选池不是上限。"
        "先扫描候选池：profit_quality、revenue_recognition、customer_concentration、supplier_concentration、"
        "inventory_impairment、receivables_collection、cash_flow_quality、capex_capacity、asset_impairment、"
        "rd_conversion、government_grant_dependency、financial_asset_dependency、goodwill_impairment、"
        "fx_overseas_exposure、related_party_governance、audit_internal_control、litigation_contingency。"
        "然后按这家公司实际重要性选出 Top Risks，数量服从证据质量和重要性，不做硬性截断。若年报出现候选池外但重要的风险，"
        "必须用 risk_type=other_material_risk，并填写 custom_label。"
        "每条 financial_risks 只允许字段：risk_type、custom_label、importance、summary、mechanism、"
        "tracking_indicators、evidence_refs、confidence。importance 只允许 high/medium/low。"
        "summary 写证据数字，mechanism 写风险传导机制，tracking_indicators 写后续跟踪指标。"
        "financial_risks 按重要性排序，通常 5-9 条，但候选池外或多项风险确实重要时必要时可以超过 9 条；"
        "不为凑数硬写没有证据支撑的问题，不能只写在“财务风险与跟踪指标”正文段里。"
        "如果证据中出现经销/价格调整/前五名客户/前五名供应商/存货/跌价准备/应收账款/应收票据/"
        "经营现金流/购建固定资产/在建工程/资产减值/交易性金融资产/投资收益/政府补助/商誉/汇率/"
        "诉讼/冻结资金/内控/审计意见/董事异议等关键词，应优先判断是否进入 financial_risks。"
        "禁止 raw URL，禁止 [^1]、[1]、[^verified]、[^supported] 等引用标记。"
        "禁止 confirmed_fact、fact_candidate、核心事实、已证实。"
    )
    user_parts = [
        f"报告类型：{fulltext_pack.get('report_type', 'unknown')}",
        f"审计状态：{fulltext_pack.get('audit_status', 'unknown')}",
    ]
    ground_truth_block = _build_ground_truth_prompt_block(
        required_metrics,
        required_financial_metrics,
    )
    if ground_truth_block:
        user_parts.append(ground_truth_block)
    if required_metrics:
        user_parts.extend([
            "required_business_metrics（确定性摘录，禁止将其中 id 用作 evidence_refs）：",
            json.dumps(required_metrics, ensure_ascii=False, sort_keys=True),
        ])
    if required_financial_metrics:
        user_parts.extend([
            "required_financial_risk_metrics（确定性摘录，禁止将其中 id 用作 evidence_refs）：",
            json.dumps(required_financial_metrics, ensure_ascii=False, sort_keys=True),
        ])
    user_parts.append("以下为大块年报原文证据。只基于这些 fulltext-* 块输出 JSON：")
    for block in blocks:
        user_parts.append(
            f"id: {block.get('id')}\n"
            f"usage: {block.get('usage')}\n"
            f"section: {block.get('section')}\n"
            f"title: {block.get('title')}\n"
            f"text:\n{block.get('text', '')}"
        )
    user = "\n\n".join(user_parts)
    if len(user) > max_prompt_chars:
        user = user[: max_prompt_chars - 1].rstrip() + "…"
    return {
        "system": system,
        "user": user,
        "item_map": {block.get("id"): block for block in blocks if block.get("id")},
        "report_meta": {
            "report_type": fulltext_pack.get("report_type", "unknown"),
            "audit_status": fulltext_pack.get("audit_status", "unknown"),
        },
    }


def summarize_periodic_report_fulltext_with_llm(
    fulltext_pack: Dict[str, Any],
    client: object,
    *,
    required_metrics: Dict[str, Any] | None = None,
    required_financial_metrics: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Run the experimental full-text prompt and validate fixed-section judgments."""
    if not client:
        raise ValueError("client is required")
    if not fulltext_pack.get("blocks"):
        return _empty_fulltext_analysis(fulltext_pack)
    prompt = build_periodic_report_fulltext_prompt(
        fulltext_pack,
        required_metrics=required_metrics,
        required_financial_metrics=required_financial_metrics,
    )
    raw_response = _call_client(client, prompt)
    validated = validate_periodic_report_fulltext_output(
        raw_response,
        fulltext_pack,
        required_metrics=required_metrics,
        required_financial_metrics=required_financial_metrics,
    )
    return {
        **validated,
        "source_type": "periodic_report_fulltext_analysis",
        "source_credit": 75,
        "verification_status": "professional_analysis",
        "claim_status": "professional_analysis",
        "knowledge_eligible": False,
        "report_eligible": False,
        "experimental": True,
    }


def render_periodic_report_fulltext_markdown(
    analysis: Dict[str, Any],
    *,
    required_metrics: Dict[str, Any] | None = None,
    required_financial_metrics: Dict[str, Any] | None = None,
) -> str:
    """Render fixed-section full-text analysis as Markdown."""
    if not isinstance(analysis, dict):
        return ""

    lines = [
        "# 定期报告全文判断摘要",
        "",
        f"- 报告类型：{analysis.get('report_type', 'unknown')}",
        f"- 审计状态：{analysis.get('audit_status', 'unknown')}",
        f"- 来源类型：{analysis.get('source_type', 'periodic_report_fulltext_analysis')}",
        f"- 信用等级：{analysis.get('source_credit', 75)}",
        f"- 核验状态：{analysis.get('verification_status', 'professional_analysis')}",
        "",
        "> 本摘要是全文/大块年报实验路径产物：允许基于证据做分析判断，但每条判断必须绑定 evidence_refs；"
        "不直接进入核心事实、评分、风险评分或最终建议。",
        "",
    ]
    lines.extend(_render_required_metrics_lines(required_metrics))
    lines.extend(_render_required_financial_metrics_lines(required_financial_metrics))
    for section in analysis.get("sections") or []:
        title = _escape_md(str(section.get("title", "")))
        lines.extend([f"## {title}", ""])
        judgments = section.get("judgments") or []
        if not judgments:
            lines.extend(["未形成可引用判断。", ""])
        else:
            for item in judgments:
                judgment = _escape_md(str(item.get("judgment", "")))
                confidence = item.get("confidence", "—")
                refs = item.get("evidence_refs") or []
                ref_text = f"；依据：{', '.join(str(ref) for ref in refs)}" if refs else ""
                lines.append(f"- {judgment}（置信度 {confidence}{ref_text}）")
            lines.append("")
        if section.get("title") == "财务风险与跟踪指标":
            risks = analysis.get("financial_risks") or []
            if risks:
                lines.extend(["### 重点财务风险清单", ""])
                for risk in risks:
                    label = str(risk.get("custom_label") or risk.get("risk_type", ""))
                    importance = str(risk.get("importance", ""))
                    confidence = risk.get("confidence", "—")
                    refs = risk.get("evidence_refs") or []
                    summary = _escape_md(str(risk.get("summary", "")))
                    mechanism = _escape_md(str(risk.get("mechanism", "")))
                    indicators = "、".join(str(item) for item in risk.get("tracking_indicators") or [])
                    ref_text = f"；依据：{', '.join(str(ref) for ref in refs)}" if refs else ""
                    lines.append(f"- **{_escape_md(label)}**（{importance}，置信度 {confidence}{ref_text}）：{summary}")
                    if mechanism:
                        lines.append(f"  - 机制：{mechanism}")
                    if indicators:
                        lines.append(f"  - 跟踪指标：{_escape_md(indicators)}")
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_periodic_report_fulltext_audit_markdown(
    analysis: Dict[str, Any],
    fulltext_pack: Dict[str, Any],
    *,
    max_excerpt_chars: int = 600,
) -> str:
    """Render analysis with referenced source snippets for manual grounding review."""
    if not isinstance(analysis, dict):
        return ""
    item_map = _build_item_map(fulltext_pack)
    lines = [
        "# 定期报告全文判断证据审计",
        "",
        "> 用于人工核验 LLM 总结是否被原文证据支撑；这里只展开每条 judgment/risk 的 evidence_refs 原文片段。",
        "",
    ]
    for section in analysis.get("sections") or []:
        title = _escape_md(str(section.get("title", "")))
        lines.extend([f"## {title}", ""])
        judgments = section.get("judgments") or []
        if not judgments:
            lines.extend(["未形成可审计判断。", ""])
            continue
        for index, judgment in enumerate(judgments, start=1):
            text = _escape_md(str(judgment.get("judgment", "")))
            confidence = judgment.get("confidence", "—")
            lines.extend([
                f"### 判断 {index}",
                "",
                f"- 摘要：{text}",
                f"- 置信度：{confidence}",
                "",
            ])
            lines.extend(_render_audit_ref_lines(
                judgment.get("evidence_refs") or [],
                item_map,
                max_excerpt_chars,
            ))
    risks = analysis.get("financial_risks") or []
    if risks:
        lines.extend(["## 财务风险证据", ""])
        for index, risk in enumerate(risks, start=1):
            label = str(risk.get("custom_label") or risk.get("risk_type", ""))
            summary = _escape_md(str(risk.get("summary", "")))
            mechanism = _escape_md(str(risk.get("mechanism", "")))
            confidence = risk.get("confidence", "—")
            lines.extend([
                f"### 风险 {index}: {_escape_md(label)}",
                "",
                f"- 摘要：{summary}",
                f"- 机制：{mechanism}",
                f"- 置信度：{confidence}",
                "",
            ])
            lines.extend(_render_audit_ref_lines(
                risk.get("evidence_refs") or [],
                item_map,
                max_excerpt_chars,
            ))
    return "\n".join(lines).rstrip() + "\n"


def validate_periodic_report_fulltext_output(
    raw_text: str,
    fulltext_pack: Dict[str, Any],
    *,
    required_metrics: Dict[str, Any] | None = None,
    required_financial_metrics: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Validate fixed-section full-text LLM output against evidence chunks."""
    if not isinstance(raw_text, str):
        raise PeriodicReportFulltextError("raw_text must be a string")

    try:
        import json

        parsed = json.loads(_extract_json_payload(raw_text))
    except Exception as exc:
        raise PeriodicReportFulltextError(f"JSON parse failed: {exc}") from exc

    if not isinstance(parsed, dict):
        raise PeriodicReportFulltextError("JSON root must be an object")
    if parsed.get("schema_version") != FULLTEXT_ANALYSIS_SCHEMA_VERSION:
        raise PeriodicReportFulltextError(
            f"schema_version mismatch: {parsed.get('schema_version')!r}"
        )
    extra_keys = set(parsed) - {"schema_version", "sections", "financial_risks"}
    if extra_keys:
        raise PeriodicReportFulltextError(f"unsupported top-level field: {sorted(extra_keys)[0]}")
    _reject_illegal_content(parsed)

    item_map = _build_item_map(fulltext_pack)
    ground_truth_text = _ground_truth_fidelity_text(required_metrics, required_financial_metrics)
    sections = parsed.get("sections")
    if not isinstance(sections, list):
        raise PeriodicReportFulltextError("sections must be a list")
    titles = [section.get("title") if isinstance(section, dict) else None for section in sections]
    if titles != list(FIXED_ANALYSIS_SECTION_TITLES):
        raise PeriodicReportFulltextError("sections must match fixed six titles")

    normalized_sections: List[Dict[str, Any]] = []
    for section in sections:
        judgments = section.get("judgments", [])
        if judgments is None:
            judgments = []
        if not isinstance(judgments, list):
            raise PeriodicReportFulltextError("judgments must be a list")
        normalized_judgments = []
        for judgment in judgments:
            if not isinstance(judgment, dict):
                continue
            extra_item_keys = set(judgment) - {"judgment", "evidence_refs", "confidence", "importance"}
            if extra_item_keys:
                raise PeriodicReportFulltextError(
                    f"unsupported judgment field: {sorted(extra_item_keys)[0]}"
                )
            refs = judgment.get("evidence_refs")
            _reject_invalid_evidence_refs(refs, item_map)
            confidence = normalize_confidence(judgment.get("confidence"))
            if confidence is None:
                continue
            text = str(judgment.get("judgment", ""))
            if has_citation_markers(text):
                raise PeriodicReportFulltextError("judgment contains citation marker")
            if has_raw_url(text):
                raise PeriodicReportFulltextError("judgment contains raw URL")
            text = sanitize_text(text)
            if not text:
                continue
            if not _check_fidelity_with_ground_truth(text, refs, item_map, ground_truth_text):
                continue
            normalized_judgments.append({
                "judgment": text,
                "evidence_refs": list(refs),
                "confidence": confidence,
            })
        normalized_sections.append({
            "title": str(section.get("title")),
            "judgments": normalized_judgments,
        })
    normalized_sections = _backfill_sections_from_required_metrics(
        normalized_sections,
        required_metrics,
        item_map,
    )
    normalized_sections = _backfill_sections_from_product_project_evidence(
        normalized_sections,
        item_map,
    )
    normalized_sections = _deduplicate_section_judgments(normalized_sections)

    financial_risks = parsed.get("financial_risks") or []
    normalized_risks = _normalize_financial_risks(financial_risks, item_map, ground_truth_text)
    normalized_risks = _backfill_risks_from_sections(normalized_sections, normalized_risks)
    normalized_risks = _backfill_risks_from_required_financial_metrics(
        normalized_risks,
        required_financial_metrics,
        required_metrics,
        item_map,
    )
    normalized_risks = _deduplicate_financial_risks(normalized_risks)

    return {
        "schema_version": FULLTEXT_ANALYSIS_SCHEMA_VERSION,
        "report_type": fulltext_pack.get("report_type", "unknown"),
        "audit_status": fulltext_pack.get("audit_status", "unknown"),
        "sections": normalized_sections,
        "financial_risks": normalized_risks,
    }


def _split_major_sections(text: str) -> List[tuple[str, str]]:
    matches = [
        match for match in _SECTION_HEADING_RE.finditer(text)
        if not _looks_like_toc_heading(match.group(0))
    ]
    if not matches:
        return []
    sections: List[tuple[str, str]] = []
    preface = _extract_hk_preface_business_content(text[:matches[0].start()])
    if preface:
        sections.append(("業務回顧及前景", preface))
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        heading = _clean_line(match.group(1))
        content = text[start:end].strip()
        if heading and content:
            sections.append((heading, content))
    return sections


def _extract_hk_preface_business_content(prefix: str) -> str:
    """Keep HK business-review content that appears before first detected heading."""
    if not prefix:
        return ""
    lines = []
    started = False
    business_tokens = (
        "本公司",
        "收入",
        "毛利率",
        "產品",
        "产品",
        "解決方案",
        "解决方案",
        "量產",
        "量产",
        "OEM",
        "客戶",
        "客户",
        "HSD",
        "SuperDrive",
        "征程",
        "Journey",
    )
    for line in prefix.splitlines():
        stripped = line.strip()
        if not stripped:
            if started:
                lines.append("")
            continue
        if not started:
            if "目錄" in stripped or "股份代號" in stripped or "公司資料" in stripped:
                continue
            if not any(token in stripped for token in business_tokens):
                continue
            started = True
        lines.append(stripped)
    content = "\n".join(lines).strip()
    if len(content) < 80:
        return ""
    return content


def _looks_like_toc_heading(line: str) -> bool:
    compact = line.strip()
    return "..." in compact or "……" in compact or bool(re.search(r"\.{3,}\s*\d+\s*$", compact))


def _chunk_text(text: str, chunk_chars: int) -> List[str]:
    if len(text) <= chunk_chars:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_chars)
        boundary = max(text.rfind("\n", start, end), text.rfind("。", start, end))
        if boundary > start + chunk_chars // 2:
            end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks


def _usage_for_fulltext_heading(heading: str) -> str:
    compact = re.sub(r"\s+", "", heading)
    if "公司简介" in compact or "财务指标" in compact:
        return "fulltext_financial_snapshot"
    if "主要摘要" in compact:
        return "fulltext_financial_snapshot"
    if (
        "管理层讨论" in compact
        or "管理層討論" in compact
        or "業務回顧" in compact
        or "业务回顾" in compact
        or "董事長致辭" in compact
        or "主席報告" in compact
    ):
        return "fulltext_management_discussion"
    if "重要事项" in compact or "董事會報告" in compact:
        return "fulltext_important_events"
    if (
        "财务报告" in compact
        or "獨立核數師報告" in compact
        or "綜合財務" in compact
        or "綜合全面" in compact
        or "綜合損益" in compact
        or "綜合權益" in compact
        or "綜合現金流量" in compact
    ):
        return "fulltext_financial_notes"
    if "公司治理" in compact or "企業管治" in compact:
        return "fulltext_governance"
    if "风险" in compact or "重要提示" in compact:
        return "fulltext_risk_disclosure"
    return "fulltext_section"


def _call_client(client: object, prompt: Dict[str, Any]) -> str:
    system = prompt.get("system", "")
    user = prompt.get("user", "")
    full_prompt = f"{system}\n\n{user}".strip()

    chat_fn = getattr(client, "chat", None)
    if callable(chat_fn):
        return str(chat_fn(full_prompt))

    completions = getattr(client, "chat", None)
    if hasattr(completions, "completions"):
        completions = completions.completions
    if hasattr(completions, "create"):
        response = completions.create(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=getattr(client, "model", "default"),
        )
        return _extract_completion_text(response)
    raise PeriodicReportFulltextError(
        "client must provide .chat(prompt) or .chat.completions.create(...)"
    )


def _extract_completion_text(response: object) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message") or {}
            return str(message.get("content", ""))
        return str(response.get("content", ""))
    choices = getattr(response, "choices", None)
    if choices:
        first = choices[0]
        if hasattr(first, "message"):
            return str(getattr(first.message, "content", ""))
        if isinstance(first, dict):
            message = first.get("message", {})
            return str(message.get("content", ""))
    return str(response)


def _check_fidelity_with_ground_truth(
    text: str,
    refs: List[str],
    item_map: Dict[str, Any],
    ground_truth_text: str = "",
) -> bool:
    if check_fidelity(text, refs, item_map):
        return True
    if not ground_truth_text:
        return False
    augmented_item_map: Dict[str, Any] = {}
    for ref, item in item_map.items():
        if not isinstance(item, dict):
            augmented_item_map[ref] = item
            continue
        augmented_item = dict(item)
        augmented_item["text"] = (
            f"{item.get('text', '')}\n\n"
            "Ground Truth normalized values:\n"
            f"{ground_truth_text}"
        )
        augmented_item_map[ref] = augmented_item
    return check_fidelity(text, refs, augmented_item_map)


def _normalize_financial_risks(
    risks: Any,
    item_map: Dict[str, Any],
    ground_truth_text: str = "",
) -> List[Dict[str, Any]]:
    if not isinstance(risks, list):
        raise PeriodicReportFulltextError("financial_risks must be a list")
    normalized: List[Dict[str, Any]] = []
    for risk in risks:
        if not isinstance(risk, dict):
            continue
        extra_keys = set(risk) - {
            "risk_type",
            "custom_label",
            "importance",
            "summary",
            "mechanism",
            "tracking_indicators",
            "evidence_refs",
            "confidence",
        }
        if extra_keys:
            raise PeriodicReportFulltextError(
                f"unsupported financial_risk field: {sorted(extra_keys)[0]}"
            )
        raw_risk_type = str(risk.get("risk_type", "")).strip()
        risk_type = _normalize_risk_type(raw_risk_type, risk)
        if risk_type not in FINANCIAL_RISK_CANDIDATE_TYPES:
            raise PeriodicReportFulltextError(f"unsupported risk_type: {risk_type}")
        custom_label = _normalize_custom_label(risk.get("custom_label", ""))
        if risk_type == "other_material_risk" and not custom_label:
            raise PeriodicReportFulltextError("other_material_risk requires custom_label")
        importance = str(risk.get("importance", "")).strip()
        if importance not in _ALLOWED_RISK_IMPORTANCE:
            continue
        refs = risk.get("evidence_refs")
        _reject_invalid_evidence_refs(refs, item_map)
        confidence = normalize_confidence(risk.get("confidence"))
        if confidence is None:
            continue

        summary = sanitize_text(str(risk.get("summary", "")))
        mechanism = sanitize_text(str(risk.get("mechanism", "")))
        tracking_indicators = risk.get("tracking_indicators") or []
        if not isinstance(tracking_indicators, list):
            continue
        tracking_indicators = [
            sanitize_text(str(item)) for item in tracking_indicators if sanitize_text(str(item))
        ]
        if _is_generic_risk_mechanism(mechanism):
            mechanism = _mechanism_for_inferred_risk(risk_type)
        if _is_generic_tracking_indicators(tracking_indicators):
            tracking_indicators = _tracking_indicators_for_inferred_risk(risk_type)
        combined_text = " ".join([summary, mechanism, " ".join(tracking_indicators)]).strip()
        if not combined_text:
            continue
        if _is_positive_observation_without_risk(raw_risk_type, f"{summary} {mechanism}"):
            continue
        if has_citation_markers(combined_text):
            raise PeriodicReportFulltextError("financial_risk contains citation marker")
        if has_raw_url(combined_text):
            raise PeriodicReportFulltextError("financial_risk contains raw URL")
        if not _check_fidelity_with_ground_truth(combined_text, refs, item_map, ground_truth_text):
            continue

        normalized_risk = {
            "risk_type": risk_type,
            "importance": importance,
            "summary": summary,
            "mechanism": mechanism,
            "tracking_indicators": tracking_indicators,
            "evidence_refs": list(refs),
            "confidence": confidence,
        }
        if custom_label:
            normalized_risk["custom_label"] = custom_label
        normalized.append(normalized_risk)
    return normalized


def _backfill_risks_from_sections(
    sections: List[Dict[str, Any]],
    risks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    existing = {_risk_semantic_key(risk) for risk in risks}
    backfilled = list(risks)
    for section in sections:
        for judgment in section.get("judgments") or []:
            text = str(judgment.get("judgment", ""))
            risk_type = _infer_risk_type_from_text(text)
            semantic_key = _risk_semantic_key({"risk_type": risk_type})
            if not risk_type or semantic_key in existing:
                continue
            refs = judgment.get("evidence_refs") or []
            confidence = judgment.get("confidence", 70)
            backfilled.append({
                "risk_type": risk_type,
                "importance": _importance_for_inferred_risk(risk_type),
                "summary": text,
                "mechanism": _mechanism_for_inferred_risk(risk_type),
                "tracking_indicators": _tracking_indicators_for_inferred_risk(risk_type),
                "evidence_refs": list(refs),
                "confidence": confidence,
            })
            existing.add(semantic_key)
    return backfilled


def _backfill_risks_from_required_financial_metrics(
    risks: List[Dict[str, Any]],
    required_financial_metrics: Dict[str, Any] | None,
    required_metrics: Dict[str, Any] | None,
    item_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not isinstance(required_financial_metrics, dict):
        return risks
    supplier = required_financial_metrics.get("supplier_concentration") or {}
    if not isinstance(supplier, dict):
        return risks
    business_supplier = {}
    if isinstance(required_metrics, dict) and isinstance(required_metrics.get("supplier_concentration"), dict):
        business_supplier = required_metrics.get("supplier_concentration") or {}
        supplier = {**business_supplier, **supplier}
    if not _should_backfill_supplier_concentration(supplier):
        return risks
    existing = {_risk_semantic_key(risk) for risk in risks}
    if "supplier_concentration" in existing:
        return risks

    top_pct = _metric_cell(supplier.get("top_five_percentage"))
    largest_pct = _metric_cell(supplier.get("largest_percentage"))
    top_amount = _metric_cell(supplier.get("top_five_amount"))
    largest_amount = _metric_cell(supplier.get("largest_amount"))
    summary_parts = []
    if top_amount or top_pct:
        summary_parts.append(
            f"前五名供应商采购额{top_amount or '未提取'}，占年度采购总额{top_pct or '未提取'}"
        )
    if largest_amount or largest_pct:
        summary_parts.append(
            f"第一大供应商采购额{largest_amount or '未提取'}，占比{largest_pct or '未提取'}"
        )
    summary = "；".join(summary_parts) + "。供应商集中度较高，需要作为财务风险跟踪项。"
    return [
        *risks,
        {
            "risk_type": "supplier_concentration",
            "importance": "high",
            "summary": summary,
            "mechanism": _mechanism_for_inferred_risk("supplier_concentration"),
            "tracking_indicators": _tracking_indicators_for_inferred_risk("supplier_concentration"),
            "evidence_refs": _refs_for_metric_values(item_map, (top_pct, largest_pct)) or _refs_for_required_metric_backfill(item_map),
            "confidence": 80,
        },
    ]


def _should_backfill_supplier_concentration(supplier: Dict[str, Any]) -> bool:
    top_pct = _metric_percentage_value(supplier.get("top_five_percentage"))
    largest_pct = _metric_percentage_value(supplier.get("largest_percentage"))
    return (top_pct is not None and top_pct >= 60) or (
        largest_pct is not None and largest_pct >= 30
    )


def _metric_percentage_value(cell: Any) -> float | None:
    text = _metric_cell(cell)
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _refs_for_metric_values(
    item_map: Dict[str, Any],
    values: tuple[str, ...],
) -> List[str]:
    wanted = [value for value in values if value]
    if not wanted:
        return []
    refs = []
    for ref, item in item_map.items():
        text = str(item.get("text", ""))
        compact_text = re.sub(r"\s+", "", text)
        if any(re.sub(r"\s+", "", value) in compact_text for value in wanted):
            refs.append(ref)
    return refs[:2]


def _backfill_sections_from_required_metrics(
    sections: List[Dict[str, Any]],
    required_metrics: Dict[str, Any] | None,
    item_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    result = [dict(section) for section in sections]
    if isinstance(required_metrics, dict):
        customer_section = next((section for section in result if section.get("title") == "客户与订单结构"), None)
        if customer_section and not customer_section.get("judgments"):
            text = _customer_order_judgment_from_required_metrics(required_metrics)
            refs = _refs_for_required_metric_backfill(item_map)
            if text and refs:
                customer_section["judgments"] = [{
                    "judgment": text,
                    "evidence_refs": refs,
                    "confidence": 70,
                }]
    _backfill_rd_section_from_fulltext(result, item_map)
    return result


def _backfill_sections_from_product_project_evidence(
    sections: List[Dict[str, Any]],
    item_map: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Backfill 公司画像 and 研发与技术进展 from generic product/project evidence."""
    result = [dict(section) for section in sections]
    evidence = extract_product_project_evidence(item_map)

    profile_section = next(
        (section for section in result if section.get("title") == "公司画像"), None
    )
    if profile_section:
        existing_text = " ".join(
            str(j.get("judgment", "")) for j in profile_section.get("judgments") or []
        )
        judgment, refs = build_company_profile_backfill(evidence)
        if judgment and refs:
            already_present = any(
                str(item.get("judgment", "")) == judgment
                for item in profile_section.get("judgments") or []
            )
            missing = _profile_missing_evidence(existing_text, evidence)
            if not already_present and (not profile_section.get("judgments") or missing):
                profile_section["judgments"] = (profile_section.get("judgments") or []) + [{
                    "judgment": judgment,
                    "evidence_refs": refs,
                    "confidence": 72,
                }]

    rd_section = next(
        (section for section in result if section.get("title") == "研发与技术进展"), None
    )
    if rd_section:
        existing_text = " ".join(
            str(j.get("judgment", "")) for j in rd_section.get("judgments") or []
        )
        judgment, refs = build_rd_progress_backfill(evidence)
        if judgment and refs:
            # Add as supplemental judgment if section is empty or if existing
            # judgments miss product/project names found in the evidence.
            product_names = _extracted_product_names(evidence)
            missing = any(name not in existing_text for name in product_names)
            if not rd_section.get("judgments") or missing:
                rd_section["judgments"] = (rd_section.get("judgments") or []) + [{
                    "judgment": judgment,
                    "evidence_refs": refs,
                    "confidence": 72,
                }]

    return result


def _deduplicate_section_judgments(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped_sections: List[Dict[str, Any]] = []
    for section in sections:
        seen = set()
        judgments = []
        for judgment in section.get("judgments") or []:
            key = str(judgment.get("judgment", ""))
            if key in seen:
                continue
            seen.add(key)
            judgments.append(judgment)
        deduped = dict(section)
        deduped["judgments"] = judgments
        deduped_sections.append(deduped)
    return deduped_sections


def _profile_missing_evidence(existing_text: str, evidence: Dict[str, Any]) -> bool:
    """Return True if existing profile text misses evidence we extracted."""
    issuer_names = evidence.get("issuer_names") or set()
    if evidence.get("customer_chain", {}).get("present"):
        # Look for at least one customer/ODM/module token from the evidence.
        customer_text = " ".join(evidence["customer_chain"]["snippets"])
        # Use the same generic org suffixes as product_project_evidence so
        # aerospace/materials/etc. customers also trigger backfill.
        customer_tokens = [
            token for token in _customer_org_tokens(customer_text)
            if not _is_issuer_name(token, issuer_names)
        ]
        if not any(token in existing_text for token in customer_tokens[:6]):
            return True
    if evidence.get("sales_model", {}).get("present"):
        if "经销" not in existing_text and "直销" not in existing_text and "买断式" not in existing_text:
            return True
    if evidence.get("frequency_coverage", {}).get("present"):
        if not any(token in existing_text for token in ("2G", "3G", "4G", "5G", "Wi-Fi", "频段")):
            return True
    return False


def _is_issuer_name(candidate: str, issuer_names: set[str]) -> bool:
    """Return True if candidate matches or is contained by an issuer name."""
    if not issuer_names:
        return False
    candidate = candidate.strip()
    for name in issuer_names:
        if candidate in name or name in candidate:
            return True
    return False


def _extracted_product_names(evidence: Dict[str, Any]) -> List[str]:
    """Return a small set of product/tech names extracted from evidence snippets."""
    names: List[str] = []
    snippets = []
    for bucket in ("product_lines", "project_statuses"):
        snippets.extend((evidence.get(bucket) or {}).get("snippets", []))
    text = " ".join(snippets)
    # Match technical-looking tokens such as L-PAMiD, RedCap, AEC-Q104, Phase8L.
    for match in re.finditer(
        r"[A-Z][A-Za-z0-9/-]*\d+[A-Za-z0-9/-]*|"
        r"[A-Z][a-z]+[A-Z][a-z]+|"
        r"[A-Z]+-[A-Za-z0-9-]+",
        text,
    ):
        token = match.group(0)
        if token not in names and len(token) >= 2:
            names.append(token)
    return names


def _backfill_rd_section_from_fulltext(
    sections: List[Dict[str, Any]],
    item_map: Dict[str, Any],
) -> None:
    rd_section = next((section for section in sections if section.get("title") == "研发与技术进展"), None)
    if not rd_section or rd_section.get("judgments"):
        return
    judgment, refs = _rd_judgment_from_fulltext(item_map)
    if not judgment or not refs:
        return
    rd_section["judgments"] = [{
        "judgment": judgment,
        "evidence_refs": refs,
        "confidence": 72,
    }]


def _rd_judgment_from_fulltext(item_map: Dict[str, Any]) -> tuple[str, List[str]]:
    hard_parts: List[str] = []
    tech_parts: List[str] = []
    refs: List[str] = []
    seen_rd_staff_counts: set[str] = set()

    def add(part: str, ref: str, *, bucket: str = "hard") -> None:
        target = tech_parts if bucket == "tech" else hard_parts
        if part and part not in target:
            target.append(part)
        if ref and ref not in refs:
            refs.append(ref)

    for ref, item in item_map.items():
        text = str(item.get("text", ""))
        normalized = _clean_line(text)
        rd_spend = re.search(
            r"(?:EDA\s*领域)?研发投入(?:为|金额)?\s*([\d,\.]+)\s*万元",
            normalized,
        )
        rd_ratio = re.search(r"占营业收入比例为\s*([\d,\.]+)\s*%", normalized)
        if rd_spend:
            part = f"研发投入为 {rd_spend.group(1)} 万元"
            if rd_ratio:
                part += f"，占营业收入比例为 {rd_ratio.group(1)}%"
            add(part, ref)

        expensed = re.search(r"费用化研发投入\s*([\d,\.]+)", normalized)
        capitalized = re.search(r"资本化研发投入\s*([\d,\.]+)", normalized)
        if expensed:
            add(f"费用化研发投入 {expensed.group(1)}", ref)
        if capitalized:
            add(f"资本化研发投入 {capitalized.group(1)}", ref)

        ip_summary = re.search(
            r"拥有\s*([\d,\.]+)\s*项发明专利[、，]\s*([\d,\.]+)\s*项实用新型专利"
            r"[、，]\s*([\d,\.]+)\s*项集成电路布图设计",
            normalized,
        )
        if not ip_summary:
            ip_summary = re.search(
                r"拥有\s*([\d,\.]+)\s*项发明专利[、，]\s*([\d,\.]+)\s*项实用\s*新\s*型专利"
                r"[、，]\s*([\d,\.]+)\s*项集成电路布图设计",
                normalized,
            )
        patent = re.search(r"发明专利\s*([\d,\.]+)\s*项", normalized)
        utility = re.search(r"实用新型专利\s*([\d,\.]+)\s*项", normalized)
        layout = re.search(r"集成电路布图设计(?:登记|专有权)?\s*([\d,\.]+)\s*项", normalized)
        authorized_patent = re.search(r"授权专利\s*([\d,\.]+)\s*项", normalized)
        software_copyright = re.search(r"软件著作权\s*([\d,\.]+)\s*项", normalized)
        ip_parts = []
        if ip_summary:
            ip_parts.extend([
                f"发明专利 {ip_summary.group(1)} 项",
                f"实用新型专利 {ip_summary.group(2)} 项",
                f"集成电路布图设计登记 {ip_summary.group(3)} 项",
            ])
        elif authorized_patent or software_copyright:
            if authorized_patent:
                ip_parts.append(f"授权专利 {authorized_patent.group(1)} 项")
            if software_copyright:
                ip_parts.append(f"软件著作权 {software_copyright.group(1)} 项")
        elif patent:
            ip_parts.append(f"发明专利 {patent.group(1)} 项")
            if utility:
                ip_parts.append(f"实用新型专利 {utility.group(1)} 项")
            if layout:
                ip_parts.append(f"集成电路布图设计登记 {layout.group(1)} 项")
        if ip_parts:
            add("知识产权储备包括" + "、".join(ip_parts), ref)

        rd_staff = re.search(
            r"研发人员(?:的数量（人）|数量(?:（人）)?)\s*([\d,\.]+)",
            normalized,
        )
        if not rd_staff:
            rd_staff = re.search(r"研发技术人员\s*([\d,\.]+)\s*人", normalized)
        rd_staff_ratio = re.search(
            r"(?:研发人员数量占公司总人数的比例（%）|占(?:公司|员工)?总数(?:的比例)?(?:\s*为)?\s*)"
            r"([\d,\.]+)\s*%?",
            normalized,
        )
        if rd_staff:
            rd_staff_key = rd_staff.group(1).replace(",", "")
            if rd_staff_key in seen_rd_staff_counts:
                continue
            seen_rd_staff_counts.add(rd_staff_key)
            part = f"研发人员数量 {rd_staff.group(1)} 人"
            if rd_staff_ratio:
                part += f"，占公司总人数比例 {rd_staff_ratio.group(1)}%"
            add(part, ref)

        tech_progress = re.search(r"((?:Phase8L|RedCap|L-PAMiD)[^。；;]{0,90}(?:量产|供货|验证|导入))", normalized)
        if tech_progress and not tech_parts:
            add(f"技术/产品进展包括{tech_progress.group(1)}", ref, bucket="tech")

    parts = hard_parts[:5] + tech_parts[:1]
    if not parts:
        return "", []
    judgment = (
        "研发与技术进展补充判断：" + "；".join(parts[:6]) +
        "。这些研发投入、资本化和知识产权指标说明技术迭代仍是后续收入转化与利润率修复的重要观察点。"
    )
    return judgment, refs[:3]


def _customer_order_judgment_from_required_metrics(metrics: Dict[str, Any]) -> str:
    parts = []
    customer = metrics.get("customer_concentration") or {}
    supplier = metrics.get("supplier_concentration") or {}
    sales_modes = metrics.get("sales_mode_rows") or []
    if customer.get("present"):
        values = []
        if customer.get("top_five_percentage"):
            values.append(f"前五名客户占比{_metric_cell(customer.get('top_five_percentage'))}")
        if customer.get("largest_percentage"):
            values.append(f"第一大客户占比{_metric_cell(customer.get('largest_percentage'))}")
        if values:
            parts.append("、".join(values))
    if supplier.get("present"):
        values = []
        if supplier.get("top_five_percentage"):
            values.append(f"前五名供应商占比{_metric_cell(supplier.get('top_five_percentage'))}")
        if supplier.get("largest_percentage"):
            values.append(f"第一大供应商占比{_metric_cell(supplier.get('largest_percentage'))}")
        if values:
            parts.append("、".join(values))
    for row in sales_modes[:2]:
        label = str(row.get("label", ""))
        revenue = _metric_cell(row.get("revenue"))
        yoy = _metric_cell(row.get("revenue_yoy"))
        row_text = f"{label}收入{revenue}" if label and revenue else ""
        if row_text and yoy:
            row_text += f"、同比{yoy}"
        if row_text:
            parts.append(row_text)
    if not parts:
        return ""
    return "客户与订单结构补充判断：" + "；".join(parts) + "。这些指标说明订单、渠道或供应链集中度需要在后续报告中单独跟踪。"


def _refs_for_required_metric_backfill(item_map: Dict[str, Any]) -> List[str]:
    preferred_usages = (
        "fulltext_management_discussion",
        "fulltext_financial_snapshot",
        "fulltext_financial_notes",
    )
    refs = [
        ref for ref, item in item_map.items()
        if item.get("usage") in preferred_usages
    ]
    return refs[:1] or list(item_map.keys())[:1]


def _deduplicate_financial_risks(risks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    seen_content = set()
    deduped: List[Dict[str, Any]] = []
    for risk in risks:
        key = _risk_semantic_key(risk)
        if key in seen:
            continue
        content_key = _risk_content_key(risk)
        if content_key and content_key in seen_content:
            continue
        if _is_duplicate_collection_of_cashflow(risk, deduped):
            continue
        seen.add(key)
        if content_key:
            seen_content.add(content_key)
        deduped.append(risk)
    return deduped


def _risk_content_key(risk: Dict[str, Any]) -> str:
    text = " ".join([
        str(risk.get("summary", "")),
        str(risk.get("mechanism", "")),
    ])
    text = _SPACE_RE.sub("", text)
    return text if len(text) >= 20 else ""


def _is_duplicate_collection_of_cashflow(
    risk: Dict[str, Any],
    existing_risks: List[Dict[str, Any]],
) -> bool:
    if risk.get("risk_type") != "receivables_collection":
        return False
    text = " ".join([
        str(risk.get("summary", "")),
        str(risk.get("mechanism", "")),
        " ".join(str(item) for item in risk.get("tracking_indicators") or []),
    ])
    if "经营" not in text or "现金流" not in text:
        return False
    refs = set(risk.get("evidence_refs") or [])
    for existing in existing_risks:
        if existing.get("risk_type") != "cash_flow_quality":
            continue
        existing_refs = set(existing.get("evidence_refs") or [])
        if refs and refs == existing_refs:
            return True
    return False


def _risk_semantic_key(risk: Dict[str, Any]) -> str:
    risk_type = str(risk.get("risk_type", ""))
    label = str(risk.get("custom_label", ""))
    text = f"{risk_type} {label}"
    if risk_type in {"audit_internal_control", "related_party_governance"}:
        return "governance_or_internal_control"
    if "诉讼" in text or "冻结" in text:
        return "litigation_contingency"
    if "治理" in text or "董事异议" in text or "内控" in text or "审计" in text:
        return "governance_or_internal_control"
    return risk_type if risk_type != "other_material_risk" else f"other:{label}"


def _normalize_risk_type(risk_type: str, risk: Dict[str, Any]) -> str:
    text = " ".join([
        str(risk.get("summary", "")),
        str(risk.get("mechanism", "")),
        " ".join(str(item) for item in risk.get("tracking_indicators") or []),
    ])
    inferred = _infer_risk_type_from_text(text)
    if risk_type not in FINANCIAL_RISK_CANDIDATE_TYPES:
        alias = _risk_type_alias(risk_type, inferred)
        if alias:
            risk_type = alias
    if inferred == "revenue_recognition" and risk_type in {"inventory_impairment", "other_material_risk", "profit_quality"}:
        return inferred
    if inferred in {"cash_flow_quality", "receivables_collection"} and risk_type in {
        "inventory_impairment",
        "revenue_recognition",
        "other_material_risk",
        "profit_quality",
    }:
        return inferred
    if inferred in {"supplier_concentration", "customer_concentration"} and risk_type in {
        "supplier_concentration",
        "customer_concentration",
        "other_material_risk",
        "profit_quality",
    }:
        return inferred
    return risk_type


def _risk_type_alias(risk_type: str, inferred: str) -> str:
    """Map common model-invented aliases back to the fixed risk taxonomy."""
    aliases = {
        "governance_risk": "related_party_governance",
        "governance": "related_party_governance",
        "audit_governance": "audit_internal_control",
        "internal_control": "audit_internal_control",
        "internal_control_risk": "audit_internal_control",
    }
    alias = aliases.get(risk_type, "")
    if inferred in {"audit_internal_control", "related_party_governance"}:
        return inferred
    return alias


def _infer_risk_type_from_text(text: str) -> str:
    # Supplemental backfill judgments should not spawn inferred risks.
    if text.startswith(("公司画像补充判断：", "客户与订单结构补充判断：", "研发与技术进展补充判断：")):
        return ""
    if any(token in text for token in ("收入确认", "经销", "价格调整", "冲减收入", "合同资产")):
        return "revenue_recognition"
    if any(token in text for token in ("前五名客户", "前五大客户", "客户A", "客户集中")):
        return "customer_concentration"
    if any(token in text for token in ("前五名供应商", "前五大供应商", "供应商集中", "供应商采购", "采购总额", "台积电")):
        return "supplier_concentration"
    if any(token in text for token in ("存货", "库存", "跌价")):
        return "inventory_impairment"
    if any(token in text for token in ("经营活动现金流", "经营现金流", "现金流量净额", "现金流与净利润")):
        return "cash_flow_quality"
    if any(token in text for token in ("回款", "应收账款", "应收票据", "商业承兑", "航信", "电汇")):
        return "receivables_collection"
    if any(token in text for token in ("在建工程", "购建固定资产", "资本开支", "转固", "产能利用率")):
        return "capex_capacity"
    if any(token in text for token in ("资产减值", "设备减值", "减值损失")):
        return "asset_impairment"
    if any(token in text for token in ("交易性金融资产", "理财", "投资收益", "公允价值变动")):
        return "financial_asset_dependency"
    if any(token in text for token in ("政府补助", "其他收益")):
        return "government_grant_dependency"
    if any(token in text for token in ("商誉", "并购", "收购")):
        return "goodwill_impairment"
    if any(token in text for token in ("汇率", "外币", "香港", "海外")):
        return "fx_overseas_exposure"
    if any(token in text for token in ("内控", "内部控制", "审计意见", "强调事项")):
        return "audit_internal_control"
    if any(token in text for token in ("董事异议", "董事会异议", "治理", "关联交易")):
        return "related_party_governance"
    if any(token in text for token in ("诉讼", "冻结资金", "财产保全")):
        return "litigation_contingency"
    if any(token in text for token in ("扣非", "净利润", "毛利率", "增收不增利", "利润质量")):
        return "profit_quality"
    if any(token in text for token in ("研发投入", "研发费用", "研发资本化", "客户导入")):
        return "rd_conversion"
    return ""


def _is_positive_observation_without_risk(risk_type: str, text: str) -> bool:
    if risk_type != "profit_quality":
        return False
    positive_markers = (
        "同比增长",
        "均实现增长",
        "盈利质量改善",
        "经营改善",
        "毛利率提升",
    )
    risk_markers = (
        "扣非净利润同比下降",
        "扣非下降",
        "扣非为负",
        "亏损",
        "经营活动现金流",
        "经营现金流",
        "现金流",
        "低于净利润",
        "背离",
        "毛利率下降",
        "毛利率下滑",
        "非经常性",
        "政府补助",
        "投资收益",
        "公允价值",
        "不可持续",
        "承压",
        "减值",
    )
    risk_patterns = (
        r"扣非[^。；]{0,80}同比(?:下降|减少|下滑|为负)",
        r"毛利率[^。；]{0,80}(?:下降|减少|下滑)",
        r"经营(?:活动)?现金流[^。；]{0,80}(?:下降|减少|下滑|为负|低于)",
    )
    has_positive = any(marker in text for marker in positive_markers)
    has_risk_marker = any(marker in text for marker in risk_markers)
    has_risk_pattern = any(re.search(pattern, text) for pattern in risk_patterns)
    return has_positive and not has_risk_marker and not has_risk_pattern


def _importance_for_inferred_risk(risk_type: str) -> str:
    if risk_type in {"customer_concentration", "inventory_impairment", "cash_flow_quality"}:
        return "high"
    return "medium"


def _mechanism_for_inferred_risk(risk_type: str) -> str:
    mechanisms = {
        "customer_concentration": "客户或订单节奏变化会放大收入、回款和产能利用率波动。",
        "supplier_concentration": "关键供应商价格、产能或交付变化会影响成本、交付和毛利率。",
        "inventory_impairment": "库存消化不及预期可能导致跌价准备增加，并压制后续毛利率和利润。",
        "cash_flow_quality": "经营现金流与利润背离会影响盈利质量和现金回收持续性判断。",
        "receivables_collection": "回款方式和应收票据变化会影响现金流稳定性与信用风险。",
        "capex_capacity": "资本开支和在建工程转固后，若需求不足会带来折旧和产能利用率压力。",
        "asset_impairment": "资产减值反映部分资产预期收益下降，可能影响后续利润质量。",
        "financial_asset_dependency": "理财和公允价值收益不具备经营持续性，可能扰动利润。",
        "audit_internal_control": "内控或审计异常会增加财务信息质量和治理风险。",
        "related_party_governance": "治理分歧或关联事项会影响决策效率和信息透明度。",
        "profit_quality": "利润增速、毛利率或扣非利润变化会影响盈利质量和持续性判断。",
        "revenue_recognition": "经销、价格调整或合同条款会增加收入确认估计的不确定性。",
        "rd_conversion": "研发投入需要通过新产品放量和客户导入转化，否则会持续压制利润率。",
        "goodwill_impairment": "并购标的经营不及预期时，商誉减值会直接冲减利润。",
        "fx_overseas_exposure": "外币结算和海外收入占比会放大汇率波动对收入及财务费用的影响。",
        "litigation_contingency": "诉讼、冻结或监管事项可能带来资金占用、赔付或声誉影响。",
        "government_grant_dependency": "补助和其他收益不具备经营持续性，可能扰动利润质量。",
    }
    return mechanisms.get(risk_type, "该事项可能影响后续经营质量、利润波动或信息披露透明度。")


def _tracking_indicators_for_inferred_risk(risk_type: str) -> List[str]:
    indicators = {
        "customer_concentration": ["第一大客户收入占比", "前五大客户收入占比", "订单节奏"],
        "supplier_concentration": ["前五大供应商采购占比", "主要供应商价格", "交付周期"],
        "inventory_impairment": ["存货余额", "库存量", "跌价准备", "毛利率"],
        "cash_flow_quality": ["经营活动现金流量净额", "净利润", "经营现金流/净利润"],
        "receivables_collection": ["应收账款余额", "应收票据余额", "回款方式"],
        "capex_capacity": ["在建工程", "购建长期资产现金流", "产能利用率", "折旧摊销"],
        "asset_impairment": ["资产减值损失", "减值资产类型", "后续转回或新增计提"],
        "financial_asset_dependency": ["交易性金融资产", "投资收益", "公允价值变动收益"],
        "audit_internal_control": ["内控审计意见", "整改进展", "资金管理制度执行"],
        "related_party_governance": ["董事异议", "关联交易", "诉讼进展"],
        "profit_quality": ["收入增速", "扣非净利润", "毛利率", "经营现金流"],
        "revenue_recognition": ["经销收入占比", "价格调整金额", "收入冲减", "合同资产"],
        "rd_conversion": ["研发投入", "研发费用率", "新产品收入贡献", "客户导入进度"],
        "goodwill_impairment": ["商誉余额", "并购标的业绩", "减值测试假设"],
        "fx_overseas_exposure": ["境外收入占比", "汇兑损益", "外币资产负债"],
        "litigation_contingency": ["诉讼进展", "冻结资金", "预计负债"],
        "government_grant_dependency": ["政府补助", "其他收益", "扣非净利润"],
    }
    return indicators.get(risk_type, ["相关风险证据", "后续披露变化"])


def _is_generic_risk_mechanism(text: str) -> bool:
    generic_markers = (
        "该风险已在年报证据中出现",
        "需要在后续报告中关注其变化",
        "相关风险证据",
    )
    return any(marker in text for marker in generic_markers)


def _is_generic_tracking_indicators(indicators: List[str]) -> bool:
    if not indicators:
        return True
    compact = {indicator.strip() for indicator in indicators if indicator.strip()}
    return compact <= {"相关风险证据", "后续披露变化"}


def _build_item_map(fulltext_pack: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    item_map: Dict[str, Dict[str, Any]] = {}
    for index, block in enumerate(fulltext_pack.get("blocks") or []):
        if not isinstance(block, dict):
            continue
        block_id = block.get("id") or f"fulltext-{index}"
        item_map[str(block_id)] = block
    return item_map


def _normalize_custom_label(value: Any) -> str:
    label = sanitize_text(str(value or ""))
    if label.lower() in {"none", "null", "n/a", "na"} or label in {"无", "不适用", "无自定义标签"}:
        return ""
    return label


def _extract_json_payload(raw_text: str) -> str:
    text = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    if text.startswith("{"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1].strip()
    return text


def _reject_invalid_evidence_refs(refs: Any, item_map: Dict[str, Any]) -> None:
    if not isinstance(refs, list) or not refs:
        raise PeriodicReportFulltextError("invalid evidence_refs")
    for ref in refs:
        if not isinstance(ref, str) or ref not in item_map:
            raise PeriodicReportFulltextError("invalid evidence_refs")


def _reject_illegal_content(parsed: Dict[str, Any]) -> None:
    text = _stringify_values(parsed).lower()
    for substring in ("confirmed_fact", "fact_candidate", "核心事实", "已证实"):
        if substring in text:
            raise PeriodicReportFulltextError(f"illegal content detected: {substring!r}")


def _stringify_values(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " ".join(_stringify_values(value) for value in obj.values())
    if isinstance(obj, list):
        return " ".join(_stringify_values(value) for value in obj)
    return ""


def _escape_md(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _render_audit_ref_lines(
    refs: List[str],
    item_map: Dict[str, Any],
    max_excerpt_chars: int,
) -> List[str]:
    lines: List[str] = []
    for ref in refs:
        item = item_map.get(str(ref))
        if not item:
            lines.extend([f"### 证据 {ref}", "", "未找到对应证据块。", ""])
            continue
        section = _escape_md(str(item.get("section") or item.get("title") or ""))
        usage = _escape_md(str(item.get("usage") or ""))
        excerpt = _escape_md(_audit_excerpt(str(item.get("text") or ""), max_excerpt_chars))
        lines.extend([
            f"### 证据 {ref}",
            "",
            f"- section：{section}",
            f"- usage：{usage}",
            f"> {excerpt}",
            "",
        ])
    return lines


def _audit_excerpt(text: str, max_chars: int) -> str:
    cleaned = _clean_line(text)
    if max_chars <= 0 or len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip() + "..."


def _render_required_metrics_lines(metrics: Dict[str, Any] | None) -> List[str]:
    if not isinstance(metrics, dict):
        return []
    lines = ["## 必备经营指标摘录", ""]

    segment_rows = metrics.get("segment_rows") or []
    if segment_rows:
        lines.extend([
            "### 分产品/业务毛利率",
            "",
            "| 项目 | 收入 | 收入同比 | 毛利率 | 毛利率变化 |",
            "|------|------|----------|--------|------------|",
        ])
        for row in segment_rows:
            lines.append(
                "| {label} | {revenue} | {revenue_yoy} | {gross_margin} | {gross_margin_delta} |".format(
                    label=_escape_md(str(row.get("label", ""))),
                    revenue=_escape_md(_metric_cell(row.get("revenue"))),
                    revenue_yoy=_escape_md(_metric_cell(row.get("revenue_yoy"))),
                    gross_margin=_escape_md(_metric_cell(row.get("gross_margin"))),
                    gross_margin_delta=_escape_md(_metric_cell(row.get("gross_margin_delta"))),
                )
            )
        lines.append("")

    inventory_rows = metrics.get("inventory_rows") or []
    if inventory_rows:
        lines.extend([
            "### 产销库存",
            "",
            "| 项目 | 生产量 | 销售量 | 库存量 | 库存同比 |",
            "|------|--------|--------|--------|----------|",
        ])
        for row in inventory_rows:
            lines.append(
                "| {label} | {production} | {sales} | {inventory} | {inventory_yoy} |".format(
                    label=_escape_md(str(row.get("label", ""))),
                    production=_escape_md(_metric_cell(row.get("production_volume"))),
                    sales=_escape_md(_metric_cell(row.get("sales_volume"))),
                    inventory=_escape_md(_metric_cell(row.get("inventory_volume"))),
                    inventory_yoy=_escape_md(_metric_cell(row.get("inventory_yoy"))),
                )
            )
        lines.append("")

    for title, key in (("分地区", "region_rows"), ("销售模式", "sales_mode_rows")):
        rows = metrics.get(key) or []
        if not rows:
            continue
        lines.extend([
            f"### {title}",
            "",
            "| 项目 | 收入 | 收入同比 | 毛利率 |",
            "|------|------|----------|--------|",
        ])
        for row in rows:
            lines.append(
                "| {label} | {revenue} | {revenue_yoy} | {gross_margin} |".format(
                    label=_escape_md(str(row.get("label", ""))),
                    revenue=_escape_md(_metric_cell(row.get("revenue"))),
                    revenue_yoy=_escape_md(_metric_cell(row.get("revenue_yoy"))),
                    gross_margin=_escape_md(_metric_cell(row.get("gross_margin"))),
                )
            )
        lines.append("")

    concentration_lines = []
    for label, key in (("客户集中度", "customer_concentration"), ("供应商集中度", "supplier_concentration")):
        concentration = metrics.get(key) or {}
        if not concentration.get("present"):
            continue
        concentration_lines.append(
            "- {label}：前五合计 {top_amount} / {top_pct}；第一大 {largest_amount} / {largest_pct}".format(
                label=label,
                top_amount=_metric_cell(concentration.get("top_five_amount")) or "未提取",
                top_pct=_metric_cell(concentration.get("top_five_percentage")) or "未提取",
                largest_amount=_metric_cell(concentration.get("largest_amount")) or "未提取",
                largest_pct=_metric_cell(concentration.get("largest_percentage")) or "未提取",
            )
        )
    if concentration_lines:
        lines.extend(["### 客户/供应商集中度", "", *concentration_lines, ""])

    if lines == ["## 必备经营指标摘录", ""]:
        lines.extend(["未提取到分产品、产销库存、区域/模式或客户供应商集中度表。", ""])
    return lines


def _render_required_financial_metrics_lines(metrics: Dict[str, Any] | None) -> List[str]:
    if not isinstance(metrics, dict):
        return []
    lines = ["## 必备财务风险指标摘录", ""]

    profit = metrics.get("profit_quality") or {}
    cash_flow = metrics.get("cash_flow_quality") or {}
    if profit or cash_flow:
        lines.extend(["### 盈利质量与现金流", ""])
        summary = []
        if profit.get("revenue"):
            summary.append(f"收入 {_metric_cell(profit.get('revenue'))}")
        if profit.get("revenue_yoy"):
            summary.append(f"收入同比 {_metric_cell(profit.get('revenue_yoy'))}")
        if profit.get("net_profit"):
            summary.append(f"归母净利润 {_metric_cell(profit.get('net_profit'))}")
        if profit.get("net_profit_yoy"):
            summary.append(f"归母净利润同比 {_metric_cell(profit.get('net_profit_yoy'))}")
        if profit.get("deducted_net_profit"):
            summary.append(f"扣非归母净利润 {_metric_cell(profit.get('deducted_net_profit'))}")
        if profit.get("deducted_net_profit_yoy"):
            summary.append(f"扣非同比 {_metric_cell(profit.get('deducted_net_profit_yoy'))}")
        if profit.get("gross_profit"):
            summary.append(f"毛利 {_metric_cell(profit.get('gross_profit'))}")
        if profit.get("gross_margin"):
            summary.append(f"毛利率 {_metric_cell(profit.get('gross_margin'))}")
        if profit.get("operating_loss"):
            summary.append(f"经营亏损 {_metric_cell(profit.get('operating_loss'))}")
        if profit.get("adjusted_net_loss"):
            summary.append(f"经调整亏损 {_metric_cell(profit.get('adjusted_net_loss'))}")
        if profit.get("rd_expense"):
            summary.append(f"研发开支 {_metric_cell(profit.get('rd_expense'))}")
        if cash_flow.get("operating_cash_flow"):
            summary.append(f"经营现金流 {_metric_cell(cash_flow.get('operating_cash_flow'))}")
        if cash_flow.get("operating_cash_flow_yoy"):
            summary.append(f"经营现金流同比 {_metric_cell(cash_flow.get('operating_cash_flow_yoy'))}")
        lines.extend([f"- {'；'.join(summary)}" if summary else "- 未提取到盈利质量/现金流数字。", ""])

    inventory = metrics.get("inventory_risk") or {}
    impairment = metrics.get("asset_impairment") or {}
    if inventory or impairment:
        lines.extend(["### 存货与减值", ""])
        items = []
        for label, key in (
            ("存货账面价值", "inventory_book_value"),
            ("存货账面价值同比", "inventory_book_value_yoy"),
            ("存货占总资产", "inventory_to_total_assets"),
            ("存货余额", "inventory_balance"),
            ("跌价准备", "inventory_impairment_allowance"),
            ("本期计提跌价", "current_impairment_provision"),
        ):
            if inventory.get(key):
                items.append(f"{label} {_metric_cell(inventory.get(key))}")
        if impairment.get("asset_impairment_loss"):
            items.append(f"资产减值损失 {_metric_cell(impairment.get('asset_impairment_loss'))}")
        lines.extend([f"- {'；'.join(items)}" if items else "- 未提取到存货/减值数字。", ""])

    receivables = metrics.get("receivables_collection") or {}
    supplier = metrics.get("supplier_concentration") or {}
    if receivables or supplier:
        lines.extend(["### 应收回款与供应商集中", ""])
        items = []
        for label, key in (
            ("应收账款", "accounts_receivable"),
            ("应收前五占比", "top_five_ar_percentage"),
            ("商业承兑汇票", "commercial_bills_receivable"),
        ):
            if receivables.get(key):
                items.append(f"{label} {_metric_cell(receivables.get(key))}")
        for label, key in (
            ("前五供应商采购额", "top_five_amount"),
            ("前五供应商占比", "top_five_percentage"),
            ("第一大供应商采购额", "largest_amount"),
            ("第一大供应商占比", "largest_percentage"),
        ):
            if supplier.get(key):
                items.append(f"{label} {_metric_cell(supplier.get(key))}")
        lines.extend([f"- {'；'.join(items)}" if items else "- 未提取到应收/供应商集中数字。", ""])

    capex = metrics.get("capex_capacity") or {}
    financial_assets = metrics.get("financial_assets") or {}
    leverage = metrics.get("leverage_liquidity") or {}
    goodwill = metrics.get("goodwill_risk") or {}
    if capex or financial_assets or leverage or goodwill:
        lines.extend(["### 资本开支、金融资产与杠杆", ""])
        items = []
        for label, group, key in (
            ("在建工程", capex, "construction_in_progress"),
            ("购建长期资产现金流", capex, "capex_cash_paid"),
            ("投资活动现金流", capex, "investing_cash_flow"),
            ("货币资金", financial_assets, "monetary_funds"),
            ("交易性金融资产", financial_assets, "trading_financial_assets"),
            ("交易性金融资产占总资产", financial_assets, "trading_financial_assets_to_total_assets"),
            ("公允价值金融资产", financial_assets, "fair_value_financial_assets"),
            ("短期借款", leverage, "short_term_borrowings"),
            ("借款", leverage, "borrowings"),
            ("应付账款同比", leverage, "accounts_payable_yoy"),
            ("资产负债率", leverage, "debt_ratio"),
            ("商誉", goodwill, "goodwill_balance"),
            ("商誉同比", goodwill, "goodwill_yoy"),
        ):
            if group.get(key):
                items.append(f"{label} {_metric_cell(group.get(key))}")
        lines.extend([f"- {'；'.join(items)}" if items else "- 未提取到资本开支/金融资产/杠杆数字。", ""])

    government = metrics.get("government_grants") or {}
    corporate = metrics.get("corporate_actions") or {}
    if government or corporate:
        lines.extend(["### 政府补助与资本动作", ""])
        items = []
        if government.get("government_grants_current"):
            items.append(f"政府补助 {_metric_cell(government.get('government_grants_current'))}")
        if corporate.get("placing_net_proceeds"):
            items.append(f"配售募资 {_metric_cell(corporate.get('placing_net_proceeds'))}")
        if corporate.get("acquisition_consideration"):
            items.append(f"收购对价 {_metric_cell(corporate.get('acquisition_consideration'))}")
        lines.extend([f"- {'；'.join(items)}" if items else "- 未提取到政府补助/资本动作数字。", ""])

    derived = metrics.get("derived_financial_metrics") or {}
    if derived:
        lines.extend(["### 派生风险比例", ""])
        items = []
        for label, key in (
            ("研发开支/收入", "rd_expense_to_revenue"),
            ("研发开支/毛利", "rd_expense_to_gross_profit"),
            ("经营现金净流出/现金", "operating_cash_outflow_to_cash"),
            ("贸易应收款项及应收票据/收入", "receivables_to_revenue"),
            ("收购对价/(现金+公允价值金融资产)", "acquisition_to_cash_and_fv_assets"),
            ("存货减值准备/存货原值", "inventory_impairment_allowance_to_inventory_if_available"),
        ):
            if derived.get(key):
                items.append(f"{label} {_metric_cell(derived.get(key))}")
        lines.extend([f"- {'；'.join(items)}" if items else "- 未提取到派生风险比例。", ""])

    audit = metrics.get("audit_governance") or {}
    if audit:
        lines.extend(["### 审计与治理信号", ""])
        items = []
        if audit.get("audit_opinion"):
            items.append(f"审计意见 {audit.get('audit_opinion')}")
        if audit.get("key_audit_matters"):
            items.append("关键审计事项 " + "、".join(str(item) for item in audit.get("key_audit_matters") or []))
        if audit.get("governance_dissent_present"):
            items.append("存在董事异议/反对/弃权信号")
        lines.extend([f"- {'；'.join(items)}" if items else "- 未提取到审计/治理信号。", ""])

    if lines == ["## 必备财务风险指标摘录", ""]:
        lines.extend(["未提取到现金流、存货跌价、应收、capex、金融资产、商誉或审计治理指标。", ""])
    return lines


def _metric_cell(cell: Any) -> str:
    if not isinstance(cell, dict):
        return ""
    text = str(cell.get("text") or "")
    unit = str(cell.get("unit") or "")
    normalized = str(cell.get("normalized") or "")
    if unit in {"万元", "千元", "百万元"} and normalized.endswith("万元"):
        return normalized
    if unit in {"%", "pct"}:
        return text
    if unit and text and not text.endswith(unit):
        return f"{text}{unit}"
    return text


def _clean_fulltext(text: str) -> str:
    text = text.replace("　", " ")
    text = _CITATION_RE.sub("", text)
    text = _URL_RE.sub("", text)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if _is_page_noise(stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _is_page_noise(line: str) -> bool:
    if re.match(r"^\d+\s*$", line):
        return True
    if "年度报告全文" in line and len(line) < 60:
        return True
    return False


def _clean_line(text: str) -> str:
    return _SPACE_RE.sub(" ", text).strip()


def _empty_fulltext_analysis(fulltext_pack: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": FULLTEXT_ANALYSIS_SCHEMA_VERSION,
        "source_type": "periodic_report_fulltext_analysis",
        "source_credit": 75,
        "verification_status": "professional_analysis",
        "claim_status": "professional_analysis",
        "knowledge_eligible": False,
        "report_eligible": False,
        "experimental": True,
        "report_type": fulltext_pack.get("report_type", "unknown"),
        "audit_status": fulltext_pack.get("audit_status", "unknown"),
        "company_profile": {},
        "cards": [],
        "sections": [],
        "financial_risks": [],
        "follow_up_questions": [],
    }
