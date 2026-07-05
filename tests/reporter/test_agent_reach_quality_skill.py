import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from report_skills.agent_reach_quality_skill import (
    score_agent_reach_item,
    agent_reach_quality_skill,
)
from source_adapter import SynthesisItem
from skill_pipeline import SkillContext


def _make_item(**kwargs) -> SynthesisItem:
    defaults = {
        "title": "",
        "content": "",
        "author": "",
        "source_platform": "AgentReach(twitter)",
        "url": "",
        "publish_time": "",
        "interaction_score": 0,
        "extra": {},
    }
    defaults.update(kwargs)
    return SynthesisItem(**defaults)


def test_official_relevant_evidence_rich_item_scores_keep():
    item = _make_item(
        title="黑芝麻智能2026年Q1财报分析：营收同比增长35%",
        content="因为自动驾驶芯片行业景气度回升，所以黑芝麻智能Q1营收达到12.5亿元，同比增长35%。根据公司公告，ADAS芯片出货量达到120万颗。客户包括比亚迪、理想等头部车企。",
        author="@industry_analyst",
        url="https://twitter.com/test",
        interaction_score=150,
        extra={"raw": {"verified": True}},
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    assert result["action"] == "keep"
    assert result["score"] >= 60
    assert any("股票名称" in r for r in result["reasons"])


def test_short_somewhat_relevant_item_scores_demote():
    item = _make_item(
        title="黑芝麻智能 新闻动态更新",
        content="今天看到黑芝麻智能的最新消息，感觉还不错，股价也有所波动，市场关注度在提升，投资者情绪比较积极，值得关注。",
        interaction_score=25,
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    assert result["action"] == "demote"
    assert 35 <= result["score"] < 60


def test_off_topic_spam_item_scores_discard():
    item = _make_item(
        title="冲啊！必涨！",
        content="绝对涨停！铁定翻倍！赶紧买！点击链接领取优惠！",
        interaction_score=1,
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    assert result["action"] == "discard"
    assert result["score"] < 35
    assert any("炒作信号" in r for r in result["reasons"])


def test_scorer_uses_query_terms():
    item = _make_item(
        title="黑芝麻智能 量产进展",
        content="黑芝麻智能的芯片已经量产，良率达到95%。",
        interaction_score=30,
    )
    queries = [
        {"query": "黑芝麻智能 量产", "target_platforms": ["twitter"], "rationale": "test"},
    ]
    result = score_agent_reach_item(item, stock_name="黑芝麻智能", search_queries=queries)
    assert result["score"] >= 35
    assert any("匹配" in r for r in result["reasons"])


def test_scorer_matches_split_query_terms():
    item = _make_item(
        title="黑芝麻智能发布芯片进展",
        content="公司自动驾驶芯片已经进入量产阶段，良率达到95%。",
        interaction_score=30,
    )
    queries = [
        {"query": "黑芝麻智能 量产", "target_platforms": ["twitter"], "rationale": "test"},
    ]
    result = score_agent_reach_item(item, stock_name="黑芝麻智能", search_queries=queries)
    assert any("查询词" in r for r in result["reasons"])


def test_scorer_tolerates_missing_raw_metadata():
    item = _make_item(
        title="test",
        content="some content",
        extra={},
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    assert "score" in result
    assert "action" in result
    assert "reasons" in result


def test_scorer_tolerates_raw_metadata_none():
    item = _make_item(
        title="黑芝麻智能量产更新",
        content="公司自动驾驶芯片量产进展。",
        extra={"raw": None},
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    assert "score" in result


def test_quality_skill_disabled_writes_empty():
    ctx = SkillContext(input={"stock_name": "黑芝麻智能", "agent_reach_enabled": False})
    agent_reach_quality_skill(ctx)
    assert ctx.get("agent_reach_quality_status") == "disabled"
    assert ctx.get("agent_reach_keep_items") == []
    assert ctx.get("agent_reach_demote_items") == []
    assert ctx.get("agent_reach_discard_items") == []


def test_quality_skill_missing_binary_skips():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "agent_reach_status": "missing_binary",
        "agent_reach_items": [],
    })
    agent_reach_quality_skill(ctx)
    assert ctx.get("agent_reach_quality_status") == "skipped"
    assert ctx.get("agent_reach_quality_summary")["fetch_status"] == "missing_binary"


def test_quality_skill_timeout_no_items_skips():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "agent_reach_status": "timeout",
        "agent_reach_items": [],
    })
    agent_reach_quality_skill(ctx)
    assert ctx.get("agent_reach_quality_status") == "skipped"


def test_quality_skill_timeout_with_partial_items_scores_ok():
    item = _make_item(
        title="黑芝麻智能 量产",
        content="芯片量产良率95%",
        interaction_score=50,
    )
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "agent_reach_status": "timeout",
        "agent_reach_items": [item],
        "search_queries": [],
    })
    agent_reach_quality_skill(ctx)
    assert ctx.get("agent_reach_quality_status") == "ok"
    summary = ctx.get("agent_reach_quality_summary")
    assert summary["fetch_status"] == "timeout"
    assert summary["total"] == 1


