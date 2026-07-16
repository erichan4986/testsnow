"""Tests for synthesis_credit helpers."""

import pytest
from scripts.utils.synthesis_credit import (
    citation_identity,
    credit_usage_rules_text,
    derive_synthesis_usage,
    format_synthesis_source_line,
    is_core_fact_supporting_source,
    format_claim_verification_appendix,
    sanitize_citation_markers,
)
from scripts.utils.source_adapter import SynthesisItem


def test_credit_usage_rules_text_contains_required_rules():
    text = credit_usage_rules_text()
    assert "高信用/官方/公告/交易所来源可作为事实" in text
    assert "中信用/研报/新闻/政策/微信公众号来源只能写为" in text
    assert "verified discussion 必须写为" in text
    assert "相互印证" in text
    assert "Phase 1 不使用 corroborated schema" in text
    assert "unverified discussion 只能作为待验证观点" in text
    assert "中信用新闻/研报/微信公众号可进入风险观察文字" in text
    assert "不得生成结构化风险信号" in text


def test_sanitize_citation_markers_removes_non_numeric_refs():
    assert sanitize_citation_markers("增长[^supported]超预期") == "增长超预期"
    assert sanitize_citation_markers("增长[^needs_review]超预期") == "增长超预期"
    assert sanitize_citation_markers("增长[^unverified]超预期") == "增长超预期"
    assert sanitize_citation_markers("增长[^verified]超预期") == "增长超预期"
    assert sanitize_citation_markers("增长[^abc]超预期") == "增长超预期"
    assert sanitize_citation_markers("增长[supported]超预期") == "增长超预期"


def test_sanitize_citation_markers_preserves_numeric_refs():
    assert sanitize_citation_markers("增长[^1]超预期") == "增长[^1]超预期"
    assert sanitize_citation_markers("增长[^23]超预期[^2]") == "增长[^23]超预期[^2]"
    assert sanitize_citation_markers("增长[^1][^supported]") == "增长[^1]"


def test_citation_identity_prefers_exact_url_then_metadata_then_ref():
    assert citation_identity({"url": "https://example.com/a"}, fallback_ref=9) == (
        "url",
        "https://example.com/a",
    )
    assert citation_identity({"source": "研报", "author": "机构", "title": "正文"}) == (
        "meta",
        "研报",
        "机构",
        "正文",
    )
    assert citation_identity({}, fallback_ref="claim:c1") == ("ref", "claim:c1")


def test_credit_usage_rules_text_forbids_status_markers():
    text = credit_usage_rules_text()
    assert "[^verified]" in text or "verified 状态" in text
    assert "[^supported]" in text or "supported 状态" in text
    assert "[^needs_review]" in text or "needs_review 状态" in text
    assert "[^unverified]" in text or "unverified 状态" in text
    assert "不得进入执行摘要、核心事实、结论" in text
    assert "该线索获得部分支持，但仍非官方确认" in text


def test_format_claim_verification_appendix_forbids_status_markers():
    context = {
        "enabled": True,
        "counts": {"high_credit_claims": 1, "low_credit_claims": 1, "verified": 1, "supported": 1, "unverified": 1, "needs_review": 1},
        "verified_claims": [{"claim_text": "营收增长", "action": "verified", "confidence": 84}],
        "supported_claims": [{"claim_text": "利润上升", "action": "supported", "confidence": 60}],
    }
    text = format_claim_verification_appendix(context)
    assert "[^verified]" in text or "verified 状态" in text
    assert "[^supported]" in text or "supported 状态" in text
    assert "[^needs_review]" in text or "needs_review 状态" in text
    assert "[^unverified]" in text or "unverified 状态" in text
    assert "该线索获得部分支持，但仍非官方确认" in text


def test_derive_synthesis_usage_announcement_high():
    item = SynthesisItem(
        title="公告", content="内容", author="公司",
        source_platform="公告", url="", publish_time="",
    )
    usage = derive_synthesis_usage(item)
    assert usage["credit_tier"] == "high"
    assert usage["usage"] == "core_fact_allowed"


def test_derive_synthesis_usage_report_medium():
    item = SynthesisItem(
        title="研报", content="内容", author="券商",
        source_platform="研报", url="", publish_time="",
    )
    usage = derive_synthesis_usage(item)
    assert usage["credit_tier"] == "medium"
    assert usage["usage"] == "professional_observation"


