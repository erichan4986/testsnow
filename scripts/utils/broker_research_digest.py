"""Deterministic digest cards for broker research PDFs.

The digest layer intentionally treats broker reports as professional analysis,
not confirmed facts. It extracts a few high-value excerpts for preview/report
context while keeping scoring, risk scoring, and fact confirmation isolated.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple

if __name__.startswith("utils."):
    from .source_adapter import SynthesisItem
else:
    from source_adapter import SynthesisItem


SOURCE_TYPE = "broker_research"
SOURCE_CREDIT = 72
SCHEMA_VERSION = "broker_research_digest_card.v1"
SELECTION_VERSION = "broker_digest_v3_3"

SCORE_PART_KEYS = (
    "signal", "evidence", "completeness", "coherence",
    "ocr_penalty", "noise_penalty",
)
_EXCERPT_TERMINATORS = "。；;！？!?"
_MIN_DAMAGED_GENERIC_BLOCKS = 8


def _unit_roles(text: str) -> set[str]:
    roles: set[str] = set()
    if any(
        term in text
        for term in (
            "增长",
            "提升",
            "改善",
            "受益",
            "推动",
            "带动",
            "实现",
            "认为",
            "看好",
        )
    ):
        roles.add("claim")
    if re.search(r"\d+(?:\.\d+)?\s*(?:亿元|%|pct|倍|G|T|元)", text) or any(
        term in text for term in ("客户", "订单", "产能", "毛利率", "净利润", "收入")
    ):
        roles.add("evidence")
    if any(
        term in text
        for term in (
            "产品",
            "需求",
            "客户",
            "订单",
            "产能",
            "应用",
            "下游",
            "技术",
            "供应链",
            "交付",
        )
    ):
        roles.add("driver")
    if any(
        term in text
        for term in (
            "预计",
            "预测",
            "上调",
            "维持",
            "评级",
            "目标价",
            "EPS",
            "PE",
            "估值",
        )
    ):
        roles.add("forecast")
    if any(
        term in text
        for term in (
            "风险",
            "不及预期",
            "下滑",
            "竞争加剧",
            "波动",
            "承压",
        )
    ):
        roles.add("risk")
    if any(
        term in text
        for term in (
            "导致",
            "影响",
            "拖累",
            "压制",
            "取决于",
            "若",
            "受到",
            "价格",
            "毛利率",
            "收入",
            "利润",
            "推动",
            "带动",
            "支撑",
            "来自",
            "受益于",
        )
    ):
        roles.add("mechanism")
    return roles


def _source_unit_damage_reason(text: str) -> str:
    if re.search(r"(?:图\s*\d+[:：]|(?:数据|资料)来源[:：]?|\bWind\b)", text, re.IGNORECASE):
        return "chart_metadata"
    if re.search(r"其中\s*(?:及|和|与)\s*\d+(?:\.\d+)?[GT]", text, re.IGNORECASE):
        return "missing_parallel_product"
    if re.search(
        r"(?:营业收入|营收|归母净利润|扣非(?:归母)?净利润)\s*\d+\.(?:\s*(?:同比|环比|同环比)|$)",
        text,
    ):
        return "dangling_financial_value"
    if re.match(r"\s*(?:同比|环比|同环比)分别(?:增长|下降)", text):
        return "detached_growth_series"
    for match in re.finditer(r"(?:同比|环比|同环比)分别(?:增长|下降)\s*([^。；;！？!?]*)", text):
        if len(re.findall(r"\d+(?:\.\d+)?%", match.group(1))) < 2:
            return "incomplete_paired_growth"
    if re.search(
        r"(?:营业收入|归母净利润|扣非(?:归母)?净利润)\s*\d+(?:\.\d+)?\s*元(?:[，,；;。]|同比|$)",
        text,
    ):
        return "invalid_financial_unit"
    for match in re.finditer(
        r"(20\d{2})\s*[–—-]\s*(20\d{2})年?[^。；;]{0,24}?分别为\s*"
        r"((?:\d+(?:\.\d+)?\s*(?:%|亿元|元|倍|pct)\s*[、/,，]?\s*)+)",
        text,
        re.IGNORECASE,
    ):
        expected = int(match.group(2)) - int(match.group(1)) + 1
        values = re.findall(r"\d+(?:\.\d+)?\s*(?:%|亿元|元|倍|pct)", match.group(3), re.IGNORECASE)
        if 1 <= expected <= 10 and len(values) < expected:
            return "incomplete_period_series"
    return ""


def _complete_source_units(text: str) -> List[str]:
    units: List[str] = []
    cursor = 0
    for match in re.finditer(r"[^。；;！？!?]+[。；;！？!?]", text):
        cursor = match.end()
        unit = clean_broker_research_excerpt_text(match.group(0).strip())
        if len(unit) < 14 or _looks_like_front_matter_noise(unit):
            continue
        if _source_unit_damage_reason(unit) or _has_severe_ocr_damage(
            _candidate_score_parts(unit)
        ):
            continue
        if _unit_roles(unit):
            units.append(unit)
    tail = clean_broker_research_excerpt_text(text[cursor:].strip())
    if (
        14 <= len(tail) <= 180
        and not _looks_like_front_matter_noise(tail)
        and not _source_unit_damage_reason(tail)
        and not _has_severe_ocr_damage(_candidate_score_parts(tail))
        and _unit_roles(tail)
    ):
        units.append(tail)
    return units


def _family_requirements_met(card_type: str, units: List[str]) -> bool:
    roles = set().union(*(_unit_roles(unit) for unit in units)) if units else set()
    text = " ".join(units)
    if card_type == "broker_core_view":
        return "claim" in roles and bool(roles & {"evidence", "mechanism"})
    if card_type == "broker_product_driver":
        clusters = _generic_driver_cluster_labels(text)
        return "driver" in roles and ("evidence" in roles or len(clusters) >= 2)
    if card_type == "broker_earnings_forecast":
        return "forecast" in roles and "evidence" in roles
    if card_type == "broker_risk_note":
        return "risk" in roles and bool(roles & {"mechanism", "evidence"})
    return False


def _units_redundant(left: str, right: str) -> bool:
    number_pattern = r"\d+(?:\.\d+)?(?:年|亿元|%|pct|倍|G|T|元)?"
    if set(re.findall(number_pattern, left)) != set(re.findall(number_pattern, right)):
        return False
    left_tokens = set(re.findall(r"[一-鿿]|[A-Za-z0-9]+", left.lower()))
    right_tokens = set(re.findall(r"[一-鿿]|[A-Za-z0-9]+", right.lower()))
    if not left_tokens or not right_tokens:
        return False
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens) >= 0.5


def _select_excerpt_units(text: str, card_type: str, max_units: int = 5) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    if card_type == "broker_earnings_forecast" and _looks_like_financial_table_fragment(text):
        return ""
    if card_type == "broker_risk_note" and not _has_specific_risk_signal(text):
        return ""
    if card_type == "broker_product_driver" and _looks_like_risk_only(text):
        return ""
    units = _complete_source_units(text)
    chosen: List[Tuple[int, str]] = []
    covered: set[str] = set()
    for index, unit in enumerate(units):
        roles = _unit_roles(unit)
        if roles <= covered:
            if any(_units_redundant(unit, selected) for _, selected in chosen):
                continue
        chosen.append((index, unit))
        covered.update(roles)
        if len(chosen) >= max_units:
            break
    selected = [unit for _, unit in chosen]
    if not _family_requirements_met(card_type, selected):
        return ""
    return _bounded_complete_excerpt(" ".join(selected))

_STOP_PATTERNS = [
    "免责声明",
    "免责条款",
    "评级说明",
    "投资评级说明",
    "分析师声明",
    "声明：",
    "本报告仅供",
    "法律声明",
    "重要声明",
    "请务必阅读",
    "请务必阅读正文之后的免责",
    "请认真阅读文后免责",
    "市场有风险，投资需谨慎",
    "在任何情况下",
    "本报告版权归",
    "最终解释权",
    "研究报告评级体系",
    "报告评级体系",
    "客户使用",
    "本报告清晰准确地反映",
    "本人保证",
]

_SECTION_SPECS: List[Tuple[str, Tuple[str, ...], str]] = [
    (
        "broker_core_view",
        ("核心观点", "投资要点", "主要观点", "核心结论", "事件", "观点", "点评", "事件点评"),
        "券商核心观点",
    ),
    (
        "broker_product_driver",
        (
            "产业趋势",
            "竞争格局",
            "业务概况",
            "公司业务概况",
            "业务结构",
            "业务演进路径",
            "产品与产业",
            "产品布局",
            "客户结构",
            "订单与交付",
            "产能与供应链",
            "技术优势",
            "行业趋势",
            "行业需求",
            "增长逻辑",
            "成长逻辑",
        ),
        "产品与产业驱动",
    ),
    ("broker_earnings_forecast", ("盈利预测", "业绩预测", "投资建议", "投资评级", "财务数据与估值", "盈利与估值", "估值分析"), "盈利预测与评级"),
    ("broker_risk_note", ("风险提示", "主要风险", "风险因素", "风险分析"), "风险提示"),
]
_SHORT_REPORT_CARD_TYPES = {"broker_core_view", "broker_earnings_forecast", "broker_risk_note"}
_MEDIUM_REPORT_CARD_TYPES = {
    "broker_core_view",
    "broker_product_driver",
    "broker_earnings_forecast",
    "broker_risk_note",
}
_LONG_REPORT_CARD_TYPES = set(_MEDIUM_REPORT_CARD_TYPES)

_ALL_HEADINGS = tuple(dict.fromkeys(h for _, headings, _ in _SECTION_SPECS for h in headings))
_GENERIC_NOISE_PATTERNS = [
    "股票走势图",
    "基础数据",
    "分析师电话",
    "分析师联系方式",
    "公司近一年市场表现",
    "市场数据",
    "本报告的信息均来自",
]
_SPECIFIC_TERMS = [
    "营收",
    "收入",
    "净利润",
    "毛利率",
    "同比",
    "环比",
    "EPS",
    "PE",
    "亿元",
    "%",
    "客户",
    "订单",
    "产能",
    "产品",
    "业务",
    "需求",
    "增长",
    "景气",
    "导入",
    "升级",
    "结构",
    "份额",
    "应用",
    "市场",
    "下游",
    "交付",
    "盈利能力",
    "研发",
    "800G",
    "1.6T",
    "AI",
    "芯片",
    "光模块",
]

_PDF_OCR_ARTIFACT_REPAIRS = (
    ("实 现", "实现"),
    ("光模 块", "光模块"),
    ("现 方面", "现金流方面"),
    ("高速光 过持续", "高速光模块持续"),
    ("盈 展", "盈利扩展"),
    ("核心增 链能力", "核心增长与供应链能力"),
    ("结构升级驱 的业务格局", "结构升级驱动的业务格局"),
    ("同环比 262.3%", "同环比增长262.3%"),
    ("营业收 382.40", "营业收入382.40"),
    ("超大 互联", "超大互联"),
    ("公司 品出货", "公司产品出货"),
    ("随着产 方案", "随着产品方案"),
    ("产 方案", "产品方案"),
    ("净利 均", "净利润均"),
    ("稳中 升", "稳中有升"),
    ("将迎 强劲", "将迎来强劲"),
    ("延续增 势", "延续增长态势"),
    ("产 投入", "产能投入"),
    ("已 到", "已达到"),
    ("客 给予", "客户给予"),
    ("实现归 公司股东", "实现归属于公司股东"),
    ("产品毛 净利润率", "产品毛利率、净利润率"),
    ("同环比 分别", "同环比分别"),
    ("拉货 动", "拉货波动"),
    ("继 加", "继续增加"),
)


def _filter_irrecoverable_legacy_units(text: str) -> str:
    text = re.sub(
        r"(?:(?:20\d{2}年[^，,。；;]{0,12}[，,])?公司)?(?:实现)?"
        r"(?:营业收入|营收|归母净利润|扣非(?:归母)?净利润)\s*\d+\."
        r"(?=\s*(?:同比|环比|同环比))",
        "",
        text,
    )
    text = re.sub(
        r"(^|[，,。；;])\s*(?:同比|环比|同环比)分别(?:增长|下降)"
        r"[^，,。；;！？!?]*(?:[，,；;]|$)",
        r"\1",
        text,
    )
    units = re.findall(r"[^。；;！？!?]+(?:[。；;！？!?]|$)", text)
    return " ".join(
        unit.strip()
        for unit in units
        if unit.strip() and not _source_unit_damage_reason(unit.strip())
    )


def clean_broker_research_excerpt_text(
    text: str,
    *,
    repair_legacy_artifacts: bool = False,
) -> str:
    """Clean broker excerpts while preserving broker claims.

    ``repair_legacy_artifacts`` is intentionally opt-in. New digest production
    should prefer cleaner source candidates instead of rewriting broken OCR
    fragments into synthetic-looking claims; the opt-in path keeps old persisted
    notes readable until they are regenerated.
    """
    value = re.sub(r"\s+", " ", str(text or "")).strip(" ：:")
    if not value:
        return ""
    value = re.sub(r"[▌•●]\s*", "", value)
    value = re.sub(r"^(?:投资要点|核心观点|事件|观点|业绩简评|经营分析)[：:，,\s]*", "", value)
    value = re.sub(r"(?:(?<=^)|(?<=[。；;，,]))\s*(?:事件|观点|业绩简评|经营分析|投资要点)[：:，,\s]*", "", value)
    value = re.sub(
        r"^20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日[，,]?\s*[^，,：:；;。]{0,18}?发布\s*20\d{2}\s*年[一二三四]季报[：:，,]\s*",
        "",
        value,
    )
    if repair_legacy_artifacts:
        for old, new in _PDF_OCR_ARTIFACT_REPAIRS:
            value = value.replace(old, new)
        value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
        value = _filter_irrecoverable_legacy_units(value)
        if value.count("“") != value.count("”") or value.count("‘") != value.count("’"):
            return ""
    value = re.sub(r"(?<=预计)\s*20\s+(?=20\d{2}\s*年)", "", value)
    value = re.sub(r"(20\d{2})\s+年", r"\1年", value)
    value = re.sub(r"(?<=\d)\s+(?=(?:年|亿元|%|pct|倍|G|T))", "", value)
    value = re.sub(r"(?<=年)\s+(?=\d)", "", value)
    value = re.sub(r"(800G|1\.6T)\s+(?=光模块)", r"\1", value)
    value = re.sub(r"\s*([，,；;。])\s*", r"\1", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" ：:")


def build_broker_research_digest_cards(
    item: SynthesisItem,
    pdf_text: str,
    *,
    max_cards: int = 5,
) -> List[Dict[str, Any]]:
    """Build deterministic digest cards from extracted broker PDF text."""
    useful_text = _truncate_before_disclaimer(_normalize_text(pdf_text))
    if not useful_text:
        return []

    report_length_class = _classify_report_length(item, useful_text)
    allowed_card_types = _allowed_card_types_for_length(report_length_class)
    max_cards = min(max_cards, _max_cards_for_length(report_length_class))
    candidates: List[Dict[str, Any]] = []
    for card_type, headings, title in _SECTION_SPECS:
        if card_type not in allowed_card_types:
            continue
        section_candidates: List[Tuple[int, int, str, str]] = []
        for heading in headings:
            section_candidates.extend(
                _extract_section_candidates(
                    useful_text, heading, card_type, order_offset=len(section_candidates)
                )
            )
        selected_sections = _select_section_candidates(card_type, section_candidates)
        if not selected_sections:
            continue
        joined_excerpt = " ".join(part for _, _, _, part in selected_sections)
        excerpt = (
            _bounded_complete_excerpt(joined_excerpt)
            if card_type == "broker_product_driver"
            else selected_sections[0][3]
        )
        if not excerpt:
            continue
        matched_headings = [heading for _, _, heading, _ in selected_sections]
        diagnostics = _section_selection_diagnostics(section_candidates, selected_sections)
        candidates.append(
            _build_card(
                item=item,
                card_type=card_type,
                title=title,
                excerpt=excerpt,
                heading=",".join(matched_headings),
                report_length_class=report_length_class,
                selection_diagnostics=diagnostics,
                selection_reason=_selection_reason(card_type, selected_sections),
            )
        )

    if (
        ("broker_product_driver" in allowed_card_types or not candidates)
        and not _has_knowledge_driver_candidate(candidates)
    ):
        for driver_excerpt in _generic_driver_block_excerpts(useful_text):
            candidates.append(
                _build_card(
                    item=item,
                    card_type="broker_product_driver",
                    title="产品与产业驱动",
                    excerpt=driver_excerpt,
                    heading="generic_driver_block",
                    report_length_class=report_length_class,
                    selection_diagnostics=[
                        _diagnostic_entry(
                            heading="generic_driver_block",
                            score=_section_candidate_score(driver_excerpt),
                            status="selected",
                            reason="selected_generic_driver_block",
                            text=driver_excerpt,
                        )
                    ],
                    selection_reason="selected_generic_driver_block",
                )
            )

    if not candidates and _allow_fallback_excerpt(useful_text):
        excerpt = _fallback_excerpt(useful_text)
        if excerpt:
            candidates.append(
                _build_card(
                    item=item,
                    card_type="broker_core_view",
                    title="券商核心观点",
                    excerpt=excerpt,
                    heading="fallback",
                    report_length_class=report_length_class,
                    selection_diagnostics=[
                        _diagnostic_entry(
                            heading="fallback",
                            score=_section_candidate_score(excerpt),
                            status="selected",
                            reason="selected_fallback_excerpt",
                            text=excerpt,
                        )
                    ],
                    selection_reason="selected_fallback_excerpt",
                )
            )

    selected: List[Dict[str, Any]] = []
    seen: List[str] = []
    for card in sorted(candidates, key=lambda c: (-int(c.get("quality_score", 0)), c["card_type"])):
        fingerprint = _fingerprint(card["source_excerpt"])
        if any(_near_duplicate(fingerprint, old) for old in seen):
            continue
        selected.append(card)
        seen.append(fingerprint)
        if len(selected) >= max_cards:
            break

    order = {
        "broker_core_view": 0,
        "broker_product_driver": 1,
        "broker_earnings_forecast": 2,
        "broker_risk_note": 3,
    }
    return sorted(selected, key=lambda c: order.get(str(c.get("card_type")), 99))


def build_broker_research_digest_preview_markdown(
    *,
    stock_name: str,
    stock_code: str = "",
    cards: List[Dict[str, Any]],
) -> str:
    """Render digest cards as deterministic preview Markdown."""
    lines = [
        "# Broker Research Digest Preview",
        "",
        f"- 股票：{stock_name or '未知'}",
        f"- 代码：{stock_code or '—'}",
        f"- cards：{len(cards)}",
        "- 边界：broker_research 仅作 professional_analysis；不进入 confirmed fact、评分或风险计分。",
        "",
    ]
    if not cards:
        lines.extend(["未生成 broker research digest cards。", ""])
        return "\n".join(lines)

    for idx, card in enumerate(cards, 1):
        lines.extend(
            [
                f"## {idx}. {card.get('title', '')} / `{card.get('card_type', '')}`",
                "",
                f"- institution：`{card.get('institution', '')}`",
                f"- stock_name：`{card.get('stock_name', '')}`",
                f"- stock_code：`{card.get('stock_code', '')}`",
                f"- report_title：`{card.get('report_title', '')}`",
                f"- publish_time：`{card.get('publish_time', '')}`",
                f"- source_credit：`{card.get('source_credit', '')}`",
                f"- claim_status：`{card.get('claim_status', '')}`",
                f"- display_only：`{str(bool(card.get('display_only'))).lower()}`",
                f"- knowledge_eligible：`{str(bool(card.get('knowledge_eligible'))).lower()}`",
                f"- confirmed_fact：`{str(bool(card.get('confirmed_fact'))).lower()}`",
                f"- scoring_eligible：`{str(bool(card.get('scoring_eligible'))).lower()}`",
                f"- risk_score_eligible：`{str(bool(card.get('risk_score_eligible'))).lower()}`",
                f"- viewpoint_cluster：`{card.get('viewpoint_cluster', '')}`",
                f"- report_length_class：`{card.get('report_length_class', '')}`",
                f"- source_pdf_path：`{card.get('source_pdf_path', '')}`",
                f"- selection_reason：`{card.get('selection_reason', '')}`",
                "",
                "> " + str(card.get("source_excerpt", "")),
                "",
            ]
        )
        diagnostics = card.get("selection_diagnostics") or []
        if diagnostics:
            lines.extend(["### Selection Diagnostics", ""])
            for entry in diagnostics[:6]:
                lines.append(
                    "- "
                    f"heading=`{entry.get('heading', '')}` | "
                    f"score=`{entry.get('score', '')}` | "
                    f"status=`{entry.get('status', '')}` | "
                    f"reason=`{entry.get('reason', '')}`"
                )
            lines.append("")
    return "\n".join(lines)


def _main_content_bbox(page, chars, header_frac=0.10, footer_frac=0.08) -> Tuple[float, float, float, float]:
    """Detect the main body text column bbox for a single PDF page.

    Uses an x-axis histogram over body characters (after stripping headers and
    footers) to find the densest horizontal window that is likely to contain
    the main narrative column.  Narrow sidebars such as first-page stock charts
    or rating tables are excluded when they sit outside the densest window.
    """
    page_width = float(page.width)
    page_height = float(page.height)

    y0 = page_height * header_frac
    y1 = page_height * (1 - footer_frac)

    # Keep reasonably-sized text only.  Tiny print is usually footnotes or chart
    # labels that we want to drop anyway.
    body_chars = [
        c
        for c in chars
        if y0 < c.get("top", 0) < y1 and c.get("size", 10) >= 7
    ]
    if len(body_chars) < 20:
        return (0, y0, page_width, y1)

    # Weighted x histogram: slightly prefer larger body text over chart labels.
    bin_width = 8
    bins: Dict[int, float] = {}
    for c in body_chars:
        bin_idx = int(c.get("x0", 0) / bin_width)
        weight = max(1.0, float(c.get("size", 10)) - 5.0)
        bins[bin_idx] = bins.get(bin_idx, 0.0) + weight

    if not bins:
        return (0, y0, page_width, y1)

    sorted_bins = sorted(bins.items())
    total_weight = sum(bins.values())

    def _best_window(max_width_frac: float, min_weight_frac: float):
        max_bins = max(3, int((page_width * max_width_frac) / bin_width))
        candidates = []
        for i in range(len(sorted_bins)):
            weight = 0.0
            left_idx = sorted_bins[i][0]
            right_idx = left_idx
            for j in range(i, min(len(sorted_bins), i + max_bins)):
                right_idx = sorted_bins[j][0]
                weight += sorted_bins[j][1]
            candidates.append((weight, left_idx, right_idx))
        if not candidates:
            return None
        candidates.sort(key=lambda x: (-x[0], x[1]))
        best_weight, best_left, best_right = candidates[0]
        # Prefer a right-shifted body column when a close runner-up exists, to
        # avoid first-page chart sidebars that often occupy the left margin.
        for weight, left_idx, right_idx in candidates[:5]:
            if left_idx * bin_width > page_width * 0.20 and weight >= best_weight * 0.75:
                best_weight, best_left, best_right = weight, left_idx, right_idx
                break
        if best_weight < total_weight * min_weight_frac:
            return None
        return (best_weight, best_left, best_right)

    # Try a narrow column first (typical body-text layout), then a wider window
    # for pages dominated by full-width tables.
    result = _best_window(max_width_frac=0.50, min_weight_frac=0.35)
    if result is None:
        result = _best_window(max_width_frac=0.70, min_weight_frac=0.30)

    if result is None:
        return (0, y0, page_width, y1)

    _, best_left, best_right = result
    x0 = max(0.0, best_left * bin_width - 8)
    x1 = min(page_width, (best_right + 1) * bin_width + 8)
    return (x0, y0, x1, y1)


def extract_pdf_text(pdf_path: str) -> str:
    """Extract text from a local PDF path using pdfplumber with layout filtering."""
    try:
        import pdfplumber
    except Exception as exc:  # pragma: no cover - environment dependency
        raise RuntimeError(f"pdfplumber import failed: {exc}") from exc

    texts: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            chars = page.chars
            if not chars:
                texts.append(page.extract_text() or "")
                continue
            try:
                bbox = _main_content_bbox(page, chars)
                cropped = page.crop(bbox)
                texts.append(cropped.extract_text() or "")
            except Exception:
                # Fall back to full-page extraction if layout parsing fails.
                texts.append(page.extract_text() or "")
    return "\f".join(texts)


def _build_card(
    *,
    item: SynthesisItem,
    card_type: str,
    title: str,
    excerpt: str,
    heading: str,
    report_length_class: str,
    selection_diagnostics: Optional[List[Dict[str, Any]]] = None,
    selection_reason: str = "",
) -> Dict[str, Any]:
    source_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    institution = str((item.extra or {}).get("institution") or item.author or "")
    viewpoint_cluster = _viewpoint_cluster(card_type, excerpt)
    display_only = _is_display_only_card(card_type, viewpoint_cluster, excerpt)
    return {
        "schema_version": SCHEMA_VERSION,
        "selection_version": SELECTION_VERSION,
        "card_id": f"broker:{source_hash[:16]}",
        "card_type": card_type,
        "title": title,
        "source_excerpt": excerpt,
        "source_excerpt_hash": source_hash,
        "source_heading": heading,
        "report_title": item.title,
        "institution": institution,
        "publish_time": item.publish_time,
        "source_url": item.url,
        "source_pdf_path": str((item.extra or {}).get("pdf_local_path") or ""),
        "stock_name": str((item.extra or {}).get("stock_name") or ""),
        "stock_code": str((item.extra or {}).get("stock_code") or ""),
        "source_type": SOURCE_TYPE,
        "source_credit": SOURCE_CREDIT,
        "claim_status": "professional_analysis",
        "verification_status": "professional_observation",
        "display_only": display_only,
        "knowledge_eligible": not display_only,
        "confirmed_fact": False,
        "scoring_eligible": False,
        "risk_score_eligible": False,
        "viewpoint_cluster": viewpoint_cluster,
        "report_length_class": report_length_class,
        "quality_score": _quality_score(excerpt),
        "selection_reason": selection_reason or "selected_by_digest_quality_score",
        "selection_diagnostics": selection_diagnostics or [],
    }


def _classify_report_length(item: SynthesisItem, text: str) -> str:
    """Classify broker report length from PDF page count, with text-length fallback."""
    raw_page_count = (item.extra or {}).get("pdf_page_count")
    try:
        page_count = int(raw_page_count)
    except (TypeError, ValueError):
        page_count = 0
    if page_count > 0:
        if page_count <= 6:
            return "short"
        if page_count <= 15:
            return "medium"
        return "long"
    if len(text) <= 8500:
        return "short"
    if len(text) <= 18000:
        return "medium"
    return "long"


def _allowed_card_types_for_length(report_length_class: str) -> set:
    if report_length_class == "short":
        return _SHORT_REPORT_CARD_TYPES
    if report_length_class == "medium":
        return _MEDIUM_REPORT_CARD_TYPES
    return _LONG_REPORT_CARD_TYPES


def _max_cards_for_length(report_length_class: str) -> int:
    if report_length_class == "short":
        return 3
    if report_length_class == "medium":
        return 5
    return 8


def _normalize_text(text: str) -> str:
    text = str(text or "").replace("\u3000", " ")
    # Preserve page separators as paragraph breaks so headings at page starts
    # remain detectable after normalization.
    text = re.sub(r"\f+", "\n\n", text)
    text = re.sub(r"[ \t\r\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _truncate_before_disclaimer(text: str) -> str:
    lower_bound = len(text)
    for pattern in _STOP_PATTERNS:
        idx = text.find(pattern)
        if idx >= 0:
            lower_bound = min(lower_bound, idx)
    return text[:lower_bound].strip()


_HEADING_BOUNDARY_TEMPLATE = r"(?:^|\n)\s*(?:[lLnN•●·\-]\s*)?{}(?::|：|\s|$)"


def _find_heading_positions(text: str, heading: str) -> List[int]:
    """Return start indices of ``heading`` occurrences that look like real section headings.

    Headings must sit at a line boundary and be followed by whitespace, a colon,
    or end-of-line.  This avoids false matches inside disclaimer boilerplate such
    as "本人的研究观点".
    """
    pattern = re.compile(_HEADING_BOUNDARY_TEMPLATE.format(re.escape(heading)))
    return [m.start() for m in re.finditer(pattern, text)]


def _find_heading_spans(text: str, heading: str) -> List[Tuple[int, int]]:
    pattern = re.compile(_HEADING_BOUNDARY_TEMPLATE.format(re.escape(heading)))
    return [(m.start(), m.end()) for m in re.finditer(pattern, text)]


def _extract_section_candidates(
    text: str,
    heading: str,
    card_type: str,
    order_offset: int = 0,
) -> List[Tuple[int, int, str, str]]:
    spans = _find_heading_spans(text, heading)
    if not spans:
        return []
    candidates: List[Tuple[int, int, str, str]] = []
    for local_order, (start, content_start) in enumerate(spans):
        next_positions = []
        for other in _ALL_HEADINGS + tuple(_STOP_PATTERNS):
            for idx in _find_heading_positions(text[content_start:], other):
                next_positions.append(content_start + idx)
                break
        end = min(next_positions) if next_positions else min(len(text), start + 1600)
        raw = text[content_start:end].strip()
        cleaned = _clean_excerpt(raw)
        if not cleaned:
            continue
        parts = _candidate_score_parts(cleaned)
        if _has_severe_ocr_damage(parts):
            score = _candidate_total(parts)
            candidates.append((score, order_offset + local_order, heading, cleaned))
            continue
        excerpt = _select_excerpt_units(cleaned, card_type)
        if not excerpt:
            continue
        score = _section_candidate_score(excerpt)
        candidates.append((score, order_offset + local_order, heading, excerpt))
    return candidates


def _candidate_score_parts(text: str) -> Dict[str, int]:
    digit_count = min(sum(ch.isdigit() for ch in text), 20)
    specific_count = sum(term in text for term in _SPECIFIC_TERMS)
    complete_sentences = len(re.findall(r"[。；;！？!?]", text))
    directional = any(
        term in text
        for term in ("预计", "认为", "维持", "受益", "推动", "带动", "提升", "改善", "风险", "不及预期")
    )
    evidence_signal = bool(re.search(r"\d+(?:\.\d+)?\s*(?:亿元|%|pct|倍|G|T)", text)) or any(
        term in text for term in ("客户", "订单", "产能", "产品", "毛利率", "净利润")
    )
    gap_count = len(re.findall(r"[\u4e00-\u9fff]\s+[\u4e00-\u9fff]", text))
    dangling_decimal_count = len(re.findall(r"\d+\.(?=\s|[，,；;。]|$)", text))
    broken_year_count = len(re.findall(r"(?:20\s+20\d{2}|20\d{2}\s+年)", text))
    noise_hits = sum(pattern in text for pattern in _GENERIC_NOISE_PATTERNS)
    table_noise = _looks_like_financial_table_fragment(text) or _looks_like_rating_table_fragment(text)
    return {
        "signal": min(specific_count * 3, 60),
        "evidence": digit_count + (8 if evidence_signal else 0),
        "completeness": min(complete_sentences * 4, 12),
        "coherence": 8 if directional and evidence_signal else 0,
        "ocr_penalty": gap_count * 4 + dangling_decimal_count * 40 + broken_year_count * 40,
        "noise_penalty": noise_hits * 12 + (80 if table_noise else 0),
    }


def _candidate_total(parts: Dict[str, int]) -> int:
    return sum(parts[key] for key in SCORE_PART_KEYS[:4]) - sum(
        parts[key] for key in SCORE_PART_KEYS[4:]
    )


def _has_severe_ocr_damage(parts: Dict[str, int]) -> bool:
    return parts["ocr_penalty"] >= 20


def _quality_score(text: str) -> int:
    return _candidate_total(_candidate_score_parts(text))


def _section_candidate_score(text: str) -> int:
    parts = _candidate_score_parts(text)
    return _candidate_total(parts)


def _select_section_candidates(
    card_type: str,
    candidates: List[Tuple[int, int, str, str]],
) -> List[Tuple[int, int, str, str]]:
    if not candidates:
        return []
    eligible = [
        candidate
        for candidate in candidates
        if candidate[3] and not _has_severe_ocr_damage(_candidate_score_parts(candidate[3]))
    ]
    ordered = sorted(eligible, key=lambda item: (-item[0], item[1]))
    if card_type != "broker_product_driver":
        return ordered[:1]

    selected: List[Tuple[int, int, str, str]] = []
    seen: List[str] = []
    for candidate in ordered:
        fingerprint = _fingerprint(candidate[3])
        if any(_near_duplicate(fingerprint, old) for old in seen):
            continue
        selected.append(candidate)
        seen.append(fingerprint)
        if len(selected) >= 2:
            break
    return selected or ordered[:1]


def _section_selection_diagnostics(
    candidates: List[Tuple[int, int, str, str]],
    selected: List[Tuple[int, int, str, str]],
) -> List[Dict[str, Any]]:
    selected_keys = {(score, order, heading) for score, order, heading, _ in selected}
    selected_fingerprints = [_fingerprint(text) for _, _, _, text in selected]
    diagnostics: List[Dict[str, Any]] = []
    for score, order, heading, text in sorted(candidates, key=lambda item: item[1]):
        parts = _candidate_score_parts(text)
        if _has_severe_ocr_damage(parts):
            diagnostics.append(
                _diagnostic_entry(
                    heading=heading,
                    score=score,
                    status="rejected",
                    reason="rejected_ocr_damage",
                    text=text,
                )
            )
            continue
        key = (score, order, heading)
        if key in selected_keys:
            diagnostics.append(
                _diagnostic_entry(heading=heading, score=score, status="selected", reason="selected", text=text)
            )
            continue
        fingerprint = _fingerprint(text)
        duplicate = any(_near_duplicate(fingerprint, old) for old in selected_fingerprints)
        diagnostics.append(
            _diagnostic_entry(
                heading=heading,
                score=score,
                status="skipped",
                reason="skipped_near_duplicate" if duplicate else "skipped_lower_score",
                text=text,
            )
        )
    return diagnostics


def _diagnostic_entry(
    *, heading: str, score: int, status: str, reason: str, text: str
) -> Dict[str, Any]:
    return {
        "heading": heading,
        "score": int(score),
        "score_parts": _candidate_score_parts(text),
        "status": status,
        "reason": reason,
    }


def _selection_reason(card_type: str, selected: List[Tuple[int, int, str, str]]) -> str:
    if card_type == "broker_product_driver" and len(selected) > 1:
        return "selected_complementary_product_driver_candidates"
    return "selected_best_heading_candidate"


def _clean_excerpt(text: str) -> str:
    text = _truncate_before_disclaimer(text)
    text = re.sub(r"\[[^\]]{0,80}(?:Table|Tab|Ta ble|table)[^\]]*\]", " ", text)
    text = re.sub(r"\[[^\]]{0,80}(?:表|价|数据|研究|作者)[^\]]*\]", " ", text)
    text = re.sub(r"\[[A-Za-z_\\]+[^\]]*\]", " ", text)
    text = re.sub(r"(?:数据)?资料?来源[:：][^。；]{0,100}?(?:研究所|整理)", " ", text)
    text = re.sub(r"来源[:：][^。；]{0,60}?研究所", " ", text)
    text = re.sub(r"图\d+[:：][^。；]{0,80}", " ", text)
    text = re.sub(r"(?:整理\s*){2,}", " ", text)
    text = re.sub(r"最新收盘价[^。；]{0,120}", " ", text)
    text = re.sub(r"总市值/流通市值[^。；]{0,120}", " ", text)
    text = re.sub(r"(?:当前价格|52周价格区间|52周最高/最低价|A股流通股|A股总股本|流通市值|总市值|总股本|流通股|资产负债率|市盈率|市净率|近一月换手)[^。；]{0,100}", " ", text)
    text = re.sub(r"(?:公司基本情况|基本数据|市场数据|过去一年股价走势|相对指数表现|个股表现|股票投资评级|相关研究报告|点评报告|研究所\s*l)", " ", text)
    text = re.sub(r"(?:-?\d+%\s*){3,}", " ", text)
    text = re.sub(r"(?:\d{4}-\d{2}\s*){2,}", " ", text)
    text = re.sub(r"证券分析师[:：].{0,80}", " ", text)
    text = re.sub(r"分析师[:：][^。；]{0,80}", " ", text)
    text = re.sub(r"执业证(?:书)?编号[:：]?[A-Z0-9]+", " ", text)
    text = re.sub(r"SAC[登]?记?编号[:：]?[A-Z0-9]+", " ", text)
    text = re.sub(r"Email[:：]?\s*[\w.\-@]+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"邮箱[:：]?\s*[\w.\-@]+", " ", text)
    text = re.sub(r"[\w.\-]+@[\w.\-]+", " ", text)
    for noise in _GENERIC_NOISE_PATTERNS:
        text = text.replace(noise, " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = clean_broker_research_excerpt_text(text)
    return text


def _bounded_complete_excerpt(text: str, limit: int = 900, extension: int = 80) -> str:
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    hard_end = min(len(text), limit + extension)
    next_positions = [
        pos for mark in _EXCERPT_TERMINATORS
        if (pos := text.find(mark, limit, hard_end + 1)) >= 0
    ]
    if next_positions:
        return text[: min(next_positions) + 1].strip()
    previous = max(text.rfind(mark, 0, limit + 1) for mark in _EXCERPT_TERMINATORS)
    return text[: previous + 1].strip() if previous >= 0 else ""


def _looks_like_front_matter_noise(text: str) -> bool:
    noise_terms = (
        "分析师",
        "执业证",
        "电话",
        "邮箱",
        "研究所",
        "走势图",
        "沪深300",
        "资料来源",
        "Wind",
        "聚源",
        "iFind",
        "声明",
        "本报告",
        "请务必阅读",
    )
    if any(term in text for term in noise_terms):
        strong_signal_terms = ("营收", "收入", "净利润", "毛利率", "EPS", "PE", "产品", "客户", "订单", "产能")
        if not any(term in text for term in strong_signal_terms):
            return True
    if len(re.findall(r"-?\d+%", text)) >= 6 and not any(term in text for term in ("毛利率", "同比", "增长率")):
        return True
    return False


def _fallback_excerpt(text: str) -> str:
    cleaned = _clean_excerpt(text)
    for card_type in ("broker_core_view", "broker_product_driver"):
        excerpt = _select_excerpt_units(cleaned, card_type)
        if excerpt:
            return excerpt
    return ""


def _allow_fallback_excerpt(text: str) -> bool:
    if _looks_like_financial_table_fragment(text):
        return False
    has_risk_heading = bool(_find_heading_positions(text, "风险提示"))
    has_non_risk_heading = any(
        _find_heading_positions(text, heading)
        for heading in _ALL_HEADINGS
        if heading != "风险提示"
    )
    if has_risk_heading and not has_non_risk_heading:
        return False
    return True


def _looks_like_risk_only(text: str) -> bool:
    if "风险" not in text and "不及预期" not in text:
        return False
    positive_terms = ("增长", "提升", "放量", "需求", "收入", "利润", "毛利率", "订单", "产能")
    if any(term in text for term in positive_terms):
        return False
    return True


def _has_knowledge_driver_candidate(candidates: List[Dict[str, Any]]) -> bool:
    return any(
        bool(card.get("knowledge_eligible"))
        and not bool(card.get("display_only"))
        and str(card.get("card_type")) == "broker_product_driver"
        for card in candidates
    )


def _generic_driver_block_excerpt(text: str) -> str:
    excerpts = _generic_driver_block_excerpts(text, max_blocks=1)
    return excerpts[0] if excerpts else ""


def _generic_driver_block_excerpts(text: str, max_blocks: int = 3) -> List[str]:
    scored: List[Tuple[int, int, str]] = []
    blocks = [_clean_driver_excerpt(block) for block in _iter_generic_driver_blocks(text)]
    damaged_count = sum(_has_severe_ocr_damage(_candidate_score_parts(block)) for block in blocks)
    if damaged_count >= _MIN_DAMAGED_GENERIC_BLOCKS and damaged_count * 2 >= len(blocks):
        return []
    for order, block in enumerate(blocks):
        if _looks_like_financial_table_fragment(block):
            continue
        if _looks_like_rating_table_fragment(block):
            continue
        block = _select_excerpt_units(block, "broker_product_driver")
        if not block:
            continue
        score = _generic_driver_score(block)
        if score <= 0:
            continue
        scored.append((score, order, block))
    if not scored:
        return []
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected: List[str] = []
    seen_clusters: set[str] = set()
    for _, _, block in scored:
        cluster = "business_driver_" + "_".join(_generic_driver_cluster_labels(block)[:2])
        if cluster in seen_clusters:
            continue
        selected.append(block)
        seen_clusters.add(cluster)
        if len(selected) >= max_blocks:
            break
    return selected


def _clean_driver_excerpt(text: str) -> str:
    text = _clean_excerpt(text)
    for marker in ("投资建议", "盈利预测", "财务数据", "财务数据与估值", "风险提示"):
        idx = text.find(marker)
        if idx >= 0:
            text = text[:idx].strip()
    return text


def _iter_generic_driver_blocks(text: str) -> List[str]:
    normalized = _normalize_text(text)
    normalized = re.sub(r"(?<!\n)([•●]\s*)", r"\n\1", normalized)
    normalized = re.sub(r"(?<!\n)([一二三四五六七八九十]+[）)]|\d+[）)])", r"\n\1", normalized)
    raw_blocks = re.split(
        r"\n{2,}|(?<=[。；;])\s+(?=(?:[一二三四五六七八九十]+[）)]|\d+[）)]|从|随着|展望|供应端|需求端|公司|业务|产品|下游))",
        normalized,
    )
    blocks: List[str] = []
    for raw in raw_blocks:
        block = re.sub(r"\s+", " ", raw).strip(" 　：:")
        if len(block) < 50:
            continue
        if any(pattern in block for pattern in _STOP_PATTERNS):
            continue
        if _looks_like_financial_table_fragment(block):
            continue
        if _looks_like_rating_table_fragment(block):
            continue
        blocks.append(block[:1200])
    return blocks


def _generic_driver_score(text: str) -> int:
    if _looks_like_financial_table_fragment(text):
        return 0
    if _looks_like_risk_only(text):
        return 0
    score = 0
    score += 3 * len(_generic_driver_cluster_labels(text))
    for term in (
        "驱动",
        "带动",
        "受益",
        "推动",
        "提升",
        "改善",
        "延续",
        "放量",
        "导入",
        "扩张",
        "升级",
        "优化",
        "释放",
        "回暖",
    ):
        if term in text:
            score += 2
    if re.search(r"\d+(?:\.\d+)?\s*(?:亿元|%|pct|倍)", text):
        score += 2
    if any(token in text for token in ("下游", "供应端", "需求端", "业务结构", "产品结构", "客户", "订单", "产能")):
        score += 3
    if any(token in text for token in ("预计", "展望", "未来", "有望")):
        score += 1
    return score


def _generic_driver_cluster_labels(text: str) -> List[str]:
    groups: List[Tuple[str, Tuple[str, ...]]] = [
        ("market_demand", ("需求", "景气", "市场", "下游", "复苏", "回暖", "资本开支", "基础设施")),
        ("product_mix", ("产品结构", "高端产品", "新品", "新产品", "升级", "迭代", "导入", "放量", "份额")),
        ("delivery_capacity", ("客户", "订单", "产能", "交付", "供应链", "上游资源", "扩充产能", "锁定资源")),
        ("profitability", ("毛利率", "净利率", "盈利能力", "规模效应", "价格", "成本", "费用率")),
        ("technology", ("研发", "技术", "平台", "工艺", "验证", "规格")),
    ]
    return [label for label, terms in groups if any(term in text for term in terms)]


def _looks_like_financial_table_fragment(text: str) -> bool:
    table_terms = (
        "营业收入",
        "营业成本",
        "销售费用",
        "管理费用",
        "研发费用",
        "归母净利润",
        "每股收益",
        "会计年度",
        "利润表",
        "资产负债表",
        "现金流量表",
        "P/E",
        "P/B",
        "ROE",
        "EPS",
    )
    term_hits = sum(1 for term in table_terms if term in text)
    year_hits = len(re.findall(r"20\d{2}[AE]?", text))
    number_hits = len(re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?%?", text))
    return term_hits >= 5 or (term_hits >= 3 and year_hits >= 3 and number_hits >= 12)


def _looks_like_rating_table_fragment(text: str) -> bool:
    rating_terms = ("买入", "增持", "中性", "减持")
    rating_hits = sum(1 for term in rating_terms if term in text)
    if "投资评级" in text and rating_hits >= 2:
        return True
    if "相关报告评级" in text and rating_hits >= 2:
        return True
    if "预期未来6" in text and rating_hits >= 2:
        return True
    if rating_hits >= 4 and len(re.findall(r"\d+(?:\.\d+)?%?", text)) >= 8:
        return True
    return False


def _has_specific_risk_signal(text: str) -> bool:
    specific_terms = (
        "物料",
        "短缺",
        "供应链",
        "出货",
        "汇兑",
        "汇率",
        "关税",
        "CSP",
        "资本开支",
        "拉货",
        "CPO",
        "NPO",
        "Scaleup",
        "份额",
        "客户集中",
        "产能",
    )
    return any(term in text for term in specific_terms)


def _viewpoint_cluster(card_type: str, excerpt: str) -> str:
    text = str(excerpt or "")
    if card_type == "broker_earnings_forecast":
        return "earnings_forecast"
    if card_type == "broker_risk_note":
        labels = []
        if any(term in text for term in ("物料", "短缺", "供应链", "出货")):
            labels.append("supply_chain")
        if any(term in text for term in ("汇兑", "汇率", "关税")):
            labels.append("fx_tariff")
        if any(term in text for term in ("CSP", "资本开支", "拉货", "北美")):
            labels.append("capex")
        if any(term in text for term in ("CPO", "NPO", "Scaleup", "份额")):
            labels.append("share")
        if not labels:
            return "risk_generic"
        return "risk_" + "_".join(labels)
    if any(term in text for term in ("营业收入", "营收", "归母净利润", "扣非", "毛利率", "ROE", "现金流")):
        labels = _generic_driver_cluster_labels(text)
        if _generic_driver_score(text) < 5 or labels == ["profitability"]:
            return "earnings_growth_snapshot"
    if card_type in {"broker_core_view", "broker_product_driver"}:
        labels = _generic_driver_cluster_labels(text)
        if labels:
            return "business_driver_" + "_".join(labels[:2])
    return f"{card_type}_other"


def _is_display_only_card(card_type: str, viewpoint_cluster: str, excerpt: str) -> bool:
    if card_type == "broker_earnings_forecast":
        return True
    if card_type == "broker_core_view" and not any(
        term in excerpt
        for term in (
            "产品",
            "客户",
            "订单",
            "产能",
            "研发",
            "业务",
            "需求",
            "导入",
            "升级",
            "结构",
            "份额",
            "交付",
            "技术",
            "收入",
            "营收",
            "利润",
            "毛利率",
            "净利率",
        )
    ):
        return True
    return False


def _looks_like_financial_snapshot_without_driver(text: str) -> bool:
    financial_terms = ("营业收入", "营收", "归母净利润", "扣非", "毛利率", "净利率", "ROE", "现金流")
    if sum(1 for term in financial_terms if term in text) < 3:
        return False
    driver_terms = (
        "下游",
        "客户",
        "订单",
        "产能",
        "交付",
        "产品结构",
        "高端产品",
        "新产品",
        "新品",
        "导入",
        "升级",
        "迭代",
        "放量",
        "份额",
        "景气",
        "需求",
        "驱动",
        "带动",
        "受益",
        "业务结构",
    )
    return not any(term in text for term in driver_terms)


def deduplicate_broker_digest_cards_by_viewpoint(
    cards: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Keep the best card per stock/viewpoint cluster while preserving distinct views."""
    best_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    order_by_key: Dict[Tuple[str, str], int] = {}
    protected_long_body_count_by_stock: Dict[str, int] = {}
    for idx, card in enumerate(cards):
        stock_key = str(card.get("stock_code") or card.get("stock_name") or "")
        institution = str(card.get("institution") or "")
        cluster = str(card.get("viewpoint_cluster") or "")
        if not cluster:
            cluster = f"{card.get('card_type', '')}:{_fingerprint(str(card.get('source_excerpt', '')))}"
        if _is_protected_long_report_body_card(card):
            count = protected_long_body_count_by_stock.get(stock_key, 0)
            if count >= 3:
                continue
            protected_long_body_count_by_stock[stock_key] = count + 1
            cluster = f"{cluster}:long_report_body:{idx}"
        key = (stock_key, cluster, institution)
        order_by_key.setdefault(key, idx)
        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = card
            continue
        current_score = int(current.get("quality_score") or 0)
        new_score = int(card.get("quality_score") or 0)
        if (new_score, len(str(card.get("source_excerpt", "")))) > (
            current_score,
            len(str(current.get("source_excerpt", ""))),
        ):
            best_by_key[key] = card

    return [
        best_by_key[key]
        for key in sorted(order_by_key, key=lambda k: order_by_key[k])
    ]


def _is_protected_long_report_body_card(card: Dict[str, Any]) -> bool:
    if str(card.get("report_length_class") or "") != "long":
        return False
    if str(card.get("card_type") or "") != "broker_product_driver":
        return False
    heading = str(card.get("source_heading") or "")
    if not heading or heading in {"投资要点", "核心观点", "事件", "观点", "点评"}:
        return False
    if str(card.get("viewpoint_cluster") or "").startswith("risk_"):
        return False
    return True


def _fingerprint(text: str) -> str:
    tokens = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", text.lower())
    return " ".join(tokens)


def _near_duplicate(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    return overlap >= 0.85