def test_quality_skill_empty_items_empty_status():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "agent_reach_status": "ok",
        "agent_reach_items": [],
    })
    agent_reach_quality_skill(ctx)
    assert ctx.get("agent_reach_quality_status") == "empty"


def test_quality_results_do_not_include_full_content():
    item = _make_item(
        title="黑芝麻智能财报",
        content="营收增长35%，净利润翻倍",
        interaction_score=100,
    )
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "agent_reach_status": "ok",
        "agent_reach_items": [item],
        "search_queries": [],
    })
    agent_reach_quality_skill(ctx)
    results = ctx.get("agent_reach_quality_results")
    assert len(results) == 1
    assert "content" not in results[0]
    assert "title" in results[0]
    assert "score" in results[0]
    assert "reasons" in results[0]


def test_quality_skill_annotates_items_for_evidence_notes():
    item = _make_item(
        title="黑芝麻智能财报",
        content="黑芝麻智能自动驾驶芯片量产，营收增长35%。",
        source_platform="AgentReach(web)",
        url="https://www.blacksesame.com/zh/list_10/972.html",
        extra={"raw": {"user_provided_url": True, "official_seed_url": True, "source_type": "official"}},
    )
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "agent_reach_status": "ok",
        "agent_reach_items": [item],
        "search_queries": [],
    })
    agent_reach_quality_skill(ctx)
    keep_items = ctx.get("agent_reach_keep_items")
    demote_items = ctx.get("agent_reach_demote_items")
    scored_item = (keep_items or demote_items)[0]
    assert scored_item.extra["agent_reach_quality_score"] > 0
    assert scored_item.extra["agent_reach_quality_action"] in ("keep", "demote")
    assert scored_item.extra["agent_reach_quality_reasons"]


