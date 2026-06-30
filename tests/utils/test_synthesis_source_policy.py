from scripts.utils.source_adapter import SynthesisItem
from scripts.utils.synthesis_source_policy import (
    classify_synthesis_source,
    is_bridge_summary_source,
    is_canonical_synthesis_source,
    is_external_viewpoint_source,
    is_formal_display_source,
)


def _item(source_platform: str, source_type: str = "", **extra) -> SynthesisItem:
    payload = dict(extra)
    if source_type:
        payload["source_type"] = source_type
    return SynthesisItem(
        title="测试来源",
        content="测试内容",
        author="作者",
        source_platform=source_platform,
        url="https://example.com",
        publish_time="2026-06-30",
        extra=payload,
    )


def test_policy_allows_formal_sources_for_canonical_synthesis():
    assert is_canonical_synthesis_source(_item("公告", "exchange_announcement")) is True
    assert is_canonical_synthesis_source(_item("研报", "broker_research")) is True
    assert is_canonical_synthesis_source(_item("新闻", "mainstream_media")) is True
    assert is_canonical_synthesis_source(_item("资金流向")) is True


def test_policy_rejects_social_and_curated_external_from_canonical_synthesis():
    assert is_canonical_synthesis_source(_item("雪球")) is False
    assert is_canonical_synthesis_source(_item("知乎")) is False
    assert is_canonical_synthesis_source(_item("微信公众号", "article", account="行业号")) is False
    assert is_canonical_synthesis_source(_item("微信公众号精选观察", "curated_external_analysis_evidence")) is False
    assert is_canonical_synthesis_source(_item("雪球专栏观察", "social_viewpoint_analysis_evidence")) is False


def test_policy_allows_formal_display_supplements_but_not_social_viewpoints():
    annual_card = _item(
        "定期报告叙事卡片",
        "periodic_report_narrative_evidence",
        synthesis_display_only=True,
    )
    broker_digest = _item(
        "券商研报",
        "broker_research",
        synthesis_display_only=True,
        verification_status="professional_observation",
    )
    social_digest = _item(
        "知乎精选观察",
        "social_viewpoint_analysis_evidence",
        synthesis_display_only=True,
    )

    assert is_formal_display_source(annual_card) is True
    assert is_formal_display_source(broker_digest) is True
    assert is_formal_display_source(social_digest) is False
    assert is_external_viewpoint_source(social_digest) is True


def test_policy_marks_verified_social_bridge_as_bridge_only():
    bridge = _item(
        "雪球",
        "verified_social_bridge_summary",
        verification_status="verified_discussion",
    )
    policy = classify_synthesis_source(bridge)

    assert policy["layer"] == "bridge_summary"
    assert is_bridge_summary_source(bridge) is True
    assert is_canonical_synthesis_source(bridge) is False
    assert is_formal_display_source(bridge) is False
    assert is_external_viewpoint_source(bridge) is False
