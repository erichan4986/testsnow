"""Deterministic evidence pack builder for A-share annual/semiannual reports.

The builder locates generic sections and tables, not industry-specific terms.
It returns bounded blocks suitable for a bounded LLM prompt.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

if __package__:
    from .annual_argument_schema import CANONICAL_FAMILIES, canonical_family_for_usage, is_high_value_narrative_usage
    from .periodic_report_coverage_manifest import build_periodic_report_coverage_manifest
else:
    from annual_argument_schema import CANONICAL_FAMILIES, canonical_family_for_usage, is_high_value_narrative_usage
    from periodic_report_coverage_manifest import build_periodic_report_coverage_manifest


SCHEMA_VERSION = "periodic_report_evidence_pack.v1"

_MAX_BLOCKS = 48
_MAX_CHARS_PER_BLOCK = 2000

# Generic section headings mapped to usage labels.
_SECTION_USAGE_PATTERNS: List[Tuple[str, Tuple[str, ...]]] = [
    ("business_overview", ("报告期内公司从事的主要业务", "公司从事的主要业务", "主营业务")),
    ("industry_outlook", ("行业情况", "行业概况", "行业发展", "市场竞争格局")),
    ("business_model", ("经营模式", "盈利模式", "采购模式", "生产模式", "销售模式")),
    ("management_strategy", ("核心竞争力", "发展战略", "经营计划", "未来展望")),
    ("risk_disclosure", ("可能面对的风险", "公司可能面对的风险", "风险因素", "重大风险提示")),
    ("income_statement", ("合并利润表", "利润表", "营业收入", "营业成本")),
    ("balance_sheet", ("合并资产负债表", "资产负债表")),
    ("cash_flow", ("合并现金流量表", "现金流量表")),
    ("ar_aging_note", ("应收账款", "应收款项")),
    ("inventory_note", ("存货", "存货跌价")),
    ("capex_cip_note", ("在建工程", "固定资产", "产能")),
    ("goodwill_note", ("商誉", "商誉减值")),
    ("government_grant_note", ("政府补助", "其他收益")),
    ("restricted_assets_note", ("受限资产", "所有权或使用权受到限制的资产")),
    ("related_party_transactions", ("关联方", "关联交易")),
    ("contingencies_litigation", ("或有事项", "诉讼", "仲裁")),
    ("subsequent_events", ("资产负债表日后事项", "期后事项")),
    ("shareholder_structure", ("股东情况", "股份变动", "控股股东", "实际控制人")),
    ("pledge", ("质押", "股份质押")),
    ("commitments", ("承诺事项", "承诺及履行")),
    ("audit_opinion", ("审计意见", "审计报告")),
]

# Targeted but industry-neutral evidence windows.  These are not conclusions;
# they only preserve report snippets that are easy to lose in broad section
# slicing but important for downstream annual-report analysis.
_KEYWORD_USAGE_PATTERNS: List[Tuple[str, Tuple[str, ...]]] = [
    ("financial_summary_table", ("主要会计数据和财务指标",)),
    (
        "product_capacity_profile",
        (
            "主要产品及应用",
            "经营范围和主营业务",
            "主要产品",
            "产品矩阵",
            "可供销售产品",
            "产品主要包括",
            "规模化生产",
        ),
    ),
    ("sales_certification_model", ("合格供方目录", "定型认证", "最终用户认可", "直接销售模式")),
    ("production_sales_inventory_table", ("销售量", "生产量", "库存量")),
    (
        "rd_product_progress",
        (
            "报告期内的主要研发成果",
            "报告期内主要研发成果",
            "研发成果",
            "客户验证",
            "客户验证导入",
            "小批量交付",
            "小批量供货",
            "量产应用",
            "实现量产",
        ),
    ),
    ("rd_investment_table", ("研发人员数量", "研发投入金额", "研发投入占营业收入比例", "研发投入资本化")),
    (
        "industry_outlook",
        (
            "全球集成电路行业整体发展愈发景气",
            "行业景气度进入上行通道",
            "全球电池管理 IC 市场规模",
            "全球电池管理IC市场规模",
            "下游各应用领域具备较大的增长潜力",
            "国产替代前景",
            "先进封装占比",
            "Chiplet",
            "HBM 存储器封装",
            "ABF 载板",
            "高导热界面材料需求",
        ),
    ),
    ("management_market_view", ("结构性分化", "产能过剩", "价格承压", "竞争加剧", "高端领域")),
    (
        "market_demand_outlook",
        (
            "市场规模将增长",
            "复合增长率",
            "复合年增长率",
            "全球电池管理 IC 市场规模",
            "全球电池管理IC市场规模",
            "下游各应用领域具备较大的增长潜力",
            "国产替代前景",
            "高速光模块的需求",
            "未来数通光模块市场需求",
            "算力需求推动",
            "先进封装占比",
            "Chiplet",
            "HBM 存储器封装",
            "ABF 载板",
            "高导热界面材料需求",
        ),
    ),
    (
        "competitive_position",
        (
            "行业竞争格局及公司竞争地位",
            "公司所处的行业地位分析",
            "公司竞争地位",
            "公司行业地位",
            "主要的国内供应商",
            "具有一定竞争力",
            "市场份额持续成长",
            "竞争优势进一步强化",
        ),
    ),
    (
        "future_strategy",
        (
            "公司未来发展的展望",
            "公司发展战略",
            "2026 年度工作计划",
            "持续专注于 AI 数据中心",
            "持续专注于AI数据中心",
        ),
    ),
    (
        "profitability_commentary",
        (
            "毛利率较上年同期提升",
            "毛利率较上年同期增加",
            "毛利率同比提升",
            "毛利率同比增加",
            "毛利率同比小幅降低",
            "毛利率基本持平",
            "毛利率同比减少",
            "毛利率整体保持稳中有升",
            "盈利能力持续改善",
            "规模效应逐步释放",
            "成本规模效应",
            "高端产品出货占比提升",
        ),
    ),
    ("audit_key_matters", ("关键审计事项",)),
    ("ar_customer_concentration_note", ("应收账款余额前五名", "前五名客户占比", "信用集中风险")),
    ("bills_receivable_note", ("商业承兑汇票",)),
    ("asset_impairment_note", ("资产减值损失", "计提减值")),
    (
        "cash_flow_capex_table",
        (
            "经营活动产生的现金流量净额",
            "经营活动现金流入小计",
            "购建固定资产、无形资产和其他长期资产支付的现金",
            "投资活动产生的现金流量净额",
        ),
    ),
    ("financial_assets_note", ("交易性金融资产", "理财产品")),
    ("governance_dissent", ("提出异议", "投反对票", "弃权")),
]

# Priority order for selecting blocks when over cap. Lower = more important.
USAGE_PRIORITY = {
    "financial_summary_table": 0,
    "segment_margin_table": 0,
    "customer_supplier_table": 1,
    "supplier_concentration_table": 2,
    "production_sales_inventory_table": 3,
    "rd_investment_table": 4,
    "rd_table": 5,
    "rd_product_progress": 5,
    "cash_flow_capex_table": 6,
    "hk_income_statement_table": 0,
    "hk_financial_summary_table": 1,
    "hk_cash_flow_table": 6,
    "hk_product_progress": 5,
    "hk_business_overview": 11,
    "hk_customer_ecosystem": 12,
    "hk_market_outlook": 14,
    "hk_financial_commentary": 17,
    "ar_customer_concentration_note": 7,
    "asset_impairment_note": 8,
    "audit_key_matters": 9,
    "governance_dissent": 10,
    "product_capacity_profile": 11,
    "sales_certification_model": 12,
    "management_market_view": 13,
    "market_demand_outlook": 14,
    "competitive_position": 15,
    "future_strategy": 16,
    "profitability_commentary": 17,
    "segment_table": 18,
    "region_table": 19,
    "ar_aging_note": 20,
    "bills_receivable_note": 21,
    "inventory_note": 22,
    "capex_cip_note": 23,
    "financial_assets_note": 24,
    "restricted_assets_note": 25,
    "related_party_transactions": 26,
    "contingencies_litigation": 27,
    "subsequent_events": 28,
    "goodwill_note": 29,
    "government_grant_note": 30,
    "business_overview": 31,
    "business_model": 32,
    "industry_outlook": 33,
    "management_strategy": 34,
    "risk_disclosure": 35,
    "shareholder_structure": 36,
    "pledge": 37,
    "commitments": 38,
    "audit_opinion": 39,
    "income_statement": 40,
    "balance_sheet": 41,
    "cash_flow": 42,
}

# Generic table header / structural tokens used to anchor table regions.
_TABLE_HEADER_TOKENS = (
    "分产品",
    "分行业",
    "分地区",
    "分销售模式",
    "前五名客户",
    "前五名供应商",
    "主要销售客户",
    "主要供应商",
    "客户名称",
    "供应商名称",
    "主要研发项目名称",
    "研发投入",
    "研发人员数量",
    "研发投入金额",
    "研发投入占营业收入比例",
    "研发投入资本化",
    "生产量",
    "销售量",
    "库存量",
    "经营活动现金流入小计",
    "投资活动现金流入小计",
    "现金及现金等价物净增加额",
    "营业收入",
    "营业成本",
    "毛利率",
    "单位：元",
)

_TABLE_STRUCTURAL_TOKENS = {
    "分产品",
    "分行业",
    "分地区",
    "分销售模式",
    "其中：",
    "前五名客户",
    "前五名供应商",
    "主要销售客户",
    "主要供应商",
    "客户名称",
    "供应商名称",
    "序号",
    "主要研发项目名称",
    "研发项目",
    "研发投入",
    "研发费用",
    "研发人员数量",
    "研发投入金额",
    "研发投入占营业收入比例",
    "研发投入资本化",
    "生产量",
    "销售量",
    "库存量",
    "经营活动现金流入小计",
    "经营活动产生的现金流量净额",
    "投资活动现金流入小计",
    "购建固定资产、无形资产和其他长期资产支付的现金",
    "投资活动产生的现金流量净额",
    "现金及现金等价物净增加额",
    "项目目的",
    "项目进展",
    "拟达到的目标",
    "营业收入",
    "营业成本",
    "毛利率",
    "销售额",
    "采购额",
    "占年度",
    "合计",
    "单位：元",
    "2025 年",
    "2024 年",
    "2023 年",
    "上年同期",
    "本期金额",
    "上期金额",
    "同比增减",
    "可批量供货",
    "项目目标已达成",
}

_TABLE_MAX_LINES = 70
_RD_TABLE_MAX_LINES = 180
_TABLE_MIN_DATA_LINES = 2
_MULTI_BLOCK_USAGE_LIMITS = {
    "product_capacity_profile": 3,
    "rd_product_progress": 3,
    "competitive_position": 2,
    "market_demand_outlook": 2,
    "profitability_commentary": 2,
    "hk_product_progress": 4,
    "hk_customer_ecosystem": 3,
    "hk_market_outlook": 3,
    "hk_financial_commentary": 3,
    "hk_business_overview": 2,
}
_PRE_CONTEXT_LINES_BY_USAGE = {
    "competitive_position": 3,
    "market_demand_outlook": 4,
    "profitability_commentary": 3,
}
_NO_SENTENCE_EXTENSION_USAGES = {
    "product_capacity_profile",
}


def build_periodic_report_evidence_pack(
    text: str, *, report_type: str = "auto"
) -> Dict[str, Any]:
    """Build a deterministic evidence pack from annual/semiannual report text."""
    if not text:
        return _empty_pack(report_type)

    cleaned = _clean_text(text)
    detected_report_type = _detect_report_type(cleaned) if report_type == "auto" else report_type
    audit_status = _detect_audit_status(cleaned, detected_report_type)

    extracted: List[Dict[str, Any]] = []
    extracted.extend(_extract_section_blocks(cleaned))
    extracted.extend(_extract_keyword_blocks(cleaned))
    extracted.extend(_extract_hk_statement_blocks(cleaned))
    extracted.extend(_extract_hk_narrative_blocks(cleaned))
    extracted.extend(_extract_table_blocks(cleaned))
    prioritized = _dedupe_and_prioritize_blocks(extracted)
    selected = _select_bounded_blocks(prioritized)
    document_style = _document_style(cleaned, detected_report_type)
    coverage = build_periodic_report_coverage_manifest(
        cleaned, report_type=detected_report_type, document_style=document_style,
        extracted_candidates=extracted, prioritized_candidates=prioritized, selected_blocks=selected,
    )
    blocks = [_trim_block_text(b, _MAX_CHARS_PER_BLOCK) for b in selected]

    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": detected_report_type,
        "audit_status": audit_status,
        "document_style": document_style,
        "blocks": blocks,
        "coverage_manifest": coverage,
    }


# ---------------------------------------------------------------------------
# Report-level metadata
# ---------------------------------------------------------------------------


def _detect_report_type(text: str) -> str:
    head = text[:5000]
    if "半年度报告" in head or "半年度" in head or "半年报" in head:
        return "semiannual_report"
    if "年度报告" in head or "年报" in head:
        return "annual_report"
    if "季度报告" in head:
        return "quarterly_report"
    if "业绩预告" in head:
        return "earnings_preview"
    return "unknown"


def _detect_audit_status(text: str, report_type: str) -> str:
    if report_type == "semiannual_report":
        if ("审阅报告" in text or "经审计" in text) and "未经审计" not in text:
            return "limited_review"
        return "interim_unaudited"
    if report_type == "annual_report":
        if _has_standard_unqualified_opinion(text):
            return "audited"
        if "审计意见" in text:
            return "audited_attention_required"
        return "audited_unknown"
    return "unknown"


def _has_standard_unqualified_opinion(text: str) -> bool:
    financial_opinion = re.search(r"(?<!内控)审计意见类型\s*(.{0,40})", text)
    if financial_opinion:
        opinion_text = financial_opinion.group(1)
        if "非标准" in opinion_text:
            return False
        if any(term in opinion_text for term in ("保留意见", "无法表示意见", "否定意见")) and "无保留意见" not in opinion_text:
            return False
        if "标准无保留意见" in opinion_text or "标准的无保留意见" in opinion_text:
            return True
        if "无保留意见" in opinion_text and "非标准" not in opinion_text:
            return True
    if any(term in text for term in ("无法表示意见", "否定意见")):
        return False
    if "保留意见" in text and "无保留意见" not in text:
        return False
    if any(term in text for term in ("标准无保留意见", "标准的无保留意见")):
        return True
    return "无保留意见" in text and "审计意见" in text


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------


def _extract_section_blocks(text: str) -> List[Dict[str, Any]]:
    """Locate generic section subheadings and extract bounded excerpts."""
    section_matches = list(re.finditer(r"(第[一二三四五六七八九十]+[节章节][^\n\r]{0,40})", text))
    section_boundaries: List[Tuple[int, int]] = []
    for index, match in enumerate(section_matches):
        start = match.start()
        end = section_matches[index + 1].start() if index + 1 < len(section_matches) else len(text)
        section_boundaries.append((start, end))

    blocks: List[Dict[str, Any]] = []
    seen_spans: set = set()

    for usage, patterns in _SECTION_USAGE_PATTERNS:
        # Search for the most specific pattern first by trying longer patterns.
        for pattern in sorted(patterns, key=len, reverse=True):
            for match in re.finditer(re.escape(pattern), text):
                start = match.start()
                section_name = _section_for_position(start, section_boundaries, text)
                # Find end at next major heading or reasonable boundary.
                end = _find_excerpt_end(text, start + len(pattern))
                span_key = (start, end)
                if span_key in seen_spans:
                    continue
                seen_spans.add(span_key)
                excerpt = text[start:end].strip()
                excerpt = _strip_boilerplate(excerpt)
                if len(excerpt) > _MAX_CHARS_PER_BLOCK:
                    excerpt = excerpt[: _MAX_CHARS_PER_BLOCK - 1].rstrip() + "…"
                if excerpt and _is_substantive_section_excerpt(usage, excerpt):
                    blocks.append(_block(usage, section_name, pattern, excerpt, start, end))
                    break
            else:
                continue
            break
    return blocks


def _extract_keyword_blocks(text: str) -> List[Dict[str, Any]]:
    """Extract bounded evidence windows for high-value annual-report signals."""
    blocks: List[Dict[str, Any]] = []
    usage_counts: Dict[str, int] = {}
    section_matches = list(re.finditer(r"(第[一二三四五六七八九十]+[节章节][^\n\r]{0,40})", text))
    section_boundaries = [
        (
            match.start(),
            section_matches[index + 1].start() if index + 1 < len(section_matches) else len(text),
        )
        for index, match in enumerate(section_matches)
    ]

    for usage, patterns in _KEYWORD_USAGE_PATTERNS:
        usage_limit = _MULTI_BLOCK_USAGE_LIMITS.get(usage, 1)
        for pattern in patterns:
            for match in re.finditer(re.escape(pattern), text):
                if usage_counts.get(usage, 0) >= usage_limit:
                    break
                start, end = _keyword_window(text, match.start(), usage)
                if _overlaps_existing_usage_span(blocks, usage, start, end):
                    continue
                excerpt = _strip_boilerplate(text[start:end].strip())
                if not excerpt or not _is_valid_keyword_excerpt(usage, excerpt):
                    continue
                blocks.append(_block(
                    usage,
                    _section_for_position(match.start(), section_boundaries, text),
                    pattern,
                    excerpt,
                    start,
                    end,
                ))
                usage_counts[usage] = usage_counts.get(usage, 0) + 1
            if usage_counts.get(usage, 0) >= usage_limit:
                break
    return blocks


def _overlaps_existing_usage_span(
    blocks: List[Dict[str, Any]],
    usage: str,
    start: int,
    end: int,
) -> bool:
    for block in blocks:
        if block.get("usage") != usage:
            continue
        span = block.get("source_span") or {}
        existing_start = int(span.get("start", -1))
        existing_end = int(span.get("end", -1))
        overlap = min(end, existing_end) - max(start, existing_start)
        if overlap <= 0:
            continue
        shorter = max(1, min(end - start, existing_end - existing_start))
        if overlap / shorter >= 0.6:
            return True
    return False


def _is_substantive_section_excerpt(usage: str, excerpt: str) -> bool:
    """Reject section heading fragments that do not include body text."""
    narrative_usages = {
        "business_overview",
        "industry_outlook",
        "business_model",
        "management_strategy",
        "risk_disclosure",
    }
    if usage not in narrative_usages:
        return True
    compact = re.sub(r"\s+", "", excerpt)
    empty_heading_fragments = (
        "经营模式、行业情况说明",
        "行业情况说明",
        "主营业务情况□适用√不适用",
    )
    if compact in empty_heading_fragments:
        return False
    if usage in {"industry_outlook", "business_model"} and len(compact) < 40:
        return False
    return True


def _extract_hk_statement_blocks(text: str) -> List[Dict[str, Any]]:
    """Extract primary HK financial statement snippets.

    HK annual reports often do not look like A-share table regions: they use
    Traditional labels and IFRS statement headings. Keep this extractor narrow
    and statement-scoped so generic labels like "收入" never anchor from raw
    narrative text.
    """
    blocks: List[Dict[str, Any]] = []
    specs = (
        (
            "hk_income_statement_table",
            ("下表載列截至", "下表载列截至", "綜合全面", "綜合損益表", "合併損益表", "综合损益表"),
            ("收入", "毛利", "年內虧損", "年内亏损"),
        ),
        (
            "hk_cash_flow_table",
            ("現金流量的概要", "现金流量的概要", "綜合現金流量表", "合併現金流量表", "综合现金流量表"),
            ("經營活動所用現金淨額", "经营活动所用现金净额", "經營活動產生的現金流量淨額", "经营活动产生的现金流量净额"),
        ),
    )
    for usage, headings, required_tokens in specs:
        for heading in headings:
            for match in re.finditer(re.escape(heading), text):
                start = match.start()
                start, end = _hk_statement_window(text, start)
                excerpt = _strip_boilerplate(text[start:end].strip())
                compact = re.sub(r"\s+", "", excerpt)
                if not excerpt or _is_hk_five_year_summary_window(excerpt):
                    continue
                if not any(re.sub(r"\s+", "", token) in compact for token in required_tokens):
                    continue
                blocks.append(_block(usage, "财务报告", heading, excerpt, start, end))
                break
            if any(block["usage"] == usage for block in blocks):
                break
    return blocks


def _hk_statement_window(text: str, start: int) -> Tuple[int, int]:
    """Return a bounded HK statement window starting at a statement heading."""
    next_heading = re.search(
        (
            r"\n\s*(?:"
            r"綜合(?:全面收益表|財務狀況表|權益變動表|現金流量表|損益表)|"
            r"合併(?:全面收益表|財務狀況表|權益變動表|現金流量表|損益表)|"
            r"综合(?:全面收益表|财务状况表|权益变动表|现金流量表|损益表)|"
            r"合并(?:全面收益表|财务状况表|权益变动表|现金流量表|损益表)|"
            r"流動資金及財務資源|流动资金及财务资源|"
            r"附註|附注|財務報表附註|财务报表附注"
            r")"
        ),
        text[start + 20:],
    )
    end = start + 20 + next_heading.start() if next_heading else start + _MAX_CHARS_PER_BLOCK
    return start, min(end, start + _MAX_CHARS_PER_BLOCK, len(text))


def _is_hk_five_year_summary_window(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    return "五年財務概要" in compact or "五年财务概要" in compact


# ---------------------------------------------------------------------------
# HK narrative block extraction (Traditional / Simplified)
# ---------------------------------------------------------------------------

# HK annual reports use Traditional headings and free-form management discussion
# paragraphs rather than A-share "第X节" sections and structured tables. The
# generic section/keyword extractors therefore find almost no narrative blocks
# for HK filings. This extractor classifies management-discussion paragraphs
# into a small set of HK narrative usages so the narrative cards layer can map
# them to existing card types. It is deliberately gated to HK-shaped text so it
# never fires on A-share reports.

_HK_REPORT_MARKERS = (
    "國際控股有限公司",
    "管理層討論及分析",
    "綜合損益表",
    "綜合全面收益表",
    "綜合現金流量表",
    "香港聯合交易所",
    "聯交所",
    "年年度報告",
    "業務回顧",
    "業務展望",
)

_HK_NARRATIVE_KEYWORDS: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "hk_product_progress": {
        "strong": (
            "華山", "华山", "武當", "武当", "A1000", "A2000", "C1200",
            "SoC", "SesameX", "NPU", "Robotaxi",
            "M2", "M2.1", "M2.5", "M2-her", "Hailuo", "海螺AI",
            "Speech", "Music", "Talkie", "星野", "MiniMax Agent",
            "Media Agent", "SWE-Bench", "OpenRouter", "HuggingFace",
        ),
        "support": (
            "芯片", "量產", "量产", "流片", "先進工藝", "先进工艺", "7nm",
            "搭載", "搭载", "車型", "车型", "定點", "定点", "送樣", "送样",
            "產品", "产品", "計算", "计算", "算力", "工藝", "工艺", "驗證", "验证",
            "模型", "大模型", "語言模型", "语言模型", "視頻模型", "视频模型",
            "語音模型", "语音模型", "音樂模型", "音乐模型", "多模態", "多模态",
            "全模態", "全模态", "工具調用", "工具调用", "深度搜索", "Token",
            "開源", "开源", "AI原生產品", "AI原生产品",
        ),
    },
    "hk_customer_ecosystem": {
        "strong": (
            "合作夥伴", "合作伙伴", "產業鏈", "产业链", "主機廠", "主机厂",
            "生態", "生态", "產學研", "产学研", "聯盟", "联盟",
            "企業客戶", "企业客户", "開發者", "开发者", "全球用戶", "全球用户",
            "付費客戶", "付费客户", "國際市場", "国际市场",
        ),
        "support": (
            "客戶", "客户", "合作", "夥伴", "伙伴", "共同推動", "共同推动",
            "頭部", "头部", "車企", "车企", "企業合作", "企业合作",
            "用戶", "用户", "訂閱", "订阅", "國家及地區", "国家及地区",
            "企業服務", "企业服务", "API", "開放平台", "开放平台",
        ),
    },
    "hk_market_outlook": {
        "strong": (
            "Robotaxi", "L2-L4", "業務展望", "业务展望", "展望未來", "展望未来",
            "平台型公司", "AI平台", "AI 平台", "智能體", "智能体",
            "Token吞吐能力", "智能供給", "智能供给", "應用層", "应用层",
            "產業格局", "产业格局", "技術壁壘", "技术壁垒",
            "產業生態格局", "产业生态格局",
        ),
        "support": (
            "展望", "未來", "未来", "規模化", "规模化", "商業化", "商业化",
            "滲透", "渗透", "賽道", "赛道", "市場", "市场", "趨勢", "趋势",
            "佈局", "布局", "機遇", "机遇", "放量", "L3", "L4",
            "模型能力", "變現模式", "变现模式", "商業化佈局", "商业化布局",
            "全球市場", "全球市场", "產業上限", "产业上限", "辦公", "办公",
            "編程", "编程", "晶圓代工", "晶圆代工", "半導體產業", "半导体产业",
        ),
    },
    "hk_financial_commentary": {
        "strong": ("毛利率", "毛利"),
        "support": (
            "收入", "營收", "营收", "虧損", "亏损", "同比", "銷售成本", "销售成本",
            "經營", "经营", "淨額", "净额", "百萬元", "百万元", "億元", "亿元",
            "盈利能力", "競爭力", "竞争力", "成本",
        ),
    },
    "hk_business_overview": {
        "strong": (
            "車規級", "车规级", "業務回顧", "业务回顾", "全棧", "全栈",
            "領先的", "领先的",
            "基礎模型", "基础模型", "AI原生產品", "AI原生产品",
            "開放平台", "开放平台", "全模態", "全模态", "AI基礎模型",
            "AI基础模型",
        ),
        "support": (
            "供應商", "供应商", "解決方案", "解决方案", "平台", "自有", "IP",
            "主要業務", "主要业务", "領先", "领先", "全棧式", "全栈式",
            "模型", "產品", "产品", "企業客戶", "企业客户", "消費者", "消费者",
            "全球化", "用戶", "用户", "MiniMax", "海螺AI", "Talkie", "星野",
        ),
    },
}

# Tie-break order when a paragraph scores equally for several usages. More
# specific usages win over generic overview.
_HK_NARRATIVE_TIE_BREAK = (
    "hk_product_progress",
    "hk_customer_ecosystem",
    "hk_market_outlook",
    "hk_financial_commentary",
    "hk_business_overview",
)

_HK_NARRATIVE_USAGE_LIMITS = {
    "hk_product_progress": 4,
    "hk_customer_ecosystem": 3,
    "hk_market_outlook": 3,
    "hk_financial_commentary": 3,
    "hk_business_overview": 2,
}

_HK_NARRATIVE_MIN_COMPACT_LENGTH = 60
_HK_NARRATIVE_MIN_SCORE = 3

# Forward-looking markers separate a market-outlook paragraph from a
# product-progress paragraph that happens to share product/segment vocabulary.
_HK_FORWARD_TOKENS = (
    "將", "将", "未來", "未来", "預計", "预计", "展望", "佈局", "布局",
    "規劃", "规划", "下一階段", "下一阶段", "2026", "2027",
    "邁進", "迈进", "機會", "机会",
)

_HK_NARRATIVE_NOISE_TOKENS = (
    "環境、社會及管治",
    "可持續性報告",
    "可持续性报告",
    "信息安全與隱私保護",
    "信息安全与隐私保护",
    "客戶隱私保護",
    "客户隐私保护",
    "產品責任",
    "产品责任",
    "ESG 工作小組",
    "核數師",
    "購股權",
    "董事袍金",
    "薪酬委員會",
    "提名委員會",
    "審核委員會",
    "關連交易",
    "釋義項",
    "重要提示",
    "財務摘要",
    "财务摘要",
    "過去四個財政年度",
    "过去四个财政年度",
    "資產及負債摘要",
    "资产及负债摘要",
    "千美元 千美元",
    "非《國際財務報告準則》計量指標",
    "非《国际财务报告准则》计量指标",
    "主要風險及不確定因素",
    "主要风险及不确定因素",
    "財務風險",
    "财务风险",
    "業績波動風險",
    "业绩波动风险",
    "毛利率和利潤波動等風險",
    "毛利率和利润波动等风险",
    "氣候變化風險",
    "气候变化风险",
    "風險 ╱ 機遇",
    "风险 ╱ 机遇",
    "前瞻性陳述的風險聲明",
    "前瞻性陈述的风险声明",
    "以識別前瞻性陳述",
    "以识别前瞻性陈述",
    "該等前瞻性陳述乃根據",
    "该等前瞻性陈述乃根据",
    "極端天氣",
    "极端天气",
    "五年業績概要",
    "五年业绩概要",
    "五年財務概要",
    "五年财务概要",
    "主要財務指標",
    "主要财务指标",
    "利潤表及現金流量表相關科目變動分析表",
    "利润表及现金流量表相关科目变动分析表",
    "損益數據",
    "损益数据",
    "合併損益及其他綜合收益表",
    "合并损益及其他综合收益表",
    "合併損益表",
    "合并损益表",
    "綜合損益及其他綜合收益表",
    "综合损益及其他综合收益表",
    "以下各方應佔年內利潤",
    "以下各方应占年内利润",
    "加權平均權益報酬率",
    "加权平均权益报酬率",
    "EBITDA利潤率",
    "EBITDA利润率",
    "每股盈利",
    "金融資產的收益及虧損",
    "金融资产的收益及亏损",
    "公允價值計量且其變動計入其他全面收益",
    "公允价值计量且其变动计入其他全面收益",
    "財務報表附註",
    "财务报表附注",
)

_HK_NARRATIVE_HEADING_TOKENS = (
    "業務回顧",
    "业务回顾",
    "業務展望",
    "业务展望",
    "管理層討論及分析",
    "管理层讨论及分析",
    "財務回顧",
    "财务回顾",
    "收入",
    "毛利及毛利率",
)

_HK_PAGE_MARKER_RES = (
    re.compile(
        r"\d{0,4}\s*[一-鿿]{2,24}控股有限公司\s*\d{4}\s*年年度報告"
        r"(?:[\s一-鿿]{0,16}（續）)?"
    ),
    re.compile(
        r"\d{0,4}\s*\d{4}\s*年年度報告\s*[一-鿿]{2,24}控股有限公司"
    ),
    re.compile(r"管理層討論及分析\s*（續）"),
)


def _looks_like_hk_report(text: str) -> bool:
    return any(marker in text for marker in _HK_REPORT_MARKERS)


def _strip_hk_page_markers(text: str) -> str:
    cleaned = text
    for pattern in _HK_PAGE_MARKER_RES:
        cleaned = pattern.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _is_hk_narrative_noise(para: str) -> bool:
    if any(token in para for token in _HK_NARRATIVE_NOISE_TOKENS):
        return True
    return _looks_like_hk_project_table_fragment(para)


def _looks_like_hk_project_table_fragment(para: str) -> bool:
    compact = re.sub(r"\s+", "", para)
    has_project_table_anchor = (
        bool(re.search(r"\d+(?:\.\d+)?(?:納米|纳米|微米|nm|NM|μm|um)", compact))
        or "研發項目表" in compact
        or "研发项目表" in compact
        or "持續研發項" in compact
        or "持续研发项" in compact
    )
    if not has_project_table_anchor:
        return False
    table_markers = (
        "PDK",
        "中國大陸領先",
        "中国大陆领先",
        "主要應用",
        "主要应用",
        "研發項",
        "研发项",
        "工藝平台",
        "工艺平台",
    )
    return sum(1 for token in table_markers if token in compact) >= 3


def _is_valid_narrative_paragraph(
    para: str,
    *,
    min_compact_length: int = _HK_NARRATIVE_MIN_COMPACT_LENGTH,
) -> bool:
    compact = re.sub(r"\s+", "", para)
    if len(compact) < min_compact_length:
        return False
    if not any(punct in para for punct in ("。", "；", "，")):
        return False
    return True


def _classify_hk_narrative_paragraph(para: str) -> Tuple[str, int]:
    forward = any(token in para for token in _HK_FORWARD_TOKENS)
    best_usage = ""
    best_score = 0
    for usage in _HK_NARRATIVE_TIE_BREAK:
        spec = _HK_NARRATIVE_KEYWORDS[usage]
        strong = sum(1 for token in spec["strong"] if token in para)
        support = sum(1 for token in spec["support"] if token in para)
        if strong == 0 and support < 2:
            continue
        if usage == "hk_product_progress" and strong == 0:
            progress_anchors = (
                "發佈", "发布", "推出", "完成", "導入", "导入", "量產", "量产",
                "流片", "送樣", "送样", "客戶驗證", "客户验证", "搭載", "搭载",
                "定點", "定点", "新產品", "新产品",
            )
            if not any(anchor in para for anchor in progress_anchors):
                continue
        score = strong * 3 + support
        if usage == "hk_market_outlook" and forward:
            score += 6
        if score < _HK_NARRATIVE_MIN_SCORE:
            continue
        if score > best_score:
            best_score = score
            best_usage = usage
    return best_usage, best_score


def _iter_narrative_paragraph_units(
    text: str,
    *,
    heading_tokens: Tuple[str, ...],
    clean_line,
) -> List[str]:
    """Return paragraph-like narrative units from line-oriented report text."""
    paragraphs: List[str] = []
    buffer: List[str] = []

    def flush() -> None:
        if not buffer:
            return
        paragraph = clean_line("".join(buffer))
        buffer.clear()
        if paragraph:
            paragraphs.append(paragraph)

    for raw_line in text.splitlines():
        line = clean_line(raw_line.strip())
        if not line or line.startswith("# Page"):
            flush()
            continue
        compact = re.sub(r"\s+", "", line)
        if compact in heading_tokens:
            flush()
            continue
        if len(compact) <= 14 and any(token in compact for token in heading_tokens):
            flush()
            continue
        buffer.append(line)
        if line.endswith(("。", "；", ";")) or len("".join(buffer)) >= _MAX_CHARS_PER_BLOCK:
            flush()
    flush()
    return paragraphs


def _iter_hk_narrative_paragraphs(text: str) -> List[str]:
    """Return paragraph-like HK narrative units from Jina or PDF text."""
    return _iter_narrative_paragraph_units(
        text,
        heading_tokens=_HK_NARRATIVE_HEADING_TOKENS,
        clean_line=_strip_hk_page_markers,
    )


def _build_scored_narrative_blocks(
    *,
    text: str,
    by_usage: Dict[str, List[Tuple[int, str]]],
    usage_limits: Dict[str, int],
    section: str,
) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    for usage, items in by_usage.items():
        items.sort(key=lambda item: -item[0])
        limit = usage_limits.get(usage, 1)
        for _score, para in items[:limit]:
            excerpt = para[:_MAX_CHARS_PER_BLOCK]
            start = max(text.find(para[:40]), 0)
            blocks.append(_block(usage, section, usage, excerpt, start, start + len(excerpt)))
    return blocks


def _extract_hk_narrative_blocks(text: str) -> List[Dict[str, Any]]:
    """Classify HK management-discussion paragraphs into narrative usages."""
    if not _looks_like_hk_report(text):
        return []

    by_usage: Dict[str, List[Tuple[int, str]]] = {}
    for para in _iter_hk_narrative_paragraphs(text):
        if not para:
            continue
        if not _is_valid_narrative_paragraph(para):
            continue
        if _is_hk_narrative_noise(para):
            continue
        usage, score = _classify_hk_narrative_paragraph(para)
        if not usage:
            continue
        by_usage.setdefault(usage, []).append((score, para))

    return _build_scored_narrative_blocks(
        text=text,
        by_usage=by_usage,
        usage_limits=_HK_NARRATIVE_USAGE_LIMITS,
        section="管理層討論及分析",
    )


def _is_valid_keyword_excerpt(usage: str, excerpt: str) -> bool:
    """Reject high-noise keyword windows before they enter the evidence pack."""
    compact = re.sub(r"\s+", "", excerpt)
    if usage == "cash_flow_capex_table":
        cash_flow_markers = (
            "投资活动现金流入小计",
            "投资活动产生的现金流量净额",
            "购建固定资产、无形资产和其他长期资产支付的现金",
            "现金及现金等价物净增加额",
        )
        return any(token in compact for token in cash_flow_markers)
    if usage == "industry_outlook":
        return any(token in compact for token in ("市场规模", "增长潜力", "国产替代", "行业景气", "复合年增长率", "终端市场", "先进封装", "Chiplet", "HBM", "ABF", "CoWoS", "高导热界面材料"))
    if usage == "market_demand_outlook":
        return any(token in compact for token in ("市场规模", "算力", "GPU", "ASIC", "光模块", "电池管理IC", "电池管理芯片", "国产替代", "增长潜力", "复合年增长率", "先进封装", "Chiplet", "HBM", "ABF", "CoWoS", "高导热界面材料"))
    if usage == "competitive_position":
        return any(token in compact for token in ("竞争优势", "行业集中度", "市场份额", "客户认可", "交付能力", "竞争力", "国内供应商", "广泛认可", "行业地位"))
    if usage == "future_strategy":
        if any(token in compact for token in ("目录", "利润分配预案", "注意投资风险", "重要提示")):
            return False
        return any(token in compact for token in ("AI数据中心", "1.6T", "3.2T", "工作计划", "国际化战略", "供应链", "下游市场需求", "产品结构升级", "技术研发投入", "产品线", "国产化替代"))
    if usage == "profitability_commentary":
        return any(token in compact for token in ("毛利率", "盈利能力", "规模效应"))
    if usage == "rd_product_progress":
        return any(
            token in compact
            for token in (
                "研发成果",
                "客户验证",
                "验证导入",
                "小批量交付",
                "小批量供货",
                "量产",
                "技术突破",
                "开发",
                "产品",
            )
        )
    if usage != "product_capacity_profile":
        return True
    audit_noise = (
        "关键审计事项",
        "存货跌价准备",
        "财务报表附注",
        "会计估计",
        "生产线上的半成品",
    )
    if any(token in compact for token in audit_noise):
        return False
    product_markers = (
        "主要产品",
        "主营业务",
        "经营范围",
        "产品矩阵",
        "可供销售产品",
        "产品主要包括",
        "规模化生产",
    )
    return any(token in compact for token in product_markers)


def _keyword_window(text: str, position: int, usage: str) -> Tuple[int, int]:
    """Return a bounded multi-line window around a keyword occurrence."""
    lines = text.splitlines(keepends=True)
    cursor = 0
    line_index = 0
    for index, line in enumerate(lines):
        next_cursor = cursor + len(line)
        if cursor <= position < next_cursor:
            line_index = index
            break
        cursor = next_cursor

    start_index = line_index
    # Include a short caption immediately above the hit.
    if start_index > 0:
        previous = lines[start_index - 1].strip()
        if previous and len(previous) <= 40 and not any(ch in previous for ch in "。，；！？"):
            start_index -= 1
    remaining_context_lines = _PRE_CONTEXT_LINES_BY_USAGE.get(usage, 0)
    while remaining_context_lines > 0 and start_index > 0:
        previous = lines[start_index - 1].strip()
        if not previous:
            start_index -= 1
            continue
        if previous in {"√适用 □不适用", "□适用 √不适用"}:
            break
        if re.match(r"^(?:第[一二三四五六七八九十]+[节章节]|[一二三四五六七八九十]+、|（[一二三四五六七八九十\d]+）|\(\d+\)|\d+[、．])", previous):
            break
        start_index -= 1
        remaining_context_lines -= 1

    max_lines_by_usage = {
        "rd_investment_table": 36,
        "production_sales_inventory_table": 14,
        "cash_flow_capex_table": 20,
        "financial_summary_table": 46,
        "product_capacity_profile": 24,
        "sales_certification_model": 8,
        "market_demand_outlook": 14,
        "competitive_position": 20,
        "future_strategy": 16,
        "profitability_commentary": 18,
        "rd_product_progress": 16,
    }
    max_lines = max_lines_by_usage.get(usage, 6)
    allow_numbered_subheadings = usage in {
        "product_capacity_profile",
        "sales_certification_model",
        "rd_investment_table",
        "production_sales_inventory_table",
        "cash_flow_capex_table",
        "competitive_position",
        "future_strategy",
        "rd_product_progress",
        "profitability_commentary",
    }

    end_index = min(len(lines), start_index + max_lines)
    for idx in range(line_index + 1, end_index):
        stripped = lines[idx].strip()
        if not stripped:
            continue
        heading_re = (
            r"^(?:第[一二三四五六七八九十]+[节章节])"
            if allow_numbered_subheadings
            else r"^(?:第[一二三四五六七八九十]+[节章节]|[一二三四五六七八九十]+、|（[一二三四五六七八九十\d]+）|\(\d+\)|\d+[、．])"
        )
        if idx > line_index + 1 and re.match(heading_re, stripped):
            end_index = idx
            break

    start = sum(len(line) for line in lines[:start_index])
    end = min(sum(len(line) for line in lines[:end_index]), start + _MAX_CHARS_PER_BLOCK)
    if usage not in _NO_SENTENCE_EXTENSION_USAGES:
        end = _extend_to_sentence_boundary(text, end, start + _MAX_CHARS_PER_BLOCK)
    return start, end


def _extend_to_sentence_boundary(text: str, end: int, hard_end: int) -> int:
    """Extend a keyword window to avoid cutting in the middle of a sentence."""
    if end >= len(text):
        return len(text)
    if text[:end].rstrip().endswith(("。", "；", ";")):
        return end

    limit = min(len(text), hard_end, end + 600)
    tail = text[end:limit]
    next_heading = re.search(
        r"\n\s*(?:第[一二三四五六七八九十]+[节章节]|[一二三四五六七八九十]+、|（[一二三四五六七八九十\d]+）|\(\d+\)|\d+[、．])",
        tail,
    )
    search_tail = tail[:next_heading.start()] if next_heading else tail
    positions = [
        pos
        for mark in ("。", "；", ";")
        if (pos := search_tail.find(mark)) >= 0
    ]
    if not positions:
        return end
    return end + min(positions) + 1


def _section_for_position(position: int, boundaries: List[Tuple[int, int]], text: str) -> str:
    for start, end in boundaries:
        if start <= position < end:
            heading_match = re.search(r"(第[一二三四五六七八九十]+[节章节][^\n\r]{0,40})", text[start:start + 60])
            if heading_match:
                return _clean_heading(heading_match.group(1))
    return ""


def _find_excerpt_end(text: str, start: int) -> int:
    # Look for next major section heading, next numbered subheading, or a reasonable sentence boundary.
    next_heading = re.search(r"\n\s*(?:第[一二三四五六七八九十]+[节章节]|\([一二三四五六七八九十]+\)|[一二三四五六七八九十]+、)", text[start:])
    end = start + (next_heading.start() if next_heading else 1200)
    # Also stop at a sentence boundary before max length if possible.
    window = text[start:end]
    sentence_end = max(window.rfind("。"), window.rfind("；"), window.rfind("\n"))
    if sentence_end > 40:
        end = start + sentence_end + 1
    return min(end, len(text))


def _split_sections(text: str) -> Dict[str, str]:
    pattern = re.compile(r"(第[一二三四五六七八九十]+[节章节][^\n\r]{0,40})")
    matches = list(pattern.finditer(text))
    sections: Dict[str, str] = {}
    if not matches:
        return sections
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        heading = _clean_heading(match.group(1))
        if not _is_valid_section_heading(heading):
            continue
        if heading in sections:
            continue
        sections[heading] = text[start:end].strip()
    return sections


def _extract_section_excerpt(content: str, heading: str) -> str:
    # Drop boilerplate and keep the first substantive chunk.
    cleaned = _strip_boilerplate(content)
    # Find first sentence-like chunk after heading.
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    result_lines: List[str] = []
    for line in lines:
        stripped_heading = _clean_heading(heading)
        if line == heading or _clean_heading(line) == stripped_heading:
            continue
        if _is_boilerplate(line):
            continue
        if len(line) >= 12:
            result_lines.append(line)
        if len("\n".join(result_lines)) >= _MAX_CHARS_PER_BLOCK:
            break
    if not result_lines:
        return cleaned[:_MAX_CHARS_PER_BLOCK].strip()
    return "\n".join(result_lines)[:_MAX_CHARS_PER_BLOCK].strip()


# ---------------------------------------------------------------------------
# Table extraction
# ---------------------------------------------------------------------------


def _extract_table_blocks(text: str) -> List[Dict[str, Any]]:
    """Find table-like regions and classify them by header/content keywords.

    Real annual reports often insert blank lines between table rows and use
    multi-line cells (especially for R&D project tables).  We therefore anchor
    on known table headers / structural lines, expand the region while the
    lines still look like part of the same table, and classify from the whole
    region.
    """
    lines = text.splitlines()
    blocks: List[Dict[str, Any]] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].strip()
        if not line or not _is_table_header_line(line):
            i += 1
            continue

        start = i
        end = i
        data_lines = 0
        seen_data_row = False
        is_rd_region = _is_rd_header_line(line)
        max_lines = _RD_TABLE_MAX_LINES if is_rd_region else _TABLE_MAX_LINES
        while end < n and (end - start) < max_lines:
            cur = lines[end].strip()
            if not cur:
                # Blank lines are common between table rows.  Only treat a blank
                # as a table boundary if we have already seen real data rows and
                # the next non-blank line looks like a fresh table header.
                next_non_blank = _next_non_blank(lines, end)
                if (
                    seen_data_row
                    and next_non_blank
                    and _is_fresh_table_header(next_non_blank)
                    and not _is_table_subheader(next_non_blank)
                    and not _looks_like_table_row(next_non_blank)
                ):
                    break
                end += 1
                continue
            if _is_table_terminator(cur):
                break
            if is_rd_region:
                # R&D project tables use multi-line cells; keep everything
                # until the next major heading.
                data_lines += 1
                seen_data_row = True
            elif _is_table_content_line(cur):
                # Count all structural / row lines as table content.
                data_lines += 1
                if _looks_like_table_row(cur):
                    seen_data_row = True
            else:
                break
            end += 1

        if data_lines < _TABLE_MIN_DATA_LINES:
            i += 1
            continue

        region_lines = [l.strip() for l in lines[start:end] if l.strip()]
        combined = "\n".join(region_lines)
        usage = _classify_table_region(combined, line)
        if not usage:
            i += 1
            continue

        table_text = "\n".join(region_lines)
        start_pos = sum(len(l) + 1 for l in lines[:start])
        end_pos = start_pos + len(table_text)
        blocks.append(_block(
            usage,
            _table_section_for_line(text, start_pos),
            table_text[:80],
            table_text,
            start_pos,
            end_pos,
        ))
        i = end
    return blocks


def _next_non_blank(lines: List[str], start: int) -> str:
    for i in range(start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped:
            return stripped
    return ""


# Fresh table-start tokens used to detect a boundary between adjacent tables
# separated by a blank line.  We match with startswith to avoid breaking on
# continuation header lines such as "序号  客户名称  ...".
_TABLE_BOUNDARY_TOKENS = (
    "分产品",
    "分行业",
    "分地区",
    "分销售模式",
    "前五名客户",
    "前五名供应商",
    "主要销售客户",
    "主要供应商",
    "客户名称",
    "供应商名称",
    "主要研发项目名称",
    "研发投入",
    "研发人员数量",
    "生产量",
    "销售量",
    "库存量",
    "经营活动现金流入小计",
    "经营活动产生的现金流量净额",
    "投资活动现金流入小计",
    "投资活动产生的现金流量净额",
    "现金及现金等价物净增加额",
)


def _is_fresh_table_header(line: str) -> bool:
    stripped = line.strip()
    # Strip optional leading enumeration such as "2、分地区" or "4、研发投入".
    stripped = re.sub(r"^\d+[、．]?\s*", "", stripped)
    return any(stripped.startswith(token) for token in _TABLE_BOUNDARY_TOKENS)


def _is_table_header_line(line: str) -> bool:
    # Avoid starting a table on a narrative sentence that merely mentions a
    # structural keyword (e.g. "...持续研发投入。").
    stripped = line.strip()
    if len(stripped) > 80:
        return False
    if any(ch in stripped for ch in "。，；：！？"):
        return False
    return any(token in stripped for token in _TABLE_HEADER_TOKENS)


def _is_rd_header_line(line: str) -> bool:
    return "主要研发项目名称" in line or ("研发项目" in line and "项目进展" in line)


def _is_table_content_line(line: str) -> bool:
    if _looks_like_table_row(line):
        return True
    if _is_table_subheader(line):
        return True
    if any(token in line for token in _TABLE_STRUCTURAL_TOKENS):
        return True
    # Allow short header-fragment lines (e.g. "年同期增减", "营业成本比上")
    # that have no sentence punctuation and look like column labels.
    stripped = line.strip()
    if len(stripped) <= 16 and not any(ch in stripped for ch in "。，；：！？"):
        return True
    return False


def _is_table_subheader(line: str) -> bool:
    return bool(re.search(r"^(?:其中[：:]|分产品|分行业|分地区|分销售模式)", line))


def _classify_table_region(combined: str, header_line: str) -> Optional[str]:
    """Classify a captured table region into a usage label."""
    compact = re.sub(r"\s+", "", combined)

    if all(token in compact for token in ("销售量", "生产量", "库存量")):
        return "production_sales_inventory_table"

    if (
        "研发人员数量" in compact
        or "研发投入金额" in compact
        or "研发投入占营业收入比例" in compact
        or "研发投入资本化" in compact
        or "资本化研发投入" in compact
    ):
        return "rd_investment_table"

    if (
        "购建固定资产、无形资产和其他长期资产支付的现金" in compact
        or "投资活动现金流入小计" in compact
        or "投资活动产生的现金流量净额" in compact
        or "现金及现金等价物净增加额" in compact
        or ("经营活动现金流入小计" in compact and "经营活动现金流出小计" in compact)
    ):
        return "cash_flow_capex_table"

    # Customer / supplier tables.
    region_head = combined[:160]
    if any(
        token in region_head
        for token in (
            "公司主要供应商情况",
            "前五名供应商",
            "主要供应商",
            "供应商名称",
            "供应商合计采购金额",
        )
    ):
        return "supplier_concentration_table"

    if any(
        token in combined
        for token in (
            "前五名客户",
            "主要销售客户",
            "客户名称",
        )
    ):
        return "customer_supplier_table"

    # R&D project tables.
    if "主要研发项目名称" in combined:
        return "rd_table"
    if ("研发项目" in combined or "研发投入" in combined or "研发费用" in combined) and (
        "项目进展" in combined or "项目目的" in combined or "项目" in combined
    ):
        return "rd_table"

    # Region-only table.
    if "分地区" in combined and "分产品" not in combined and "分行业" not in combined:
        return "region_table"

    # Product / segment tables.
    if "分产品" in combined or "分行业" in combined:
        if "毛利率" in combined and "营业成本" in combined:
            return "segment_margin_table"
        return "segment_table"

    # Fallback for margin tables that lack explicit 分产品/分行业 headers.
    if "营业收入" in combined and "营业成本" in combined and "毛利率" in combined:
        return "segment_margin_table"

    return None


def _looks_like_table_row(line: str) -> bool:
    # A table row has multiple whitespace-separated columns and a substantive
    # number (multi-digit, comma-separated, decimal, or percent).
    parts = line.split()
    if len(parts) < 3:
        return False
    # Require at least one numeric token that is not a single isolated digit.
    for match in re.finditer(r"[\d,]+(?:\.\d+)?%?", line):
        token = match.group(0)
        if len(token) >= 2 or "," in token or "." in token or "%" in token:
            return True
    return False


def _is_table_terminator(line: str) -> bool:
    terminators = (
        "注：",
        "注释",
        "数据来源",
        "（以下无正文",
        "第四节",
        "第五节",
        "第六节",
        "第七节",
        "第八节",
        "第九节",
        "第十节",
        "重要事项",
        "公司治理",
    )
    if any(term in line for term in terminators):
        return True
    # Major sub-headings that terminate a table region.
    if re.search(r"^##\s+[\d一二三四五六七八九十]", line):
        return True
    if re.search(r"^（\d+[）)]", line):
        return True
    if re.search(r"^第[一二三四五六七八九十]+[节章节]", line):
        return True
    # Numbered subsections like "4、研发投入" are not table content, unless the
    # line is itself a table caption that contains table structural keywords.
    if re.search(r"^\d+[、．]\s*[^\d]", line):
        if not any(token in line for token in _TABLE_STRUCTURAL_TOKENS):
            return True
    return False


def _table_section_for_line(text: str, position: int) -> str:
    prefix = text[:position]
    pattern = re.compile(r"(第[一二三四五六七八九十]+[节章节][^\n\r]{0,40})")
    matches = list(pattern.finditer(prefix))
    if matches:
        return _clean_heading(matches[-1].group(1))
    return "财务报告"


# ---------------------------------------------------------------------------
# Block utilities
# ---------------------------------------------------------------------------


def _block(
    usage: str,
    section: str,
    title: str,
    text: str,
    start: int,
    end: int,
) -> Dict[str, Any]:
    return {
        "id": f"{usage}-0",
        "usage": usage,
        "section": section,
        "title": title[:120],
        "text": text,
        "source_span": {"start": start, "end": end},
    }


def _dedupe_and_prioritize_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove near-duplicate blocks, assign stable ids, and sort by priority."""
    by_usage: Dict[str, List[Dict[str, Any]]] = {}
    for block in blocks:
        usage = block["usage"]
        limit = _MULTI_BLOCK_USAGE_LIMITS.get(usage, 1)
        group = by_usage.setdefault(usage, [])
        if len(group) < limit:
            group.append(block)
    # Stable id assignment per usage group.
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for group in by_usage.values():
        for block in group:
            grouped.setdefault(block["usage"], []).append(block)

    prioritized: List[Tuple[int, int, Dict[str, Any]]] = []
    for usage, group in grouped.items():
        priority = USAGE_PRIORITY.get(usage, 99)
        for index, block in enumerate(group):
            block["id"] = f"{usage}-{index}"
            prioritized.append((priority, index, block))
    prioritized.sort(key=lambda x: (x[0], x[1]))
    return [block for _, _, block in prioritized]