def test_official_seed_url_calibrated_reasons():
    """Official seed URL with navigation-heavy but article-rich content should be keep/demote and use calibrated reason."""
    lines = [
        "黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证",
        "[首页](https://www.blacksesame.com/zh)",
        "[网站地图](https://www.blacksesame.com/zh/website-map/)",
    ]
    for i in range(30):
        lines.append(f"[链接{i}](http://x{i}.com)")
    lines.append("黑芝麻智能Q1营收达到12.5亿元，同比增长35%。")
    lines.append("ADAS芯片出货量达到120万颗，2026年6月量产。")

    item = _make_item(
        title="Title: 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证-黑芝麻智能科技有限公司",
        content="\n".join(lines),
        source_platform="AgentReach(web)",
        url="https://www.blacksesame.com/zh/list_10/972.html",
        interaction_score=0,
        extra={"raw": {"user_provided_url": True, "query_type": "web_read", "official_seed_url": True, "source_type": "official"}},
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    assert result["action"] in ("keep", "demote")
    assert any("官方种子来源" in r for r in result["reasons"])
    assert not any("内容价值低" in r for r in result["reasons"])
    assert any("导航噪音" in r for r in result["reasons"])


def test_official_seed_navigation_noise_reduces_score():
    """Official seed navigation noise should be a real penalty, not a bonus."""
    clean_item = _make_item(
        title="黑芝麻智能华山A2000U获安全认证",
        content="\n".join(
            ["黑芝麻智能Q1营收达到12.5亿元，同比增长35%。ADAS芯片出货量达到120万颗，2026年6月量产。"]
            + [f"公司产品进展说明段落{i}，用于保持与导航噪音样本相近的正文长度。" for i in range(30)]
        ),
        source_platform="AgentReach(web)",
        url="https://www.blacksesame.com/zh/list_10/972.html",
        interaction_score=0,
        extra={"raw": {"user_provided_url": True, "query_type": "web_read", "official_seed_url": True, "source_type": "official"}},
    )
    noisy_lines = [
        "黑芝麻智能华山A2000U获安全认证",
        "[首页](https://www.blacksesame.com/zh)",
        "[网站地图](https://www.blacksesame.com/zh/website-map/)",
    ]
    for i in range(30):
        noisy_lines.append(f"[链接{i}](http://x{i}.com)")
    noisy_lines.append(clean_item.content)
    noisy_item = _make_item(
        title=clean_item.title,
        content="\n".join(noisy_lines),
        source_platform=clean_item.source_platform,
        url=clean_item.url,
        interaction_score=0,
        extra=clean_item.extra,
    )

    clean = score_agent_reach_item(clean_item, stock_name="黑芝麻智能")
    noisy = score_agent_reach_item(noisy_item, stock_name="黑芝麻智能")

    assert any("导航噪音" in r for r in noisy["reasons"])
    assert noisy["score"] < clean["score"]


def test_non_official_portal_still_discarded():
    """Generic non-official portal must still be discarded."""
    content = "百度一下，你就知道\n" + "\n".join([f"链接{i}: http://x{i}.com" for i in range(50)])
    item = _make_item(
        title="Title: 百度一下，你就知道",
        content=content,
        source_platform="AgentReach(web)",
        url="https://www.baidu.com",
        interaction_score=0,
        extra={},
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    assert result["action"] == "discard"


def test_low_substance_explicit_url_portal_still_discarded():
    """A low-substance explicit user-provided URL portal should still be discarded."""
    lines = [
        "首页",
        "[网站地图](https://example.com/sitemap)",
        "[更多](https://example.com/more)",
    ]
    for i in range(50):
        lines.append(f"[链接{i}](http://x{i}.com)")

    content = "\n".join(lines)
    item = _make_item(
        title="首页 - Example Portal",
        content=content,
        source_platform="AgentReach(web)",
        url="https://example.com/",
        interaction_score=0,
        extra={"raw": {"user_provided_url": True, "query_type": "web_read", "official_seed_url": True, "source_type": "official"}},
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    assert result["action"] == "discard"


def test_quality_skill_writes_run_summary_for_success():
    item = _make_item(
        title="黑芝麻智能财报",
        content="营收增长35%，净利润翻倍",
        source_platform="AgentReach(web)",
        url="https://www.blacksesame.com/a",
        interaction_score=100,
        extra={"raw": {"official_seed_url": True, "source_type": "official", "query_type": "web_read"}},
    )
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "agent_reach_status": "ok",
        "agent_reach_items": [item],
        "search_queries": [{"query": "web_read", "target_platforms": ["web"], "urls": ["https://www.blacksesame.com/a"], "official_domains": ["blacksesame.com"]}],
    })
    agent_reach_quality_skill(ctx)
    summary = ctx.output.get("agent_reach_run_summary")
    assert summary is not None
    assert summary["stock_name"] == "黑芝麻智能"
    assert summary["enabled"] is True
    assert summary["fetch_status"] == "ok"
    assert summary["quality_status"] == "ok"
    assert summary["counts"]["total"] == 1
    assert summary["queries"][0]["official_domains"] == ["blacksesame.com"]
    assert "results" in summary
    assert len(summary["results"]) == 1
    assert summary["results"][0]["official_seed_url"] is True
    assert summary["results"][0]["source_type"] == "official"
    assert "content" not in summary["results"][0]
    assert "content" not in str(summary)


def test_quality_skill_writes_run_summary_for_disabled():
    ctx = SkillContext(input={"stock_name": "黑芝麻智能", "agent_reach_enabled": False})
    agent_reach_quality_skill(ctx)
    summary = ctx.output.get("agent_reach_run_summary")
    assert summary is not None
    assert summary["enabled"] is False
    assert summary["counts"]["total"] == 0


def test_quality_skill_writes_run_summary_for_empty():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "agent_reach_status": "ok",
        "agent_reach_items": [],
        "search_queries": [],
    })
    agent_reach_quality_skill(ctx)
    summary = ctx.output.get("agent_reach_run_summary")
    assert summary is not None
    assert summary["enabled"] is True
    assert summary["fetch_status"] == "ok"
    assert summary["quality_status"] == "empty"
    assert summary["counts"]["total"] == 0


