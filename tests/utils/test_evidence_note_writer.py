"""Tests for evidence_note_writer module."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

import evidence_note_writer as evidence_writer_module
from evidence_note_writer import (
    EvidenceWritePlan,
    _build_filename,
    _canonical_key,
    _canonical_url,
    _classify_topics,
    _claim_status,
    _dedupe_existing,
    _find_unique_path,
    _parse_date_to_yyyymmdd,
    _safe_filename_segment,
    _short_hash,
    write_evidence_notes,
)
from source_adapter import SynthesisItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(
    *,
    title: str = "",
    content: str = "",
    url: str = "",
    publish_time: str = "",
    source_platform: str = "AgentReach(web)",
    source_credit: int = 50,
    source_type: str = "unknown_web",
    source_domain: str = "",
    verification_status: str = "unverified",
    credit_reasons=None,
    knowledge_eligible: bool = True,
    report_eligible: bool = False,
    quality_score: int = 0,
    quality_action: str = "keep",
) -> SynthesisItem:
    if credit_reasons is None:
        credit_reasons = []
    return SynthesisItem(
        title=title,
        content=content,
        author="",
        source_platform=source_platform,
        url=url,
        publish_time=publish_time,
        interaction_score=0,
        extra={
            "raw": {},
            "source_credit": source_credit,
            "source_type": source_type,
            "source_domain": source_domain,
            "verification_status": verification_status,
            "credit_reasons": credit_reasons,
            "knowledge_eligible": knowledge_eligible,
            "report_eligible": report_eligible,
            "agent_reach_quality_score": quality_score,
            "agent_reach_quality_action": quality_action,
        },
    )


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------


def test_canonical_url_normalization():
    assert _canonical_url("https://www.Example.COM/path/?q=1") == "example.com/path"
    assert _canonical_url("http://example.com/path/") == "example.com/path"
    assert _canonical_url("not a url") == ""
    assert _canonical_url("") == ""


def test_canonical_url_preserves_cninfo_disclosure_identity():
    url_a = (
        "http://www.cninfo.com.cn/new/disclosure/detail?"
        "stockCode=300777&announcementId=1225145344&orgId=9900034129"
        "&announcementTime=2026-04-23%2000:00:00"
    )
    url_b = (
        "http://www.cninfo.com.cn/new/disclosure/detail?"
        "stockCode=300777&announcementId=1225106812&orgId=9900034129"
        "&announcementTime=2026-04-15%2018:22:28"
    )

    assert _canonical_url(url_a) == "cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225145344"
    assert _canonical_url(url_b) == "cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225106812"
    assert _canonical_url(url_a) != _canonical_url(url_b)


def test_safe_filename_segment():
    assert _safe_filename_segment("Hello World!") == "hello-world"
    assert _safe_filename_segment("中文.test") == "test"
    assert _safe_filename_segment("") == ""
    assert _safe_filename_segment("a--b") == "a-b"


def test_parse_date_to_yyyymmdd():
    assert _parse_date_to_yyyymmdd("2026-06-12") == "20260612"
    assert _parse_date_to_yyyymmdd("2026/06/12") == "20260612"
    assert _parse_date_to_yyyymmdd("2026-06-12T10:30:00+08:00") == "20260612"
    assert _parse_date_to_yyyymmdd("") is None
    assert _parse_date_to_yyyymmdd("invalid") is None


def test_claim_status_mapping():
    assert _claim_status(85) == "fact_candidate"
    assert _claim_status(80) == "fact_candidate"
    assert _claim_status(72) == "professional_analysis"
    assert _claim_status(55) == "professional_analysis"
    assert _claim_status(35) == "unverified_claim"
    assert _claim_status(30) == "unverified_claim"
    assert _claim_status(29) is None
    assert _claim_status(10) is None


def test_short_hash_is_stable():
    item = _make_item(url="https://example.com/article", title="t")
    h1 = _short_hash(item)
    h2 = _short_hash(item)
    assert h1 == h2
    assert len(h1) == 8


def test_canonical_key_uses_url_when_available():
    item = _make_item(url="https://example.com/article", title="t")
    assert _canonical_key(item) == "example.com/article"


def test_canonical_key_fallback_when_no_url():
    item = _make_item(url="", source_platform="AgentReach(twitter)", title="t", publish_time="2026-06-01")
    key = _canonical_key(item)
    assert key  # non-empty hash
    assert "example.com" not in key


# ---------------------------------------------------------------------------
# Filename / path helpers
# ---------------------------------------------------------------------------


def test_build_filename_with_all_fields():
    item = _make_item(
        title="t",
        url="https://www.blacksesame.com/zh/list_10/972.html",
        publish_time="2026-06-08",
        source_type="company_official",
        source_domain="blacksesame.com",
    )
    filename = _build_filename(item, collected_at="2026-06-12T10:30:00+08:00")
    assert filename.startswith("20260608-company-official-blacksesame-com-")
    assert filename.endswith(".md")


def test_build_filename_uses_collected_at_when_publish_time_missing():
    item = _make_item(
        title="t",
        source_type="social_discussion",
        source_domain="xueqiu.com",
    )
    filename = _build_filename(item, collected_at="2026-06-12T10:30:00+08:00")
    assert filename.startswith("20260612-social-discussion-xueqiu-com-")


def test_build_filename_uses_unknown_date_when_both_missing():
    item = _make_item(title="t", source_type="unknown_web", source_domain="example.com")
    filename = _build_filename(item, collected_at=None)
    assert filename.startswith("unknown-date-unknown-web-example-com-")


def test_build_filename_empty_domain_uses_no_domain():
    item = _make_item(title="t", source_type="social_discussion", source_domain="")
    filename = _build_filename(item, collected_at="2026-06-12")
    assert "-no-domain-" in filename


def test_find_unique_path_appends_counter(tmp_path):
    existing = tmp_path / "note.md"
    existing.write_text("x")
    path1 = _find_unique_path(tmp_path, "note.md")
    assert path1 == tmp_path / "note-1.md"
    path1.write_text("x")
    path2 = _find_unique_path(tmp_path, "note.md")
    assert path2 == tmp_path / "note-2.md"


def test_find_unique_path_returns_same_if_free(tmp_path):
    path = _find_unique_path(tmp_path, "note.md")
    assert path == tmp_path / "note.md"


def test_safe_filename_prevents_path_traversal():
    segment = _safe_filename_segment("../etc/passwd")
    assert ".." not in segment
    assert "/" not in segment


# ---------------------------------------------------------------------------
# Topic classification
# ---------------------------------------------------------------------------


def test_classify_topics_fallback_for_known_keywords():
    item = _make_item(title="芯片量产良率达到95%", content="")
    topics = _classify_topics(item)
    assert topics == ["product_progress"]


def test_classify_topics_fallback_to_verify():
    item = _make_item(title="随机内容", content="没有任何主题关键词")
    topics = _classify_topics(item)
    assert topics == ["to_verify"]


# ---------------------------------------------------------------------------
# write_evidence_notes: happy path and tiers
# ---------------------------------------------------------------------------


def test_high_credit_official_item_dry_run_generates_fact_candidate(tmp_path):
    item = _make_item(
        title="黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证",
        content="2026年6月8日，黑芝麻智能宣布其华山A2000U、A2000X芯片获得ISO 26262 ASIL-D功能安全认证。",
        url="https://www.blacksesame.com/zh/list_10/972.html",
        publish_time="2026-06-08",
        source_type="company_official",
        source_domain="blacksesame.com",
        source_credit=85,
        verification_status="primary_source",
        credit_reasons=["公司官网域名: blacksesame.com"],
        report_eligible=True,
        quality_score=72,
        quality_action="keep",
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        collected_at="2026-06-12T10:30:00+08:00",
        dry_run=True,
    )
    assert len(plan.written) == 1
    assert len(plan.skipped_existing) == 0
    assert len(plan.filtered) == 0
    assert "fact_candidate" in plan.written[0]["reason"]
    assert plan.written[0]["planned_path"].endswith(".md")
    assert not (tmp_path / "10-Stocks" / "黑芝麻智能" / "evidence").exists()


def test_official_announcement_extracts_key_fact_claims(tmp_path):
    item = _make_item(
        title="中简科技2026年第一季度业绩预告",
        content=(
            "报告期内，影响公司业绩变动的主要原因：1、客户对公司部分产品的需求量阶段性减少"
            "导致发货暂时减少，其中收入下降约 50%-60%。"
            "2、围绕新领域的应用需求，公司持续加大研发投入，研发费用同比增长约 175%-185%。"
        ),
        url=(
            "http://www.cninfo.com.cn/new/disclosure/detail?"
            "stockCode=300777&announcementId=1225106812&orgId=9900034129"
        ),
        source_type="exchange_announcement",
        source_domain="cninfo.com.cn",
        source_credit=98,
        verification_status="primary_source",
        credit_reasons=["交易所/监管公告域名: cninfo.com.cn"],
        report_eligible=True,
    )

    write_evidence_notes(
        stock_name="中简科技",
        stock_code="300777",
        items=[item],
        base_dir=tmp_path,
        collected_at="2026-06-14T19:00:00+08:00",
        dry_run=False,
    )

    evidence_dir = tmp_path / "10-Stocks" / "中简科技" / "evidence"
    written = next(evidence_dir.glob("*.md"))
    content = written.read_text(encoding="utf-8")
    assert "客户对公司部分产品的需求量阶段性减少导致发货暂时减少，其中收入下降约 50%-60%" in content
    assert "研发费用同比增长约 175%-185%" in content
    assert "extracted_from: official_content_rule" in content
    assert "earnings_business" in content
    assert "customer_orders" in content


def test_dry_run_does_not_write_files(tmp_path):
    item = _make_item(
        title="t",
        source_credit=85,
        source_type="company_official",
        source_domain="example.com",
    )
    write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=True,
    )
    assert not (tmp_path / "10-Stocks").exists()


def test_dry_run_false_writes_note_to_tmp_path(tmp_path):
    item = _make_item(
        title="黑芝麻智能发布新芯片",
        content="新芯片已经量产，良率达到95%。",
        url="https://www.blacksesame.com/zh/news/1.html",
        publish_time="2026-06-10",
        source_type="company_official",
        source_domain="blacksesame.com",
        source_credit=85,
        verification_status="primary_source",
        credit_reasons=["公司官网域名: blacksesame.com"],
        quality_score=70,
        quality_action="keep",
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        collected_at="2026-06-12T10:30:00+08:00",
        dry_run=False,
    )
    assert len(plan.written) == 1
    evidence_dir = tmp_path / "10-Stocks" / "黑芝麻智能" / "evidence"
    assert evidence_dir.exists()
    files = list(evidence_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "# 黑芝麻智能发布新芯片" in content
    assert "claim_status: fact_candidate" in content
    assert "source_credit: 85" in content
    assert "verification_status: primary_source" in content


def test_social_low_credit_item_generates_unverified_claim(tmp_path):
    item = _make_item(
        title="雪球用户讨论黑芝麻智能",
        content="感觉黑芝麻智能最近热度不错。",
        url="https://xueqiu.com/123/456",
        publish_time="2026-06-11",
        source_type="social_discussion",
        source_domain="xueqiu.com",
        source_credit=35,
        verification_status="market_opinion",
        credit_reasons=["社交/讨论平台: xueqiu.com"],
        quality_score=45,
        quality_action="demote",
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=True,
    )
    assert len(plan.written) == 1
    assert "unverified_claim" in plan.written[0]["reason"]


def test_broker_medium_credit_item_generates_professional_analysis(tmp_path):
    item = _make_item(
        title="国信证券：黑芝麻智能深度报告",
        content="目标价上调，维持买入评级。",
        url="https://example.com/report/1",
        publish_time="2026-06-09",
        source_type="broker_research",
        source_domain="example.com",
        source_credit=72,
        verification_status="professional_analysis",
        credit_reasons=["券商/机构研报来源"],
        quality_score=65,
        quality_action="keep",
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=True,
    )
    assert len(plan.written) == 1
    assert "professional_analysis" in plan.written[0]["reason"]


def test_mainstream_media_credit_item_generates_professional_analysis(tmp_path):
    item = _make_item(
        title="东方财富：黑芝麻智能量产进展",
        content="媒体采访获悉，公司芯片已量产。",
        url="https://finance.eastmoney.com/a/202606091234567890.html",
        publish_time="2026-06-09",
        source_type="mainstream_media",
        source_domain="finance.eastmoney.com",
        source_credit=65,
        verification_status="secondary_source",
        credit_reasons=["主流财经媒体域名: finance.eastmoney.com"],
        quality_score=55,
        quality_action="demote",
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=True,
    )
    assert len(plan.written) == 1
    assert "professional_analysis" in plan.written[0]["reason"]


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def test_knowledge_eligible_false_is_filtered(tmp_path):
    item = _make_item(
        title="t",
        source_credit=10,
        source_type="missing_source",
        knowledge_eligible=False,
        quality_action="keep",
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=True,
    )
    assert len(plan.filtered) == 1  # first matching filter wins
    # source_credit < 30 is also true, but we stop at the first filter.
    assert "knowledge_eligible=False" in plan.filtered[0]["reason"]
    assert len(plan.written) == 0


def test_source_credit_below_30_is_filtered(tmp_path):
    item = _make_item(
        title="t",
        source_credit=25,
        source_type="unknown_web",
        source_domain="blog.com",
        knowledge_eligible=True,
        quality_action="keep",
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=True,
    )
    assert len(plan.filtered) == 1
    assert "below 30" in plan.filtered[0]["reason"]
    assert len(plan.written) == 0


def test_discard_action_is_filtered(tmp_path):
    item = _make_item(
        title="t",
        source_credit=35,
        source_type="social_discussion",
        source_domain="xueqiu.com",
        quality_action="discard",
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=True,
    )
    assert len(plan.filtered) == 1
    assert "discard" in plan.filtered[0]["reason"]
    assert len(plan.written) == 0


def test_missing_source_credit_metadata_is_filtered(tmp_path):
    item = SynthesisItem(
        title="t",
        content="c",
        author="",
        source_platform="AgentReach(web)",
        url="https://example.com",
        publish_time="2026-06-01",
        extra={"raw": {}},
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=True,
    )
    assert len(plan.filtered) == 1
    assert "missing source-credit metadata" in plan.filtered[0]["reason"]


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def test_duplicate_canonical_url_second_call_skips(tmp_path):
    item = _make_item(
        title="黑芝麻智能发布新芯片",
        content="新芯片已经量产。",
        url="https://www.blacksesame.com/zh/news/1.html",
        publish_time="2026-06-10",
        source_type="company_official",
        source_domain="blacksesame.com",
        source_credit=85,
    )
    plan1 = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=False,
    )
    assert len(plan1.written) == 1

    plan2 = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=False,
    )
    assert len(plan2.written) == 0
    assert len(plan2.skipped_existing) == 1
    assert "already exists" in plan2.skipped_existing[0]["reason"]


def test_duplicate_with_fresh_detail_content_refreshes_existing_note(tmp_path):
    old_item = _make_item(
        title="中简科技2026年第一季度业绩预告",
        content="中简科技2026年第一季度业绩预告",
        url=(
            "http://www.cninfo.com.cn/new/disclosure/detail?"
            "stockCode=300777&announcementId=1225106812&orgId=9900034129"
        ),
        source_type="exchange_announcement",
        source_domain="cninfo.com.cn",
        source_credit=95,
        verification_status="confirmed_fact",
        report_eligible=True,
    )
    first = write_evidence_notes(
        stock_name="中简科技",
        stock_code="300777",
        items=[old_item],
        base_dir=tmp_path,
        dry_run=False,
    )
    assert len(first.written) == 1
    existing_path = Path(first.written[0]["planned_path"])
    old_text = existing_path.read_text(encoding="utf-8")
    assert "official_content_rule" not in old_text

    fresh_item = _make_item(
        title="中简科技2026年第一季度业绩预告",
        content=(
            "报告期内，客户对公司部分产品的需求量阶段性减少导致发货暂时减少，"
            "其中收入下降约 50%-60%。研发费用同比增长约 175%-185%。"
        ),
        url=old_item.url,
        source_type="exchange_announcement",
        source_domain="cninfo.com.cn",
        source_credit=95,
        verification_status="confirmed_fact",
        report_eligible=True,
    )
    fresh_item.extra["detail_content_status"] = "ok"

    second = write_evidence_notes(
        stock_name="中简科技",
        stock_code="300777",
        items=[fresh_item],
        base_dir=tmp_path,
        dry_run=False,
    )

    assert len(second.written) == 1
    assert second.written[0]["reason"] == "refreshed_existing_detail_content"
    assert second.written[0]["planned_path"] == str(existing_path)
    assert len(second.skipped_existing) == 0
    refreshed = existing_path.read_text(encoding="utf-8")
    assert "official_content_rule" in refreshed
    assert "收入下降约 50%-60%" in refreshed
    assert "研发费用同比增长约 175%-185%" in refreshed


def test_no_url_item_uses_fallback_key_and_writes(tmp_path):
    item = _make_item(
        title="黑芝麻智能 某讨论",
        content="讨论内容。",
        url="",
        publish_time="2026-06-11",
        source_type="social_discussion",
        source_domain="",
        source_credit=35,
        quality_action="demote",
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=False,
    )
    assert len(plan.written) == 1
    evidence_dir = tmp_path / "10-Stocks" / "黑芝麻智能" / "evidence"
    files = list(evidence_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "canonical_url:" in content


def test_existing_frontmatter_canonical_url_recognized(tmp_path):
    evidence_dir = tmp_path / "10-Stocks" / "黑芝麻智能" / "evidence"
    evidence_dir.mkdir(parents=True)
    existing = evidence_dir / "existing.md"
    existing.write_text(
        "---\n"
        "stock: 黑芝麻智能\n"
        "code: '02533'\n"
        "url: https://www.blacksesame.com/zh/news/1.html\n"
        "canonical_url: blacksesame.com/zh/news/1\n"
        "---\n\n# Existing\n",
        encoding="utf-8",
    )

    item = _make_item(
        title="黑芝麻智能发布新芯片",
        content="新芯片已经量产。",
        url="https://www.blacksesame.com/zh/news/1.html",
        source_type="company_official",
        source_domain="blacksesame.com",
        source_credit=85,
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=False,
    )
    assert len(plan.skipped_existing) == 1
    assert len(plan.written) == 0


def test_existing_frontmatter_canonical_url_recognized_without_pyyaml(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_writer_module, "yaml", None)
    evidence_dir = tmp_path / "10-Stocks" / "黑芝麻智能" / "evidence"
    evidence_dir.mkdir(parents=True)
    existing = evidence_dir / "existing.md"
    existing.write_text(
        "---\n"
        "stock: 黑芝麻智能\n"
        "canonical_url: blacksesame.com/zh/news/1\n"
        "source_credit: 85\n"
        "---\n\n# Existing\n",
        encoding="utf-8",
    )

    item = _make_item(
        title="黑芝麻智能发布新芯片",
        content="新芯片已经量产。",
        url="https://www.blacksesame.com/zh/news/1.html",
        source_type="company_official",
        source_domain="blacksesame.com",
        source_credit=85,
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=False,
    )
    assert len(plan.skipped_existing) == 1
    assert len(plan.written) == 0


def test_dry_run_detects_existing_canonical_url(tmp_path):
    evidence_dir = tmp_path / "10-Stocks" / "黑芝麻智能" / "evidence"
    evidence_dir.mkdir(parents=True)
    existing = evidence_dir / "existing.md"
    existing.write_text(
        "---\n"
        "canonical_url: example.com/article\n"
        "---\n\n# Existing\n",
        encoding="utf-8",
    )

    item = _make_item(
        title="t",
        url="https://example.com/article",
        source_credit=85,
        source_type="company_official",
        source_domain="example.com",
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=True,
    )
    assert len(plan.skipped_existing) == 1


def test_write_evidence_note_without_pyyaml(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_writer_module, "yaml", None)
    item = _make_item(
        title="黑芝麻智能发布新芯片",
        content="新芯片已经量产，良率达到95%。",
        url="https://www.blacksesame.com/zh/news/1.html",
        publish_time="2026-06-10",
        source_type="company_official",
        source_domain="blacksesame.com",
        source_credit=85,
        verification_status="primary_source",
        credit_reasons=["公司官网域名: blacksesame.com"],
        quality_score=70,
        quality_action="keep",
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        collected_at="2026-06-12T10:30:00+08:00",
        dry_run=False,
    )
    assert len(plan.written) == 1
    path = Path(plan.written[0]["planned_path"])
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert "source_credit: 85" in content
    assert "claim_status: fact_candidate" in content
    assert "- 公司官网域名: blacksesame.com" in content


# ---------------------------------------------------------------------------
# Field passthrough
# ---------------------------------------------------------------------------


def test_source_credit_fields_passthrough_from_extra(tmp_path):
    item = _make_item(
        title="t",
        url="https://example.com/article",
        source_credit=65,
        source_type="mainstream_media",
        source_domain="example.com",
        verification_status="secondary_source",
        credit_reasons=["Reason A", "Reason B"],
        knowledge_eligible=True,
        report_eligible=True,
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=False,
    )
    assert len(plan.written) == 1
    path = Path(plan.written[0]["planned_path"])
    content = path.read_text(encoding="utf-8")
    assert "source_credit: 65" in content
    assert "source_type: mainstream_media" in content
    assert "source_domain: example.com" in content
    assert "verification_status: secondary_source" in content
    assert "- Reason A" in content
    assert "- Reason B" in content
    assert "knowledge_eligible: true" in content
    assert "report_eligible: true" in content


def test_source_credit_not_recomputed(tmp_path):
    """Writer must trust caller-provided source_credit and not recompute it."""
    item = _make_item(
        title="t",
        url="https://www.zhihu.com/question/123",
        source_credit=999,
        source_type="social_discussion",
        source_domain="zhihu.com",
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=False,
    )
    assert len(plan.written) == 1
    path = Path(plan.written[0]["planned_path"])
    content = path.read_text(encoding="utf-8")
    assert "source_credit: 999" in content
    assert "claim_status: fact_candidate" in content


def test_periodic_report_excerpt_never_becomes_fact_candidate(tmp_path):
    item = _make_item(
        title="2025年年度报告 | 财报排雷观察",
        content="存货周转和应收账款需要结合附注继续核查。",
        url="http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300777&announcementId=1225000000",
        source_type="periodic_report_excerpt",
        source_domain="cninfo.com.cn",
        source_credit=95,
        verification_status="financial_forensics",
        knowledge_eligible=True,
        report_eligible=True,
    )
    plan = write_evidence_notes(
        stock_name="中简科技",
        stock_code="300777",
        items=[item],
        base_dir=tmp_path,
        dry_run=False,
    )

    assert len(plan.written) == 1
    path = Path(plan.written[0]["planned_path"])
    content = path.read_text(encoding="utf-8")
    assert "source_credit: 95" in content
    assert "source_type: periodic_report_excerpt" in content
    assert "claim_status: professional_analysis" in content
    assert "claim_status: fact_candidate" not in content


def test_periodic_report_fulltext_analysis_is_filtered_from_knowledge(tmp_path):
    item = _make_item(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content="全文实验路径预览内容。",
        url="http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300661&announcementId=1225000001",
        source_type="periodic_report_fulltext_analysis",
        source_domain="cninfo.com.cn",
        source_credit=75,
        verification_status="professional_analysis",
        knowledge_eligible=False,
        report_eligible=False,
    )
    plan = write_evidence_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        items=[item],
        base_dir=tmp_path,
        dry_run=False,
    )

    assert len(plan.filtered) == 1
    assert "knowledge_eligible=False" in plan.filtered[0]["reason"]
    assert len(plan.written) == 0
    assert not (tmp_path / "10-Stocks" / "圣邦股份" / "evidence").exists()


def test_periodic_report_fulltext_analysis_never_becomes_fact_candidate_even_if_credit_rises(tmp_path):
    """Guard against future threshold changes: credit>=80 must not promote fulltext analysis to fact_candidate."""
    item = _make_item(
        title="2025年年度报告 | 定期报告全文摘要（实验路径）",
        content="全文实验路径预览内容。",
        url="http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300661&announcementId=1225000001",
        source_type="periodic_report_fulltext_analysis",
        source_domain="cninfo.com.cn",
        source_credit=85,
        verification_status="professional_analysis",
        knowledge_eligible=True,
        report_eligible=False,
    )
    plan = write_evidence_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        items=[item],
        base_dir=tmp_path,
        dry_run=False,
    )

    assert len(plan.written) == 1
    path = Path(plan.written[0]["planned_path"])
    content = path.read_text(encoding="utf-8")
    assert "source_type: periodic_report_fulltext_analysis" in content
    assert "claim_status: professional_analysis" in content
    assert "claim_status: fact_candidate" not in content


# ---------------------------------------------------------------------------
# Cross-stock isolation
# ---------------------------------------------------------------------------


def test_cross_stock_isolation(tmp_path):
    item_a = _make_item(
        title="A 新闻",
        url="https://example.com/a",
        source_credit=85,
        source_type="company_official",
        source_domain="example.com",
    )
    item_b = _make_item(
        title="B 新闻",
        url="https://example.com/b",
        source_credit=85,
        source_type="company_official",
        source_domain="example.com",
    )
    plan_a = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item_a],
        base_dir=tmp_path,
        dry_run=False,
    )
    plan_b = write_evidence_notes(
        stock_name="圣邦股份",
        stock_code="300661",
        items=[item_b],
        base_dir=tmp_path,
        dry_run=False,
    )
    assert len(plan_a.written) == 1
    assert len(plan_b.written) == 1
    assert (tmp_path / "10-Stocks" / "黑芝麻智能" / "evidence").exists()
    assert (tmp_path / "10-Stocks" / "圣邦股份" / "evidence").exists()


# ---------------------------------------------------------------------------
# Plan structure
# ---------------------------------------------------------------------------


def test_plan_return_type():
    plan = EvidenceWritePlan()
    assert plan.written == []
    assert plan.skipped_existing == []
    assert plan.filtered == []


def test_written_meta_contains_required_fields(tmp_path):
    item = _make_item(
        title="t",
        url="https://example.com/article",
        source_credit=85,
        source_type="company_official",
        source_domain="example.com",
    )
    plan = write_evidence_notes(
        stock_name="黑芝麻智能",
        stock_code="02533",
        items=[item],
        base_dir=tmp_path,
        dry_run=True,
    )
    meta = plan.written[0]
    assert "title" in meta
    assert "url" in meta
    assert "canonical_key" in meta
    assert "planned_path" in meta
    assert "reason" in meta
