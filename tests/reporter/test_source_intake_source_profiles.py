import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from reporter.sections.source_intake_source_profiles import (
    source_type_label,
    source_type_priority,
    source_type_purpose,
    normalize_verification_status,
)


def test_known_source_profiles_expose_display_labels_priority_and_purpose():
    assert source_type_label("industry_research") == "行业研报"
    assert source_type_priority("industry_research") == 4
    assert source_type_purpose("industry_research") == "专业观察"

    assert source_type_label("news") == "东方财富新闻"
    assert source_type_purpose("news") == "背景资讯"


def test_unknown_source_profile_falls_back_to_other_source():
    assert source_type_label("wechat_article") == "其他来源"
    assert source_type_priority("wechat_article") == 99
    assert source_type_purpose("wechat_article") == "专业观察"


def test_medium_credit_statuses_are_guarded_from_confirmed_fact():
    assert normalize_verification_status("news", "confirmed_fact") == "professional_observation"
    assert normalize_verification_status("research_report", "confirmed_fact") == "professional_observation"
    assert normalize_verification_status("industry_research", "confirmed_fact") == "professional_observation"


def test_periodic_and_fulltext_statuses_are_normalized_by_profile():
    assert normalize_verification_status("periodic_report_excerpt", "financial_forensics") == "financial_forensics"
    assert normalize_verification_status("periodic_report_excerpt", "confirmed_fact") == "management_view"
    assert normalize_verification_status("periodic_report_fulltext_analysis", "confirmed_fact") == "professional_analysis"
