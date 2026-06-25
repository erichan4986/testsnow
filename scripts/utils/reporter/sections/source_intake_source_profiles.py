"""Source Intake source-type display profiles.

This module keeps source taxonomy, display labels, ordering, and status
guardrails out of the Markdown renderer. New display-only sources should be
declared here instead of adding more conditionals to the renderer.
"""

from __future__ import annotations


SOURCE_TYPE_LABELS = {
    "exchange_announcement": "官方公告",
    "periodic_report_excerpt": "定期报告摘录",
    "periodic_report_fulltext_analysis": "定期报告全文摘要",
    "news": "东方财富新闻",
    "research_report": "券商研报摘要",
    "industry_research": "行业研报",
}

SOURCE_TYPE_PRIORITY = {
    "exchange_announcement": 0,
    "periodic_report_excerpt": 1,
    "periodic_report_fulltext_analysis": 2,
    "research_report": 3,
    "industry_research": 4,
    "news": 5,
}

PERIODIC_STATUS_LABELS = {
    "risk_disclosure": "风险披露",
    "management_view": "管理层观点",
    "capital_action": "资本事项",
    "financial_forensics": "财报排雷观察",
}

_PERIODIC_ALLOWED_STATUSES = set(PERIODIC_STATUS_LABELS)
_PROFESSIONAL_OBSERVATION_TYPES = {
    "news",
    "research_report",
    "industry_research",
}


def source_type_label(source_type: str) -> str:
    return SOURCE_TYPE_LABELS.get(_normalize_source_type(source_type), "其他来源")


def source_type_priority(source_type: str) -> int:
    return SOURCE_TYPE_PRIORITY.get(_normalize_source_type(source_type), 99)


def source_type_purpose(source_type: str) -> str:
    normalized = _normalize_source_type(source_type)
    if normalized == "exchange_announcement":
        return "可用于事实确认"
    if normalized == "periodic_report_excerpt":
        return "年报/半年报规则摘录"
    if normalized == "periodic_report_fulltext_analysis":
        return "年报/半年报全文材料层"
    if normalized == "news":
        return "背景资讯"
    return "专业观察"


def normalize_verification_status(source_type: str, status: str) -> str:
    normalized = _normalize_source_type(source_type)
    normalized_status = str(status or "").lower().strip()

    if normalized in _PROFESSIONAL_OBSERVATION_TYPES:
        return "professional_observation"
    if normalized == "periodic_report_excerpt":
        return normalized_status if normalized_status in _PERIODIC_ALLOWED_STATUSES else "management_view"
    if normalized == "periodic_report_fulltext_analysis":
        return "professional_analysis"
    return normalized_status if normalized_status else "unknown"


def periodic_status_label(status: str) -> str:
    return PERIODIC_STATUS_LABELS.get(str(status or "").lower().strip(), "管理层观点")


def _normalize_source_type(source_type: str) -> str:
    return str(source_type or "").lower().strip()