def test_derive_synthesis_usage_news_medium():
    item = SynthesisItem(
        title="新闻", content="内容", author="媒体",
        source_platform="新闻", url="", publish_time="",
    )
    usage = derive_synthesis_usage(item)
    assert usage["credit_tier"] == "medium"
    assert usage["usage"] == "professional_observation"


def test_derive_synthesis_usage_xueqiu_low():
    item = SynthesisItem(
        title="帖子", content="内容", author="用户",
        source_platform="雪球", url="", publish_time="",
    )
    usage = derive_synthesis_usage(item)
    assert usage["credit_tier"] == "low"
    assert usage["usage"] == "discussion_only"


def test_derive_synthesis_usage_zhihu_low():
    item = SynthesisItem(
        title="回答", content="内容", author="用户",
        source_platform="知乎", url="", publish_time="",
    )
    usage = derive_synthesis_usage(item)
    assert usage["credit_tier"] == "low"
    assert usage["usage"] == "discussion_only"


def test_derive_synthesis_usage_fundflow_quantitative():
    item = SynthesisItem(
        title="资金流向", content="内容", author="",
        source_platform="资金流向", url="", publish_time="",
    )
    usage = derive_synthesis_usage(item)
    assert usage["credit_tier"] == "medium"
    assert usage["usage"] == "quantitative_observation"


def test_derive_synthesis_usage_wechat_publisher_medium():
    item = SynthesisItem(
        title="文章", content="内容", author="公众号",
        source_platform="微信公众号", url="", publish_time="",
        extra={"account": "券商研究"},
    )
    usage = derive_synthesis_usage(item)
    assert usage["credit_tier"] == "medium"
    assert usage["usage"] == "professional_observation"


def test_derive_synthesis_usage_wechat_without_account_low():
    item = SynthesisItem(
        title="文章", content="内容", author="",
        source_platform="微信公众号", url="", publish_time="",
        extra={},
    )
    usage = derive_synthesis_usage(item)
    assert usage["credit_tier"] == "low"
    assert usage["usage"] == "discussion_only"


def test_derive_synthesis_usage_agent_reach_uses_extra_credit():
    item = SynthesisItem(
        title="帖子", content="内容", author="user",
        source_platform="AgentReach(twitter)", url="", publish_time="",
        extra={"source_credit": 35, "source_type": "social_discussion"},
    )
    usage = derive_synthesis_usage(item)
    assert usage["credit_tier"] == "low"
    assert usage["usage"] == "discussion_only"


def test_derive_synthesis_usage_high_credit_confirmed_overrides_platform():
    # Even a source_platform normally rejected can become core_fact_allowed if
    # metadata explicitly marks it as a high-credit confirmed fact.
    item = SynthesisItem(
        title="文件", content="内容", author="",
        source_platform="未知平台", url="", publish_time="",
        extra={"source_credit": 95, "source_type": "exchange_announcement"},
    )
    usage = derive_synthesis_usage(item)
    assert usage["credit_tier"] == "high"
    assert usage["usage"] == "core_fact_allowed"


def test_derive_synthesis_usage_unknown_background_limited():
    item = SynthesisItem(
        title="内容", content="内容", author="",
        source_platform="SomeRandomSite", url="", publish_time="",
    )
    usage = derive_synthesis_usage(item)
    assert usage["credit_tier"] == "unknown"
    assert usage["usage"] == "background_limited"


def test_derive_synthesis_usage_accepts_dict_meta():
    meta = {"source": "研报"}
    usage = derive_synthesis_usage(meta)
    assert usage["usage"] == "professional_observation"


def test_derive_synthesis_usage_dict_meta_with_top_level_credit():
    meta = {
        "source": "某来源",
        "source_credit": 90,
        "source_type": "company_ir",
    }
    usage = derive_synthesis_usage(meta)
    assert usage["usage"] == "core_fact_allowed"


def test_format_synthesis_source_line_includes_credit_label():
    item = SynthesisItem(
        title="一季报", content="营收增长", author="公司",
        source_platform="公告", url="", publish_time="2026-04-30",
    )
    line = format_synthesis_source_line(1, item)
    assert line.startswith("[1]")
    assert "信用层: high" in line
    assert "可用方式: core_fact_allowed" in line
    assert "标题: 一季报" in line


def test_is_core_fact_supporting_source_allows_announcement():
    assert is_core_fact_supporting_source("公告") is True
    assert is_core_fact_supporting_source("announcement") is True


