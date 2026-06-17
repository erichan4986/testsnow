"""Standalone periodic report extractor for A-share annual/semiannual reports.

The module is intentionally dependency-light. It reads already-extracted text
and produces structured observations that can be consumed by this repository or
used as a standalone JSON/Markdown artifact.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


SECTION_HEADING_RE = re.compile(r"(第[一二三四五六七八九十]+[章节][^\n\r]{0,40})")

MANAGEMENT_KEYWORDS = (
    "公司认为",
    "管理层",
    "行业",
    "景气",
    "竞争",
    "战略",
    "自主可控",
    "产品",
    "客户",
    "研发",
    "产能",
    "未来",
    "展望",
    "核心供应商",
    "自主创新",
    "工程化",
)

RISK_KEYWORDS = (
    "风险",
    "价格下降",
    "价格承压",
    "毛利率承压",
    "价格波动",
    "原材料价格",
    "技术迭代",
    "供应链",
    "地缘",
    "客户集中",
    "订单",
    "需求",
    "人才流失",
    "研发失败",
    "行业周期",
)

CAPEX_KEYWORDS = (
    "在建工程",
    "固定资产",
    "募投",
    "项目投入",
    "项目建设",
    "项目投产",
    "产能闲置",
    "产能利用率",
    "四期项目",
    "三期项目",
    "对外投资",
    "回购",
    "股权激励",
    "员工持股",
    "重大合同",
)

FORENSICS_NOT_EXTRACTED = (
    "应收票据/商业承兑结构",
    "合同资产/合同负债异动",
    "研发人员数量与人均研发投入",
    "商誉减值测试参数",
    "关联交易占比",
    "存货周转天数/应收周转天数趋势",
)


@dataclass(frozen=True)
class Metric:
    label: str
    value: Optional[float]
    growth: Optional[float] = None


def extract_periodic_report(
    text: str,
    *,
    report_type: str = "auto",
    industry: str = "generic",
    max_items_per_section: int = 8,
) -> Dict[str, Any]:
    """Extract structured observations from annual/semiannual report text."""

    cleaned = _clean_text(text)
    detected_report_type = _detect_report_type(cleaned) if report_type == "auto" else report_type
    sections = _split_sections(cleaned)

    items: List[Dict[str, Any]] = []
    items.extend(_extract_front_risks(sections, cleaned, max_items=max_items_per_section))
    items.extend(_extract_management_views(sections, cleaned, max_items=max_items_per_section))
    items.extend(_extract_business_structure(sections, cleaned, max_items=max_items_per_section))
    items.extend(_extract_capex_and_events(sections, cleaned, max_items=max_items_per_section))
    items.extend(_extract_financial_forensics(cleaned, industry=industry))

    return {
        "schema_version": "periodic_report_extractor.v1",
        "report_type": detected_report_type,
        "audit_status": _detect_audit_status(cleaned, detected_report_type),
        "industry": industry,
        "sections_found": list(sections.keys()),
        "forensics_notes": _build_forensics_notes(),
        "items": items,
    }


def render_markdown(result: Dict[str, Any]) -> str:
    """Render extractor result into a compact human-review Markdown report."""

    lines = [
        "# 定期报告摘录",
        "",
        f"- 报告类型：{result.get('report_type', 'unknown')}",
        f"- 审计状态：{result.get('audit_status', 'unknown')}",
        f"- 行业 profile：{result.get('industry', 'generic')}",
        "",
    ]

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in result.get("items", []) or []:
        grouped.setdefault(item.get("usage", "other"), []).append(item)

    section_titles = [
        ("risk_disclosure", "重大风险提示摘录", "公司披露的风险提示应与管理层展望交叉验证。"),
        ("management_view", "管理层讨论与分析摘录", "管理层观点可用于理解公司叙事，但不等同于外部确认事实。"),
        ("business_segment", "主营业务与产品线", "以下为年报披露的业务结构和产品线摘录，需结合收入结构与订单节奏验证。"),
        ("product_revenue_margin", "分产品收入与毛利率", "以下为规则识别的分产品收入、成本与毛利率线索，需回到原表复核列含义。"),
        ("customer_concentration", "客户结构与集中度", "客户集中度可解释订单弹性与回款风险，但需结合客户名称、账期和型号周期复核。"),
        ("rd_progress", "研发进展与技术突破", "研发进展来自年报表述，需结合专利、量产、客户验证和收入贡献继续核验。"),
        ("gross_margin_driver", "毛利率变化解释", "毛利率变化解释需拆分价格、成本、产品结构和产能利用率因素。"),
        ("capital_action", "资本开支与重要事项", "资本开支、回购、激励或重大合同需要与现金流、产能利用率和订单消化交叉验证。"),
        ("financial_forensics", "财报排雷观察", "以下为规则识别出的财务异常信号，需回到财报附注和同行数据继续核验。"),
    ]
    for usage, title, note in section_titles:
        rows = grouped.get(usage, [])
        if not rows:
            continue
        lines.extend([f"## {title}", "", f"> {note}", "", "| 等级 | 主题 | 证据 |", "|------|------|------|"])
        for item in rows:
            lines.append(
                "| {severity} | {title} | {evidence} |".format(
                    severity=_escape_md(item.get("severity", "info")),
                    title=_escape_md(item.get("title", "")),
                    evidence=_escape_md(item.get("evidence", "")),
                )
            )
        lines.append("")

    if len(lines) <= 6:
        lines.append("未抽取到高信号条目。")
    return "\n".join(lines).rstrip() + "\n"


def result_to_json(result: Dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)


def _detect_report_type(text: str) -> str:
    head = text[:5000]
    if "半年度报告" in head or "半年度" in head or "半年报" in head:
        return "semiannual_report"
    if "季度报告" in head:
        return "quarterly_report"
    if "业绩预告" in head:
        return "earnings_preview"
    if "年度报告" in head or "年报" in head:
        return "annual_report"
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


def _split_sections(text: str) -> Dict[str, str]:
    matches = list(SECTION_HEADING_RE.finditer(text))
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


def _extract_front_risks(
    sections: Dict[str, str], full_text: str, *, max_items: int
) -> List[Dict[str, Any]]:
    first_section = _find_section(sections, ("重要提示", "重大风险", "释义"))
    detail_section = _risk_detail_section(sections, full_text)
    source = "\n".join(chunk for chunk in (first_section, detail_section) if chunk) or full_text[:8000]
    sentences = _rank_sentences(source, RISK_KEYWORDS, max_items=max_items, max_chars=280)
    return [
        _item(
            usage="risk_disclosure",
            title="公司披露的重大风险",
            evidence=sentence,
            severity="medium",
            interpretation="这是公司在定期报告中披露的风险提示，应与管理层展望交叉验证。",
        )
        for sentence in sentences
    ]


def _extract_management_views(sections: Dict[str, str], full_text: str, *, max_items: int) -> List[Dict[str, Any]]:
    section = _find_section(sections, ("管理层讨论", "经营情况讨论", "主营业务分析"))
    if not section or _looks_like_toc_fragment(section):
        section = _management_fallback_section(full_text)
    if not section:
        return []
    sentences = _rank_sentences(section, MANAGEMENT_KEYWORDS, max_items=max_items, max_chars=420)
    return [
        _item(
            usage="management_view",
            title=_management_title(sentence),
            evidence=sentence,
            severity="info",
            interpretation="管理层观点可用于理解公司叙事，但不等同于外部确认事实。",
        )
        for sentence in sentences
    ]


def _extract_capex_and_events(sections: Dict[str, str], full_text: str, *, max_items: int) -> List[Dict[str, Any]]:
    source = _capex_source_section(sections, full_text)
    sentences = _rank_sentences(source, CAPEX_KEYWORDS, max_items=max_items, max_chars=320)
    return [
        _item(
            usage="capital_action",
            title=_capital_action_title(sentence),
            evidence=sentence,
            severity="info",
            interpretation="资本开支、回购、激励或重大合同需要与现金流、产能利用率和订单消化交叉验证。",
        )
        for sentence in sentences
    ]


def _extract_business_structure(sections: Dict[str, str], full_text: str, *, max_items: int) -> List[Dict[str, Any]]:
    source = _business_source_section(sections, full_text)
    items: List[Dict[str, Any]] = []
    items.extend(_extract_business_segments(source, max_items=max_items))
    items.extend(_extract_product_revenue_margin(full_text, max_items=max_items))
    items.extend(_extract_customer_structure(full_text))
    items.extend(_extract_rd_progress(source, max_items=max_items))
    items.extend(_extract_gross_margin_drivers(source, max_items=max_items))
    return items


def _extract_financial_forensics(full_text: str, *, industry: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    revenue = _metric_with_growth(full_text, ("营业收入", "营收"))
    ar = _metric_with_growth(full_text, ("应收账款", "应收款项"))
    inventory = _metric_with_growth(full_text, ("存货",))
    cip = _metric_with_growth(full_text, ("在建工程",))
    net_profit = _metric_value(full_text, ("归属于上市公司股东的净利润", "净利润"))
    deduct_profit = _metric_value(full_text, ("扣除非经常性损益后的净利润", "扣非净利润"))
    ocf = _metric_value(full_text, ("经营活动产生的现金流量净额", "经营现金流量净额"))
    rd_total = _metric_value(full_text, ("研发投入金额", "研发投入", "研发费用"))
    rd_capitalized = _metric_value(full_text, ("资本化研发投入", "开发支出"))
    inventory_impairment = _metric_value(full_text, ("存货跌价准备",))
    government_subsidy = _metric_value(full_text, ("计入当期损益的政府补助", "政府补助", "其他收益"))

    if revenue.growth is not None and ar.growth is not None and ar.growth > revenue.growth * 1.8:
        items.append(
            _financial_item(
                "应收账款增速显著高于营收增速",
                f"营业收入同比约{revenue.growth:.2f}%，应收账款同比约{ar.growth:.2f}%。",
                "营收增长可能伴随信用政策放宽或回款质量下降，需检查账龄和坏账计提。",
                severity="high",
            )
        )

    if net_profit is not None and deduct_profit is not None:
        gap_ratio = (net_profit - deduct_profit) / max(abs(net_profit), 1)
        if deduct_profit <= 0 < net_profit or gap_ratio > 0.15:
            items.append(
                _financial_item(
                    "扣非净利润弱于净利润",
                    f"净利润约{_fmt_amount(net_profit)}，扣非净利润约{_fmt_amount(deduct_profit)}。",
                    "需要拆分政府补助、投资收益等非经常性损益，观察主业造血能力。",
                    severity="high",
                )
            )

    if ocf is not None and net_profit is not None and (ocf < 0 <= net_profit or ocf < net_profit * 0.5):
        items.append(
            _financial_item(
                "经营现金流弱于利润",
                f"经营现金流净额约{_fmt_amount(ocf)}，净利润约{_fmt_amount(net_profit)}。",
                "利润含金量偏弱，需进一步核对应收、存货和收入确认节奏。",
                severity="high",
            )
        )

    if rd_total and rd_capitalized is not None:
        cap_rate = rd_capitalized / max(abs(rd_total), 1)
        if cap_rate >= 0.3:
            items.append(
                _financial_item(
                    "研发资本化率偏高",
                    f"研发投入约{_fmt_amount(rd_total)}，资本化研发投入约{_fmt_amount(rd_capitalized)}，资本化率约{cap_rate:.1%}。",
                    "科技企业需检查资本化条件、后续摊销和减值，避免当期利润被研发资本化美化。",
                    severity="medium",
                )
            )

    if inventory.growth is not None and revenue.growth is not None and inventory.growth > revenue.growth * 1.8:
        evidence = f"存货同比约{inventory.growth:.2f}%，营业收入同比约{revenue.growth:.2f}%"
        if inventory.value and inventory_impairment is not None:
            impairment_rate = inventory_impairment / max(abs(inventory.value), 1)
            evidence += f"，存货跌价准备/存货约{impairment_rate:.2%}"
            if impairment_rate < 0.05:
                title = "存货增长且跌价准备偏低"
            else:
                title = "存货增长快于营收"
        else:
            title = "存货增长快于营收"
        items.append(
            _financial_item(
                title,
                evidence + "。",
                _inventory_interpretation(industry),
                severity="high",
            )
        )

    if cip.growth is not None and cip.growth > 50:
        items.append(
            _financial_item(
                "在建工程快速增长",
                f"在建工程同比约{cip.growth:.2f}%。",
                "需跟踪转固节奏、折旧压力、产能利用率和项目投产后的订单消化。",
                severity="medium",
            )
        )

    if government_subsidy is not None and net_profit is not None and net_profit > 0:
        subsidy_ratio = government_subsidy / max(abs(net_profit), 1)
        if subsidy_ratio >= 0.3:
            items.append(
                _financial_item(
                    "政府补助占利润比例较高",
                    f"政府补助或其他收益约{_fmt_amount(government_subsidy)}，净利润约{_fmt_amount(net_profit)}，占比约{subsidy_ratio:.1%}。",
                    "需剥离政府补助观察主业盈利能力，防止利润主要依赖非经常性收益。",
                    severity="medium",
                )
            )

    customer_concentration = _customer_concentration_ratio(full_text)
    if customer_concentration is not None and customer_concentration >= 50:
        items.append(
            _financial_item(
                "客户集中度较高",
                f"前五大客户销售占比约{customer_concentration:.2f}%。",
                "需关注重点客户订单节奏、议价能力和回款风险。",
                severity="medium",
            )
        )

    ar_aging_ratio = _ar_aging_over_one_year_ratio(full_text)
    if ar_aging_ratio is not None and ar_aging_ratio >= 20:
        items.append(
            _financial_item(
                "应收账款账龄老化",
                f"一年以上应收账款占比约{ar_aging_ratio:.2f}%。",
                "需核对应收账龄、坏账计提政策和单项计提客户情况。",
                severity="high",
            )
        )

    restricted_assets = _restricted_assets_amount(full_text)
    if restricted_assets is not None:
        items.append(
            _financial_item(
                "受限资产需要关注",
                f"受限资产或受限货币资金约{_fmt_amount(restricted_assets)}。",
                "需查看受限原因、质押/保证金规模和真实可动用资金。",
                severity="medium",
            )
        )

    return items


def _metric_value(text: str, labels: Iterable[str]) -> Optional[float]:
    for label in labels:
        candidates = _metric_value_candidates(text, label)
        if candidates:
            return candidates[0]
    return None


def _metric_with_growth(text: str, labels: Iterable[str]) -> Metric:
    for label in labels:
        span_pattern = re.compile(re.escape(label) + r"(.{0,220})")
        span_match = span_pattern.search(text)
        if not span_match:
            continue
        span = span_match.group(1)
        number_matches = _plain_numbers(span)
        growth_match = re.search(r"(?:同比|增长|增减|变动|比上年同期|本年比上年)[^-\d]{0,40}(-?[\d,]+(?:\.\d+)?)\s*%", span)
        if not growth_match:
            percent_matches = re.findall(r"-?[\d,]+(?:\.\d+)?\s*%", span)
            if percent_matches:
                growth_match_value = percent_matches[-1].replace("%", "").strip()
            else:
                growth_match_value = None
        else:
            growth_match_value = growth_match.group(1)
        value = number_matches[0] if number_matches else None
        growth = _parse_number(growth_match_value) if growth_match_value else None
        if growth is None and len(number_matches) >= 2:
            current = number_matches[0]
            previous = number_matches[1]
            if current is not None and previous not in (None, 0) and _span_allows_growth_fallback(span):
                growth = (current - previous) / abs(previous) * 100
        return Metric(label=label, value=value, growth=growth)
    return Metric(label=next(iter(labels), ""), value=None, growth=None)


def _build_forensics_notes() -> Dict[str, Any]:
    return {
        "interpretation": "未列为风险不代表无风险；以下项目当前版本尚未结构化抽取。",
        "not_extracted": list(FORENSICS_NOT_EXTRACTED),
    }


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
    standard_terms = ("标准无保留意见", "标准的无保留意见")
    if any(term in text for term in standard_terms):
        return True
    return "无保留意见" in text and "审计意见" in text


def _is_valid_section_heading(heading: str) -> bool:
    if not heading:
        return False
    if _looks_like_toc_fragment(heading):
        return False
    if len(heading) < 4 or len(heading) > 32:
        return False
    return True


def _metric_value_candidates(text: str, label: str) -> List[float]:
    pattern = re.compile(re.escape(label) + r"(.{0,320})")
    candidates: List[float] = []
    for match in pattern.finditer(text):
        span = match.group(1)
        if not _span_looks_like_metric_value(span):
            continue
        number = _first_number_with_optional_unit(span)
        if number is not None:
            candidates.append(number)
    return candidates


def _span_looks_like_metric_value(span: str) -> bool:
    if "元" in span or "万元" in span or "亿元" in span:
        return True
    return bool(re.search(r"-?[\d,]+(?:\.\d+)?", span))


def _first_number_with_optional_unit(span: str) -> Optional[float]:
    unit_pattern = re.compile(r"(\(?-?[\d,]+(?:\.\d+)?\)?)\s*(亿元|万元|元)?")
    for match in unit_pattern.finditer(span):
        raw = match.group(1)
        value = _parse_number(raw)
        if value is None:
            continue
        unit = match.group(2) or ""
        if unit == "亿元":
            return value * 100_000_000
        if unit == "万元":
            return value * 10_000
        return value
    return None


def _span_allows_growth_fallback(span: str) -> bool:
    return any(token in span for token in ("上年同期", "上期", "期初", "上年末", "本期", "期末"))


def _find_section(sections: Dict[str, str], keywords: Iterable[str]) -> str:
    for heading, content in sections.items():
        if any(keyword in heading for keyword in keywords):
            return content
    return ""


def _capex_source_section(sections: Dict[str, str], full_text: str) -> str:
    """Return sections likely to contain valuable capex/event disclosures."""
    wanted = ("重要事项", "管理层讨论", "经营情况讨论", "主营业务分析")
    chunks = [content for heading, content in sections.items() if any(keyword in heading for keyword in wanted)]
    if chunks:
        return "\n".join(chunks)
    return full_text


def _business_source_section(sections: Dict[str, str], full_text: str) -> str:
    chunks = []
    for heading, content in sections.items():
        if any(keyword in heading for keyword in ("管理层讨论", "经营情况讨论", "主营业务分析")):
            chunks.append(content)
    fallback = _management_fallback_section(full_text)
    if fallback:
        chunks.append(fallback)
    if chunks:
        return "\n".join(chunks)
    return full_text[:30000]


def _risk_detail_section(sections: Dict[str, str], full_text: str) -> str:
    """Return text around the real risk discussion, not only the front pointer."""
    chunks = [
        content
        for heading, content in sections.items()
        if "风险" in heading and "释义" not in heading
    ]
    if chunks:
        return "\n".join(chunks)

    anchors = (
        "公司可能面对的风险",
        "可能面对的风险",
        "风险因素",
        "重大风险提示",
        "主要风险",
        "风险及应对措施",
    )
    starts = [full_text.find(anchor) for anchor in anchors if full_text.find(anchor) >= 0]
    if not starts:
        return ""
    start = min(starts)
    end_candidates = [
        position
        for marker in ("第四节", "第五节", "第六节", "公司治理", "重要事项", "财务报告")
        for position in [full_text.find(marker, start + 20)]
        if position > start
    ]
    end = min(end_candidates) if end_candidates else min(len(full_text), start + 8000)
    return full_text[start:end]


def _extract_business_segments(source: str, *, max_items: int) -> List[Dict[str, Any]]:
    product_tokens = ("业务", "碳纤维", "织物", "预浸料", "功能材料", "结构材料", "主要生产")
    result: List[Dict[str, Any]] = []
    seen = set()
    for sentence in _split_sentences(source):
        sentence = _strip_report_heading_noise(sentence)
        if _is_boilerplate(sentence) or _looks_like_toc_fragment(sentence):
            continue
        if "业务分析" in sentence and "报告期内" not in sentence:
            continue
        if not any(token in sentence for token in product_tokens):
            continue
        if not ("业务" in sentence or "主要生产" in sentence or "产品" in sentence):
            continue
        key = sentence[:80]
        if key in seen:
            continue
        seen.add(key)
        result.append(
            _item(
                usage="business_segment",
                title=_business_segment_title(sentence),
                severity="info",
                evidence=_truncate(sentence, 420),
                interpretation="业务结构摘录需与分产品收入、毛利率和客户订单节奏交叉验证。",
            )
        )
        if len(result) >= max_items:
            break
    return result


def _extract_product_revenue_margin(full_text: str, *, max_items: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen_products = set()
    for raw_line in full_text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line or "%" not in line:
            continue
        parsed = _parse_product_margin_line(line)
        if not parsed:
            continue
        product, revenue, cost, margin, revenue_growth, margin_change = parsed
        if product in seen_products:
            continue
        seen_products.add(product)
        rows.append(
            _item(
                usage="product_revenue_margin",
                title=f"产品收入与毛利率：{product}",
                severity="info",
                evidence=(
                    f"{product}：营业收入{_fmt_amount(revenue)}，营业成本{_fmt_amount(cost)}，"
                    f"毛利率{margin:.2f}%，营收同比{revenue_growth:.2f}%，毛利率同比{margin_change:.2f}pct。"
                ),
                interpretation="分产品收入和毛利率是判断业务结构变化的核心输入。",
            )
        )
        if len(rows) >= max_items:
            break
    return rows


def _extract_customer_structure(full_text: str) -> List[Dict[str, Any]]:
    ratio = _customer_concentration_ratio(full_text)
    if ratio is None:
        sentence = _find_sentence_with_any(full_text, ("客户集中度高", "客户明确且集中度高", "前五名客户"))
        if not sentence:
            return []
        evidence = _truncate(sentence, 280)
    else:
        evidence = f"前五大客户销售占比约{ratio:.2f}%。"
    return [
        _item(
            usage="customer_concentration",
            title="客户集中度",
            severity="medium" if ratio is not None and ratio >= 50 else "info",
            evidence=evidence,
            interpretation="客户集中度可解释订单弹性、议价能力和回款风险。",
        )
    ]


def _extract_rd_progress(source: str, *, max_items: int) -> List[Dict[str, Any]]:
    strong_keywords = ("重大突破", "关键技术", "T1100", "首次", "专利", "量产", "工业化")
    sentences = []
    for sentence in _rank_sentences(source, strong_keywords, max_items=max_items * 2, max_chars=380):
        sentence = _strip_report_heading_noise(sentence)
        if any(keyword in sentence for keyword in strong_keywords):
            sentences.append(sentence)
        if len(sentences) >= max_items:
            break
    return [
        _item(
            usage="rd_progress",
            title=_rd_progress_title(sentence),
            severity="info",
            evidence=sentence,
            interpretation="研发进展需结合客户验证、量产状态、专利和收入贡献复核。",
        )
        for sentence in sentences
    ]


def _extract_gross_margin_drivers(source: str, *, max_items: int) -> List[Dict[str, Any]]:
    keywords = ("毛利率", "价格因素", "产品价格", "成本", "原材料", "折旧", "产能利用率", "产品结构")
    sentences = [
        _strip_report_heading_noise(sentence)
        for sentence in _rank_sentences(source, keywords, max_items=max_items * 2, max_chars=320)
        if "毛利率" in sentence or "价格因素" in sentence or "产品价格" in sentence or "产能利用率" in sentence
    ][:max_items]
    return [
        _item(
            usage="gross_margin_driver",
            title="毛利率变化解释",
            severity="info",
            evidence=sentence,
            interpretation="毛利率变化需拆分价格、成本、产品结构和产能利用率因素。",
        )
        for sentence in sentences
    ]


def _management_fallback_section(text: str) -> str:
    anchors = (
        "一、报告期内公司从事的主要业务",
        "报告期内公司从事的主要业务",
        "主营业务分析",
        "核心竞争力分析",
    )
    starts = [text.find(anchor) for anchor in anchors if text.find(anchor) >= 0]
    if not starts:
        return ""
    start = min(starts)
    end_candidates = [
        position
        for marker in ("第四节", "第五节", "重要事项", "公司治理")
        for position in [text.find(marker, start + 20)]
        if position > start
    ]
    end = min(end_candidates) if end_candidates else min(len(text), start + 20000)
    return text[start:end]


def _rank_sentences(text: str, keywords: Iterable[str], *, max_items: int, max_chars: int = 180) -> List[str]:
    candidates = _split_sentences(text)
    scored: List[Tuple[int, int, str]] = []
    for index, sentence in enumerate(candidates):
        if _is_boilerplate(sentence):
            continue
        if _looks_like_toc_fragment(sentence):
            continue
        if _is_non_applicable_checkbox_noise(sentence):
            continue
        if _is_pointer_only_sentence(sentence):
            continue
        score = sum(1 for keyword in keywords if keyword in sentence)
        if score <= 0:
            continue
        scored.append((score, -index, sentence))
    scored.sort(reverse=True)
    result: List[str] = []
    seen = set()
    for _, _, sentence in scored:
        key = sentence[:60]
        if key in seen:
            continue
        seen.add(key)
        result.append(_truncate(sentence, max_chars))
        if len(result) >= max_items:
            break
    return result


def _split_sentences(text: str) -> List[str]:
    normalized = re.sub(r"\s+", " ", text)
    pieces = re.split(r"(?<=[。！？；;])\s*|\n+", normalized)
    return [piece.strip(" 　：:") for piece in pieces if len(piece.strip()) >= 18]


def _item(
    *,
    usage: str,
    title: str,
    evidence: str,
    severity: str,
    interpretation: str,
) -> Dict[str, Any]:
    return {
        "usage": usage,
        "title": title,
        "severity": severity,
        "evidence": evidence,
        "interpretation": interpretation,
    }


def _financial_item(title: str, evidence: str, interpretation: str, *, severity: str) -> Dict[str, Any]:
    return _item(
        usage="financial_forensics",
        title=title,
        severity=severity,
        evidence=evidence,
        interpretation=interpretation,
    )


def _management_title(sentence: str) -> str:
    if "行业" in sentence or "景气" in sentence:
        return "管理层行业判断"
    if "研发" in sentence or "技术" in sentence:
        return "管理层研发与技术判断"
    if "客户" in sentence:
        return "管理层客户与需求判断"
    return "管理层经营判断"


def _capital_action_title(sentence: str) -> str:
    if "回购" in sentence:
        return "回购或股权激励"
    if "在建工程" in sentence or "固定资产" in sentence or "产能" in sentence:
        return "CAPEX 与产能建设"
    if "合同" in sentence:
        return "重大合同或订单"
    if "对外投资" in sentence or "募投" in sentence:
        return "投资与募投项目"
    return "重要事项"


def _business_segment_title(sentence: str) -> str:
    if "结构" in sentence or "功能材料" in sentence or "预浸料" in sentence:
        return "结构与功能材料业务"
    if "织物" in sentence:
        return "碳纤维织物业务"
    if "碳纤维" in sentence:
        return "高性能碳纤维业务"
    return "主营业务结构"


def _rd_progress_title(sentence: str) -> str:
    if "重大突破" in sentence or "关键技术" in sentence:
        return "关键技术突破"
    if "专利" in sentence:
        return "专利与知识产权"
    if "量产" in sentence or "批产" in sentence:
        return "研发到量产转化"
    return "研发进展"


def _inventory_interpretation(industry: str) -> str:
    if industry in {"semiconductor", "hardtech", "manufacturing"}:
        return "硬科技企业需重点核对库存商品、发出商品、跌价准备和下游需求变化。"
    return "需核对存货结构、跌价准备和周转天数，避免资产质量被高估。"


def _parse_number(value: str) -> Optional[float]:
    try:
        cleaned = str(value).replace(",", "").strip()
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def _fmt_amount(value: float) -> str:
    abs_value = abs(value)
    sign = "-" if value < 0 else ""
    if abs_value >= 100_000_000:
        return f"{sign}{abs_value / 100_000_000:.2f}亿"
    if abs_value >= 10_000:
        return f"{sign}{abs_value / 10_000:.2f}万"
    return f"{value:.0f}"


def _clean_text(text: str) -> str:
    text = re.sub(r"\[\^[^\]]+\]|\[\d+\]", "", text or "")
    text = re.sub(r"(?<![\d,])(\d{1,2})\s+(\d(?:\.\d+)\s*%)", r"\1\2", text)
    text = re.sub(r"\s+%", "%", text)
    return text.replace("\u3000", " ")


def _clean_heading(text: str) -> str:
    return re.sub(r"\s+", "", text).strip()


def _is_boilerplate(sentence: str) -> bool:
    boilerplate = (
        "本公司及董事会全体成员保证",
        "不存在虚假记载",
        "误导性陈述",
        "证券代码",
        "证券简称",
        "公告编号",
        "目录",
    )
    return any(token in sentence for token in boilerplate)


def _is_non_applicable_checkbox_noise(sentence: str) -> bool:
    text = sentence.replace("", "☑").replace("√", "☑")
    if "不适用" in text and ("□适用" in text or "☑不适用" in text):
        return True
    if text.count("不适用") >= 3:
        return True
    noise_tokens = (
        "方框图",
        "实际控制人通过信托或其他资产管理方式控制公司",
        "其他持股在 10% 以上的法人股东",
        "股份限制减持",
    )
    return any(token in text for token in noise_tokens)


def _is_pointer_only_sentence(sentence: str) -> bool:
    text = re.sub(r"\s+", "", sentence.replace("#", ""))
    return "具体风险及应对措施请见" in text or ("相关风险" in text and ("详见" in text or "请见" in text))


def _looks_like_toc_fragment(text: str) -> bool:
    if "..." in text or "……" in text:
        return True
    dot_count = text.count(".")
    return dot_count >= 6


def _plain_numbers(text: str) -> List[float]:
    values: List[float] = []
    for match in re.finditer(r"-?[\d,]+(?:\.\d+)?", text):
        tail = text[match.end() : match.end() + 3].strip()
        if tail.startswith("%"):
            continue
        parsed = _parse_number(match.group(0))
        if parsed is not None:
            values.append(parsed)
    return values


def _customer_concentration_ratio(text: str) -> Optional[float]:
    patterns = (
        r"前五[大名]客户.{0,80}?占(?:年度)?销售(?:总额)?(?:比例)?\s*([\d,]+(?:\.\d+)?)\s*%",
        r"前五[大名]客户.{0,80}?销售.{0,40}?占比\s*([\d,]+(?:\.\d+)?)\s*%",
        r"前五[大名]客户.{0,80}?([\d,]+(?:\.\d+)?)\s*%",
    )
    return _first_percent_match(text, patterns)


def _ar_aging_over_one_year_ratio(text: str) -> Optional[float]:
    patterns = (
        r"(?:1|一)年以上.{0,80}?应收账款.{0,80}?占(?:应收账款余额)?(?:比例|比)?\s*([\d,]+(?:\.\d+)?)\s*%",
        r"应收账款.{0,80}?(?:1|一)年以上.{0,80}?占(?:比|比例)?\s*([\d,]+(?:\.\d+)?)\s*%",
    )
    return _first_percent_match(text, patterns)


def _restricted_assets_amount(text: str) -> Optional[float]:
    sentence = _find_sentence_with_any(
        text,
        (
            "所有权或使用权受到限制的资产",
            "受限资产",
            "受限货币资金",
            "货币资金受限",
            "银行承兑汇票保证金",
            "定期存单质押",
        ),
    )
    if not sentence:
        return None
    return _first_number_with_optional_unit(sentence)


def _parse_product_margin_line(line: str) -> Optional[Tuple[str, float, float, float, float, float]]:
    cleaned = re.sub(r"^(其中[:：]\s*)", "", line.strip())
    product_match = re.match(r"([\u4e00-\u9fffA-Za-z0-9（）()＋+\-]+)\s+", cleaned)
    if not product_match:
        return None
    product = product_match.group(1).strip()
    if product in {"营业收入合计", "主营业务收入", "其他业务收入", "合计", "分产品", "分行业", "分地区"}:
        return None
    if product.endswith("业"):
        return None
    if not any(token in product for token in ("碳纤维", "芯片", "产品", "材料", "织物", "设备", "模组")):
        return None
    tail = cleaned[product_match.end() :]
    numbers = re.findall(r"-?[\d,]+(?:\.\d+)?%?", tail)
    if len(numbers) < 6:
        return None
    revenue = _parse_number(numbers[0])
    cost = _parse_number(numbers[1])
    margin = _parse_percent(numbers[2])
    revenue_growth = _parse_percent(numbers[3])
    margin_change = _parse_percent(numbers[5])
    if None in (revenue, cost, margin, revenue_growth, margin_change):
        return None
    return product, revenue, cost, margin, revenue_growth, margin_change


def _parse_percent(value: str) -> Optional[float]:
    return _parse_number(str(value).replace("%", ""))


def _strip_report_heading_noise(text: str) -> str:
    text = re.sub(
        r"^第[一二三四五六七八九十]+[章节]\s*(?:管理层讨论与分析|公司治理|重要事项|财务报告|环境和社会责任|公司简介和主要财务指标)\s*#?\s*",
        "",
        text,
    ).strip()
    text = re.sub(r"^(?:[一二三四五六七八九十]+、|[（(][一二三四五六七八九十]+[）)])\s*", "", text).strip()
    text = re.sub(r"^报告期内公司从事的主要业务\s*", "", text).strip()
    text = re.sub(r"^公司从事的主要业务\s*", "", text).strip()
    return text


def _first_percent_match(text: str, patterns: Iterable[str]) -> Optional[float]:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _parse_number(match.group(1))
    return None


def _find_sentence_with_any(text: str, keywords: Iterable[str]) -> str:
    for sentence in _split_sentences(text):
        if any(keyword in sentence for keyword in keywords):
            return sentence
    return ""


def _truncate(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _escape_md(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()