def _trim_block_text(block: Dict[str, Any], max_chars: int) -> Dict[str, Any]:
    text = block["text"]
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    block["text"] = text
    return block


def _document_style(text: str, report_type: str) -> str:
    if _looks_like_hk_report(text):
        return "hkex_annual"
    return "a_share_annual" if report_type in {"annual", "annual_report"} and any(token in text for token in ("管理层讨论与分析", "报告期内公司", "年度报告全文")) else "unknown"


def _has_complete_narrative_clause(text: str) -> bool:
    return any(len(clause.strip()) >= 24 for clause in re.split(r"[。；;]", re.sub(r"\s+", "", str(text or ""))))


def _reserved_narrative_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [block for family in CANONICAL_FAMILIES if (block := next((block for block in blocks if canonical_family_for_usage(block.get("usage")) == family and is_high_value_narrative_usage(block.get("usage")) and _has_complete_narrative_clause(block.get("text", ""))), None)) is not None]


def _select_bounded_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    selected_ids = {block["id"] for block in _reserved_narrative_blocks(blocks)}
    for block in blocks:
        if len(selected_ids) >= _MAX_BLOCKS:
            break
        selected_ids.add(block["id"])
    return [block for block in blocks if block["id"] in selected_ids]


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------


def _clean_text(text: str) -> str:
    text = text.replace("　", " ")
    text = re.sub(r"\[\^[^\]]+\]|\[\d+\]", "", text)
    return text