def test_is_core_fact_supporting_source_allows_official_and_exchange():
    assert is_core_fact_supporting_source("官方") is True
    assert is_core_fact_supporting_source("交易所") is True
    assert is_core_fact_supporting_source("巨潮") is True


def test_is_core_fact_supporting_source_rejects_news_report_community():
    assert is_core_fact_supporting_source("新闻") is False
    assert is_core_fact_supporting_source("研报") is False
    assert is_core_fact_supporting_source("雪球") is False
    assert is_core_fact_supporting_source("知乎") is False
    assert is_core_fact_supporting_source("AgentReach(twitter)") is False
    assert is_core_fact_supporting_source("资金流向") is False


def test_is_core_fact_supporting_source_rejects_wechat_without_metadata():
    assert is_core_fact_supporting_source("微信公众号") is False


def test_is_core_fact_supporting_source_allows_high_credit_metadata():
    meta = {"source_credit": 90, "source_type": "exchange_announcement"}
    assert is_core_fact_supporting_source("未知平台", meta) is True


def test_is_core_fact_supporting_source_rejects_low_credit_metadata():
    meta = {"source_credit": 30, "source_type": "social_discussion"}
    assert is_core_fact_supporting_source("雪球", meta) is False


def test_format_claim_verification_appendix_contains_required_wording():
    context = {
        "enabled": True,
        "counts": {"high_credit_claims": 1, "low_credit_claims": 1, "verified": 1, "supported": 0, "unverified": 0, "needs_review": 0},
        "verified_claims": [{"claim_text": "营收增长", "action": "verified", "confidence": 84}],
    }
    text = format_claim_verification_appendix(context)
    assert "Claim Verification Context" in text
    assert "不是新的引用来源" in text
    assert "已验证讨论线索" in text
    assert "部分支持讨论线索" in text
    assert "未验证市场讨论" in text
    assert "Phase 1 不输出 corroborated bucket" in text
    assert "社区共振/市场关注" in text


def test_format_claim_verification_appendix_disabled_returns_empty():
    assert format_claim_verification_appendix({"enabled": False}) == ""
    assert format_claim_verification_appendix(None) == ""


# --- periodic report fulltext material ---


def _fulltext_item(content="年报全文材料层内容。"):
    return SynthesisItem(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content=content,
        author="",
        source_platform="定期报告全文",
        url="",
        publish_time="2026-04-15",
        extra={
            "source_type": "periodic_report_fulltext_analysis",
            "source_credit": 75,
            "verification_status": "professional_analysis",
            "claim_status": "professional_analysis",
            "knowledge_eligible": False,
            "report_eligible": False,
            "experimental": True,
        },
    )


def test_derive_synthesis_usage_periodic_report_fulltext_is_annual_report_material():
    usage = derive_synthesis_usage(_fulltext_item())
    assert usage["credit_tier"] == "medium"
    assert usage["usage"] == "annual_report_material"
    assert usage["display_label"] == "中信用/annual_report_material"


def test_fulltext_source_type_cannot_be_promoted_by_malformed_confirmed_metadata():
    item = _fulltext_item()
    item.extra = {
        **item.extra,
        "source_credit": 95,
        "verification_status": "confirmed_fact",
    }
    usage = derive_synthesis_usage(item)
    assert usage["credit_tier"] == "medium"
    assert usage["usage"] == "annual_report_material"


def test_fulltext_is_not_core_fact_supporting():
    meta = {
        "source_credit": 75,
        "source_type": "periodic_report_fulltext_analysis",
        "verification_status": "professional_analysis",
    }
    assert is_core_fact_supporting_source("定期报告全文", meta) is False
    assert is_core_fact_supporting_source("定期报告全文") is False


def test_format_synthesis_source_line_fulltext_cap_is_1200():
    long_content = "甲" * 2000
    line = format_synthesis_source_line(1, _fulltext_item(content=long_content))
    # 1200 chars retained (cap), not 500
    assert "甲" * 1200 in line
    assert "甲" * 1201 not in line
    assert "可用方式: annual_report_material" in line


def test_format_synthesis_source_line_ordinary_cap_remains_500():
    long_content = "乙" * 2000
    item = SynthesisItem(
        title="研报", content=long_content, author="券商",
        source_platform="研报", url="", publish_time="",
    )
    line = format_synthesis_source_line(2, item)
    assert "乙" * 500 in line
    assert "乙" * 501 not in line