# --- Phase 0B quality calibration tests ---

def test_rss_data_rich_item_can_keep_with_zero_interaction():
    """A data-rich RSS item should reach keep even with interaction_score=0."""
    item = _make_item(
        title="创维独家投资数千万，这家企业将碳化硅切割损耗降至40微米内",
        content="36氪首发报道。创维独家投资数千万人民币，某半导体企业将碳化硅切割损耗降至40微米内，良率提升至95%。2026年Q1营收同比增长35%。",
        source_platform="AgentReach(rss)",
        url="https://36kr.com/p/xxx",
        interaction_score=0,
        extra={},
    )
    result = score_agent_reach_item(item, stock_name="创维")
    assert result["action"] == "keep"
    assert result["score"] >= 50


def test_web_article_can_keep_with_zero_interaction():
    """A legitimate Web article should reach keep with interaction_score=0."""
    item = _make_item(
        title="黑芝麻智能2026年Q1财报分析",
        content="黑芝麻智能Q1营收达到12.5亿元，同比增长35%。ADAS芯片出货量达到120万颗。客户包括比亚迪、理想等头部车企。公司预计全年营收增长40%。",
        source_platform="AgentReach(web)",
        url="https://example.com/article",
        interaction_score=0,
        extra={},
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    assert result["action"] == "keep"
    assert result["score"] >= 50


def test_social_item_below_threshold_stays_not_keep():
    """A social item that previously scored below 60 should not auto-become keep."""
    item = _make_item(
        title="黑芝麻智能 新闻",
        content="今天看到黑芝麻智能的最新消息，感觉还不错。",
        source_platform="AgentReach(twitter)",
        url="https://twitter.com/x",
        interaction_score=0,
        extra={},
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    # Without interaction, this should still be demote or discard, not keep
    assert result["action"] != "keep"


def test_generic_unrelated_rss_item_not_keep():
    """A generic RSS item unrelated to the stock should not reach keep."""
    item = _make_item(
        title="Mis-Teeq on reuniting, UK garage and Alesha Dixon's ad libs",
        content="The noughties girl group are back for a reunion gig to celebrate the 25th anniversary of their debut album.",
        source_platform="AgentReach(rss)",
        url="https://bbc.com/news/xxx",
        interaction_score=0,
        extra={},
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    assert result["action"] != "keep"


def test_web_portal_page_discarded():
    """A Web portal/navigation page should be discarded with a portal reason."""
    # Simulate baidu-like portal content
    content = "百度一下，你就知道\n" + "\n".join([f"链接{i}: http://x{i}.com" for i in range(50)])
    item = _make_item(
        title="Title: 百度一下，你就知道",
        content=content,
        source_platform="AgentReach(web)",
        url="https://www.baidu.com",
        interaction_score=0,
        extra={},
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    assert result["action"] == "discard"
    assert any("门户" in r or "导航" in r for r in result["reasons"])


def test_data_rich_web_portal_page_still_discarded():
    """Portal detection should override article-like scoring bonuses."""
    content = "\n".join(
        [
            f"黑芝麻智能 导航 链接{i}: http://x{i}.com 营收12.5亿元 同比35% ADAS芯片 出货50万颗 2026年06月"
            for i in range(50)
        ]
    )
    item = _make_item(
        title="Title: 黑芝麻智能 股票频道 首页",
        content=content,
        source_platform="AgentReach(web)",
        url="https://example.com/portal",
        interaction_score=0,
        extra={},
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    assert result["action"] == "discard"
    assert any("门户" in r or "导航" in r for r in result["reasons"])


def test_web_article_with_one_link_not_discarded():
    """A legitimate article containing one '链接' should not be auto-discarded."""
    item = _make_item(
        title="黑芝麻智能发布芯片进展",
        content="黑芝麻智能宣布最新芯片已量产。点击链接查看详情：http://example.com/details。公司预计Q2出货量达到50万颗。",
        source_platform="AgentReach(web)",
        url="https://example.com/article",
        interaction_score=0,
        extra={},
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    # Should not be discarded solely because of one 链接
    assert result["action"] != "discard"


def test_explicit_url_data_rich_portal_not_discarded():
    """A data-rich explicit user-provided URL with portal signals should not be capped to discard."""
    # Simulate Jina output for a corporate article page: lots of nav links,
    # portal keywords, but rich article body.
    lines = [
        "黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证",
        "[首页](https://www.blacksesame.com/zh)",
        "[公司信息](https://www.blacksesame.com/zh/company-profile/)",
        "[网站地图](https://www.blacksesame.com/zh/website-map/)",
        "[更多](https://www.blacksesame.com/zh/more/)",
    ]
    # Add enough links to trigger link-density signal
    for i in range(50):
        lines.append(f"[链接{i}](http://x{i}.com)")
    # Add data-rich article body
    lines.append("黑芝麻智能Q1营收达到12.5亿元，同比增长35%。")
    lines.append("ADAS芯片出货量达到120万颗，2026年6月量产。")
    lines.append("客户包括比亚迪、理想等头部车企。")

    content = "\n".join(lines)
    item = _make_item(
        title="Title: 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证-黑芝麻智能科技有限公司",
        content=content,
        source_platform="AgentReach(web)",
        url="https://www.blacksesame.com/zh/list_10/972.html",
        interaction_score=0,
        extra={"raw": {"user_provided_url": True, "query_type": "web_read"}},
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    # Should NOT be discarded; portal cap is relaxed for explicit URLs.
    # Raw score before penalty should be high enough to stay keep/demote after -15.
    assert result["action"] in ("keep", "demote"), f"expected keep or demote, got {result['action']} with score {result['score']}"
    assert any("门户" in r or "导航" in r for r in result["reasons"])


def test_low_substance_explicit_url_portal_still_discarded():
    """A low-substance explicit user-provided URL that is truly a portal should still be discarded."""
    lines = [
        "首页",
        "[网站地图](https://example.com/sitemap)",
        "[更多](https://example.com/more)",
    ]
    for i in range(50):
        lines.append(f"[链接{i}](http://x{i}.com)")

    content = "\n".join(lines)
    item = _make_item(
        title="首页 - Example Portal",
        content=content,
        source_platform="AgentReach(web)",
        url="https://example.com/",
        interaction_score=0,
        extra={"raw": {"user_provided_url": True, "query_type": "web_read"}},
    )
    result = score_agent_reach_item(item, stock_name="黑芝麻智能")
    # Low substance + portal penalty should still land in discard
    assert result["action"] == "discard"
