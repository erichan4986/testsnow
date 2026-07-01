"""Topic-ownership rules for 4.1-4.3 deep-analysis prose.

The rules are intentionally small and deterministic. They support prompt
construction and advisory prose checks; they do not rewrite report content.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List


FINAL_SECTION_THEME_MAP: Dict[str, List[str]] = {
    "4.1": ["industry_logic"],
    "4.2": ["fundamentals", "valuation_debate"],
    "4.3": ["funding_sentiment", "events_catalysts"],
}

THEME_TO_FINAL_SECTION = {
    theme: section
    for section, themes in FINAL_SECTION_THEME_MAP.items()
    for theme in themes
}

SECTION_TOPIC_OWNERSHIP = {
    "industry_logic": {
        "owns": ["产业需求", "技术路线", "供应链位置", "竞争格局", "直接竞争对手"],
        "may_reference": ["营收", "毛利率", "订单", "资金情绪"],
        "must_not_expand": ["季度利润路径", "估值多空", "融资盘", "催化剂时间线"],
    },
    "fundamentals": {
        "owns": ["营收", "利润", "毛利率", "费用率", "订单兑现", "客户结构", "业绩指引"],
        "may_reference": ["行业景气", "技术路线", "竞争格局"],
        "must_not_expand": ["完整产业背景", "资金流", "融资余额", "交易情绪"],
    },
    "valuation_debate": {
        "owns": ["估值分歧", "多空情景", "关键验证变量", "市场预期差"],
        "may_reference": ["业绩变量", "产业变量"],
        "must_not_expand": ["产业历史", "完整财务复盘", "资金面时间线"],
    },
    "funding_sentiment": {
        "owns": ["主力资金", "融资余额", "机构/北向", "市场情绪", "短期交易结构"],
        "may_reference": ["业绩兑现", "产业催化"],
        "must_not_expand": ["完整产业技术路线", "完整业绩路径"],
    },
    "events_catalysts": {
        "owns": ["时间点", "事件", "政策催化", "业绩披露节点", "验证指标"],
        "may_reference": ["产业变量", "业绩变量"],
        "must_not_expand": ["完整产业背景", "完整业绩路径", "交易建议"],
    },
}

TOPIC_FAMILIES = [
    {
        "family": "高速光互连技术路线",
        "terms": ["AI算力", "800G", "1.6T", "硅光", "CPO", "NPO", "XPO", "英伟达", "谷歌", "北美云厂商"],
        "owner_theme": "industry_logic",
        "owner_section": "4.1",
    },
    {
        "family": "智能驾驶芯片技术路线",
        "terms": ["A2000", "A1000", "C1296", "L3", "L4", "Robotaxi", "ASIL-D", "舱驾一体"],
        "owner_theme": "industry_logic",
        "owner_section": "4.1",
    },
    {
        "family": "模拟芯片产品技术路线",
        "terms": ["信号链", "电源管理", "车规", "数据中心", "GaN", "ADC"],
        "owner_theme": "industry_logic",
        "owner_section": "4.1",
    },
    {
        "family": "业绩质量变量",
        "terms": ["营收", "利润", "毛利率", "费用率", "订单", "客户结构"],
        "owner_theme": "fundamentals",
        "owner_section": "4.2",
    },
    {
        "family": "估值与预期差",
        "terms": ["估值", "目标价", "市盈率", "预期差", "情景"],
        "owner_theme": "valuation_debate",
        "owner_section": "4.2",
    },
    {
        "family": "交易资金结构",
        "terms": ["融资盘", "融资余额", "主力资金", "北向资金", "机构持仓", "卖空比例"],
        "owner_theme": "funding_sentiment",
        "owner_section": "4.3",
    },
    {
        "family": "事件催化与验证点",
        "terms": ["半年报", "季报", "年报", "披露", "量产", "定点", "政策催化", "时间点"],
        "owner_theme": "events_catalysts",
        "owner_section": "4.3",
    },
]


def final_section_for_theme(theme_key: str) -> str:
    return THEME_TO_FINAL_SECTION.get(theme_key, "")


def sibling_themes_for_theme(theme_key: str) -> List[str]:
    section = final_section_for_theme(theme_key)
    if not section:
        return [theme_key]
    return FINAL_SECTION_THEME_MAP.get(section, [theme_key])


def matching_topic_families(text: str) -> List[dict]:
    matches = []
    for family in TOPIC_FAMILIES:
        terms = [term for term in family["terms"] if _contains_term(text, term)]
        if terms:
            matches.append({**family, "matched_terms": terms})
    return matches


def format_topic_ownership_contract(theme_key: str) -> str:
    ownership = SECTION_TOPIC_OWNERSHIP.get(theme_key)
    if not ownership:
        return ""

    final_section = final_section_for_theme(theme_key)
    sibling_themes = ", ".join(sibling_themes_for_theme(theme_key))
    lines = [
        "主题归属与重复控制：",
        f"- 最终报告章节: {final_section or 'unknown'}",
        f"- 同属最终章节的内部主题: {sibling_themes}",
        f"- 本主题拥有: {'、'.join(ownership['owns'])}",
        f"- 可短句借用: {'、'.join(ownership['may_reference'])}",
        f"- 禁止重复展开: {'、'.join(ownership['must_not_expand'])}",
        "- 借用主题预算: 非本主题拥有的概念最多用一句话交代与本节变量的关系，且不超过110个中文字符；不要在多个段落或多行表格中重复展开。",
        "- 不要输出 ## 或 ### 子标题；如需小标题，使用加粗行内标签。",
    ]
    return "\n".join(lines)


def format_previous_topic_ledger(previous_narratives: Dict[str, str], theme_titles: Dict[str, str]) -> str:
    if not previous_narratives:
        return ""

    lines = ["已展开主题："]
    found = False
    for theme_key, text in previous_narratives.items():
        families = matching_topic_families(text or "")
        if not families:
            continue
        found = True
        final_section = final_section_for_theme(theme_key)
        title = theme_titles.get(theme_key, theme_key)
        section_prefix = f"{final_section} " if final_section else ""
        lines.append(f"- {section_prefix}{title}:")
        for family in families[:6]:
            terms = " / ".join(family["matched_terms"][:8])
            lines.append(f"  - {family['family']}: {terms}")

    if not found:
        return ""

    lines.extend([
        "",
        "本节规则：",
        "- 如果必须引用上述主题，只能用一句话说明与本节变量的关系。",
        "- 不要再次解释已展开主题的背景、技术路线或完整财务路径。",
    ])
    return "\n".join(lines)


def _contains_term(text: str, term: str) -> bool:
    return re.search(re.escape(term), text or "", flags=re.IGNORECASE) is not None

