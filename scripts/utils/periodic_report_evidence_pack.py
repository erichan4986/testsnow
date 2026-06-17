"""Deterministic evidence pack builder for A-share annual/semiannual reports.

The builder locates generic sections and tables, not industry-specific terms.
It returns bounded blocks suitable for a bounded LLM prompt.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


SCHEMA_VERSION = "periodic_report_evidence_pack.v1"

_MAX_BLOCKS = 30
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
    ("rd_investment_table", ("研发人员数量", "研发投入金额", "研发投入占营业收入比例", "研发投入资本化")),
    ("management_market_view", ("结构性分化", "产能过剩", "价格承压", "竞争加剧", "高端领域")),
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
    "cash_flow_capex_table": 6,
    "ar_customer_concentration_note": 7,
    "asset_impairment_note": 8,
    "audit_key_matters": 9,
    "governance_dissent": 10,
    "product_capacity_profile": 11,
    "sales_certification_model": 12,
    "management_market_view": 13,
    "segment_table": 14,
    "region_table": 15,
    "ar_aging_note": 16,
    "bills_receivable_note": 17,
    "inventory_note": 18,
    "capex_cip_note": 19,
    "financial_assets_note": 20,
    "restricted_assets_note": 21,
    "related_party_transactions": 22,
    "contingencies_litigation": 23,
    "subsequent_events": 24,
    "goodwill_note": 25,
    "government_grant_note": 26,
    "business_overview": 27,
    "business_model": 28,
    "industry_outlook": 29,
    "management_strategy": 30,
    "risk_disclosure": 31,
    "shareholder_structure": 32,
    "pledge": 33,
    "commitments": 34,
    "audit_opinion": 35,
    "income_statement": 36,
    "balance_sheet": 37,
    "cash_flow": 38,
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


def build_periodic_report_evidence_pack(
    text: str, *, report_type: str = "auto"
) -> Dict[str, Any]:
    """Build a deterministic evidence pack from annual/semiannual report text."""
    if not text:
        return _empty_pack(report_type)

    cleaned = _clean_text(text)
    detected_report_type = _detect_report_type(cleaned) if report_type == "auto" else report_type
    audit_status = _detect_audit_status(cleaned, detected_report_type)

    blocks: List[Dict[str, Any]] = []
    blocks.extend(_extract_section_blocks(cleaned))
    blocks.extend(_extract_keyword_blocks(cleaned))
    blocks.extend(_extract_table_blocks(cleaned))
    blocks = _dedupe_and_prioritize_blocks(blocks)
    blocks = blocks[:_MAX_BLOCKS]
    blocks = [_trim_block_text(b, _MAX_CHARS_PER_BLOCK) for b in blocks]

    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": detected_report_type,
        "audit_status": audit_status,
        "blocks": blocks,
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
                if excerpt:
                    blocks.append(_block(usage, section_name, pattern, excerpt, start, end))
                break
            else:
                continue
            break
    return blocks


def _extract_keyword_blocks(text: str) -> List[Dict[str, Any]]:
    """Extract bounded evidence windows for high-value annual-report signals."""
    blocks: List[Dict[str, Any]] = []
    seen_usage: set = set()
    section_matches = list(re.finditer(r"(第[一二三四五六七八九十]+[节章节][^\n\r]{0,40})", text))
    section_boundaries = [
        (
            match.start(),
            section_matches[index + 1].start() if index + 1 < len(section_matches) else len(text),
        )
        for index, match in enumerate(section_matches)
    ]

    for usage, patterns in _KEYWORD_USAGE_PATTERNS:
        if usage in seen_usage:
            continue
        for pattern in patterns:
            match = re.search(re.escape(pattern), text)
            if not match:
                continue
            start, end = _keyword_window(text, match.start(), usage)
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
            seen_usage.add(usage)
            break
    return blocks


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

    max_lines_by_usage = {
        "rd_investment_table": 36,
        "production_sales_inventory_table": 14,
        "cash_flow_capex_table": 20,
        "financial_summary_table": 46,
        "product_capacity_profile": 24,
        "sales_certification_model": 8,
    }
    max_lines = max_lines_by_usage.get(usage, 6)
    allow_numbered_subheadings = usage in {
        "product_capacity_profile",
        "sales_certification_model",
        "rd_investment_table",
        "production_sales_inventory_table",
        "cash_flow_capex_table",
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
    return start, end


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
    # Keep the first block per usage.
    by_usage: Dict[str, Dict[str, Any]] = {}
    for block in blocks:
        usage = block["usage"]
        if usage not in by_usage:
            by_usage[usage] = block
    # Stable id assignment per usage group.
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for block in by_usage.values():
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
    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": report_type if report_type != "auto" else "unknown",
        "audit_status": "unknown",
        "blocks": [],
    }