def _clean_heading(text: str) -> str:
    return re.sub(r"\s+", "", text).strip()


def _is_valid_section_heading(heading: str) -> bool:
    if not heading:
        return False
    if len(heading) < 4 or len(heading) > 32:
        return False
    if "..." in heading or "……" in heading:
        return False
    return True


def _strip_boilerplate(text: str) -> str:
    lines = text.splitlines()
    result: List[str] = []
    for line in lines:
        if _is_boilerplate(line):
            continue
        result.append(line)
    return "\n".join(result)


def _is_boilerplate(line: str) -> bool:
    boilerplate = (
        "本公司及董事会全体成员保证",
        "不存在虚假记载",
        "误导性陈述",
        "证券代码",
        "证券简称",
        "公告编号",
    )
    if any(token in line for token in boilerplate):
        return True
    stripped = line.strip()
    return stripped in {"目录", "目 录", "重要提示、目录和释义"}


def _empty_pack(report_type: str) -> Dict[str, Any]:
    normalized_type = report_type if report_type != "auto" else "unknown"
    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": normalized_type,
        "audit_status": "unknown",
        "document_style": "unknown",
        "blocks": [],
        "coverage_manifest": build_periodic_report_coverage_manifest(
            "", report_type=normalized_type, document_style="unknown",
            extracted_candidates=[], prioritized_candidates=[], selected_blocks=[]),
    }
