"""Tests for source_intake_merge_skill."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from skill_pipeline import SkillContext
from source_adapter import SynthesisItem
from report_skills.source_intake_merge_skill import source_intake_merge_skill


def _make_item(
    title="t",
    url="https://example.com/a",
    source_credit=60,
    source_type="news",
    source_domain="example.com",
    verification_status="professional_observation",
    knowledge_eligible=True,
    report_eligible=True,
    quality_action="keep",
):
    return SynthesisItem(
        title=title,
        content="c",
        author="",
        source_platform="新闻",
        url=url,
        publish_time="2026-06-01",
        extra={
            "source_credit": source_credit,
            "source_type": source_type,
            "source_domain": source_domain,
            "verification_status": verification_status,
            "knowledge_eligible": knowledge_eligible,
            "report_eligible": report_eligible,
            "agent_reach_quality_action": quality_action,
        },
    )


def test_disabled_when_no_external_paths_enabled():
    ctx = SkillContext(
        input={
            "agent_reach_enabled": False,
            "source_intake_enabled": False,
        }
    )
    result = source_intake_merge_skill(ctx)
    assert result.get("source_intake_merge_status") == "disabled"
    assert result.get("external_evidence_keep_items") == []
    assert result.get("external_evidence_demote_items") == []
    assert result.get("external_evidence_discard_items") == []


def test_source_intake_only_populates_keep_items():
    item = _make_item(title="cninfo", url="https://cninfo.com.cn/a", source_credit=95, source_type="exchange_announcement")
    ctx = SkillContext(
        input={
            "agent_reach_enabled": False,
            "source_intake_enabled": True,
            "source_intake_status": "ok",
            "source_intake_items": [item],
        }
    )
    result = source_intake_merge_skill(ctx)
    assert result.get("source_intake_merge_status") == "ok"
    keep = result.get("external_evidence_keep_items")
    assert len(keep) == 1
    assert keep[0].title == "cninfo"


def test_agent_reach_only_uses_existing_buckets():
    item = _make_item(title="web", source_credit=70, source_type="web")
    ctx = SkillContext(
        input={
            "agent_reach_enabled": True,
            "source_intake_enabled": False,
            "agent_reach_keep_items": [item],
            "agent_reach_demote_items": [],
            "agent_reach_discard_items": [],
        }
    )
    result = source_intake_merge_skill(ctx)
    assert result.get("source_intake_merge_status") == "ok"
    assert len(result.get("external_evidence_keep_items")) == 1
    assert result.get("external_evidence_keep_items")[0].title == "web"


def test_merge_dedupes_by_url_prefers_higher_credit():
    ar_item = _make_item(title="ar web", url="https://cninfo.com.cn/a", source_credit=70, source_type="web")
    si_item = _make_item(title="cninfo", url="https://cninfo.com.cn/a", source_credit=95, source_type="exchange_announcement")

    ctx = SkillContext(
        input={
            "agent_reach_enabled": True,
            "source_intake_enabled": True,
            "agent_reach_keep_items": [ar_item],
            "agent_reach_demote_items": [],
            "agent_reach_discard_items": [],
            "source_intake_status": "ok",
            "source_intake_items": [si_item],
        }
    )
    result = source_intake_merge_skill(ctx)
    keep = result.get("external_evidence_keep_items")
    assert len(keep) == 1
    assert keep[0].title == "cninfo"
    assert keep[0].extra["source_credit"] == 95


def test_preferred_duplicate_replacement_keeps_first_seen_position():
    first = _make_item(title="web-a", url="https://example.com/a", source_credit=70)
    second = _make_item(title="web-b", url="https://example.com/b", source_credit=70)
    replacement = _make_item(
        title="official-a",
        url="https://example.com/a",
        source_credit=95,
        source_type="exchange_announcement",
    )
    ctx = SkillContext(input={
        "agent_reach_enabled": True,
        "source_intake_enabled": True,
        "agent_reach_keep_items": [first, second],
        "agent_reach_demote_items": [],
        "source_intake_items": [replacement],
    })

    result = source_intake_merge_skill(ctx)

    assert [item.title for item in result.get("external_evidence_keep_items")] == [
        "official-a",
        "web-b",
    ]


def test_cninfo_detail_urls_keep_distinct_announcement_ids():
    first = _make_item(
        title="一季报",
        url="http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225145344",
        source_credit=95,
        source_type="exchange_announcement",
        source_domain="cninfo.com.cn",
    )
    second = _make_item(
        title="权益分派",
        url="http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225362219",
        source_credit=95,
        source_type="exchange_announcement",
        source_domain="cninfo.com.cn",
    )
    ctx = SkillContext(
        input={
            "agent_reach_enabled": False,
            "source_intake_enabled": True,
            "source_intake_status": "ok",
            "source_intake_items": [first, second],
        }
    )

    result = source_intake_merge_skill(ctx)

    keep = result.get("external_evidence_keep_items")
    assert len(keep) == 2
    assert {item.title for item in keep} == {"一季报", "权益分派"}


def test_periodic_report_excerpt_survives_same_url_dedup():
    original = _make_item(
        title="2025年年度报告",
        url="http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225000000",
        source_credit=95,
        source_type="exchange_announcement",
        source_domain="cninfo.com.cn",
        verification_status="confirmed_fact",
    )
    excerpt = _make_item(
        title="2025年年度报告 | 管理层观点",
        url=original.url,
        source_credit=75,
        source_type="periodic_report_excerpt",
        source_domain="cninfo.com.cn",
        verification_status="management_view",
    )
    excerpt.extra["periodic_report_excerpt_id"] = "abc123-management_view-0"

    ctx = SkillContext(
        input={
            "agent_reach_enabled": False,
            "source_intake_enabled": True,
            "source_intake_status": "ok",
            "source_intake_items": [original, excerpt],
        }
    )

    result = source_intake_merge_skill(ctx)

    keep = result.get("external_evidence_keep_items")
    assert len(keep) == 2
    assert {item.extra["source_type"] for item in keep} == {"exchange_announcement", "periodic_report_excerpt"}


def test_periodic_report_fulltext_items_are_isolated_from_url_merge():
    original = _make_item(
        title="2025年年度报告",
        url="http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225000000",
        source_credit=95,
        source_type="exchange_announcement",
        source_domain="cninfo.com.cn",
        verification_status="confirmed_fact",
    )
    fulltext = _make_item(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        url=original.url,
        source_credit=75,
        source_type="periodic_report_fulltext_analysis",
        source_domain="cninfo.com.cn",
        verification_status="professional_analysis",
        knowledge_eligible=False,
        report_eligible=False,
    )
    fulltext.extra["periodic_report_fulltext_id"] = "fulltext-abc123"

    ctx = SkillContext(
        input={
            "agent_reach_enabled": False,
            "source_intake_enabled": True,
            "source_intake_status": "ok",
            "source_intake_items": [original],
            "periodic_report_fulltext_items": [fulltext],
        }
    )

    result = source_intake_merge_skill(ctx)

    keep = result.get("external_evidence_keep_items")
    assert len(keep) == 1
    assert keep[0].title == "2025年年度报告"
    assert result.get("periodic_report_fulltext_items") == [fulltext]


def test_merge_tie_prefers_source_intake_for_official():
    ar_item = _make_item(title="ar web", url="https://cninfo.com.cn/a", source_credit=95, source_type="web")
    si_item = _make_item(title="cninfo", url="https://cninfo.com.cn/a", source_credit=95, source_type="exchange_announcement")

    ctx = SkillContext(
        input={
            "agent_reach_enabled": True,
            "source_intake_enabled": True,
            "agent_reach_keep_items": [ar_item],
            "agent_reach_demote_items": [],
            "agent_reach_discard_items": [],
            "source_intake_status": "ok",
            "source_intake_items": [si_item],
        }
    )
    result = source_intake_merge_skill(ctx)
    keep = result.get("external_evidence_keep_items")
    assert len(keep) == 1
    assert keep[0].title == "cninfo"


def test_medium_credit_items_go_to_keep_when_eligible():
    item = _make_item(title="news", source_credit=60, source_type="news")
    ctx = SkillContext(
        input={
            "agent_reach_enabled": False,
            "source_intake_enabled": True,
            "source_intake_status": "ok",
            "source_intake_items": [item],
        }
    )
    result = source_intake_merge_skill(ctx)
    assert len(result.get("external_evidence_keep_items")) == 1
    assert len(result.get("external_evidence_demote_items")) == 0


def test_non_eligible_items_go_to_discard():
    item = _make_item(title="news", source_credit=60, source_type="news", knowledge_eligible=False, report_eligible=False)
    ctx = SkillContext(
        input={
            "agent_reach_enabled": False,
            "source_intake_enabled": True,
            "source_intake_status": "ok",
            "source_intake_items": [item],
        }
    )
    result = source_intake_merge_skill(ctx)
    assert len(result.get("external_evidence_keep_items")) == 0
    assert len(result.get("external_evidence_discard_items")) == 1


def test_preserves_agent_reach_backward_compatibility():
    item = _make_item(title="ar", source_credit=50, source_type="social_discussion", quality_action="demote")
    ctx = SkillContext(
        input={
            "agent_reach_enabled": True,
            "source_intake_enabled": False,
            "agent_reach_keep_items": [],
            "agent_reach_demote_items": [item],
            "agent_reach_discard_items": [],
        }
    )
    result = source_intake_merge_skill(ctx)
    assert len(result.get("external_evidence_keep_items")) == 0
    assert len(result.get("external_evidence_demote_items")) == 1
    assert result.get("external_evidence_demote_items")[0].title == "ar"


def test_does_not_mutate_input_lists():
    item = _make_item(title="cninfo")
    original_items = [item]
    ctx = SkillContext(
        input={
            "agent_reach_enabled": False,
            "source_intake_enabled": True,
            "source_intake_status": "ok",
            "source_intake_items": original_items,
        }
    )
    source_intake_merge_skill(ctx)
    assert ctx.input["source_intake_items"] is original_items
    assert len(original_items) == 1
