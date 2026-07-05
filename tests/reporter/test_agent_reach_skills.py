import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from report_skills.agent_reach_query_skill import (
    generate_agent_reach_queries,
    agent_reach_query_skill,
)
from report_skills.agent_reach_skill import (
    agent_reach_fetch_skill,
    RSSConnector,
    WebConnector,
    _dedupe_records,
)
from skill_pipeline import SkillContext
from source_adapter import SynthesisItem


# --- Query skill tests ---

def test_query_skill_disabled_sets_status():
    ctx = SkillContext(input={"stock_name": "黑芝麻智能", "enable_agent_reach": False})
    agent_reach_query_skill(ctx)
    assert ctx.get("agent_reach_enabled") is False
    assert ctx.get("agent_reach_status") == "disabled"
    assert ctx.get("search_queries") == []


def test_query_skill_enabled_generates_rss_query():
    ctx = SkillContext(input={"stock_name": "黑芝麻智能", "stock_codes": {"黑芝麻智能": "02533"}, "enable_agent_reach": True, "agent_reach_rss_feeds": ["http://example.com/feed"]})
    agent_reach_query_skill(ctx)
    assert ctx.get("agent_reach_enabled") is True
    queries = ctx.get("search_queries")
    assert len(queries) == 1
    assert queries[0]["query"] == "rss_poll"
    assert queries[0]["target_platforms"] == ["rss"]
    assert "rss_filter_terms" in queries[0]
    assert "黑芝麻智能" in queries[0]["rss_filter_terms"]


def test_query_skill_does_not_generate_web_without_urls():
    ctx = SkillContext(input={"stock_name": "黑芝麻智能", "enable_agent_reach": True})
    agent_reach_query_skill(ctx)
    queries = ctx.get("search_queries")
    for q in queries:
        assert "web" not in q.get("target_platforms", [])


def test_query_skill_generates_web_with_agent_reach_urls():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "enable_agent_reach": True,
        "agent_reach_urls": ["http://example.com/a"],
    })
    agent_reach_query_skill(ctx)
    queries = ctx.get("search_queries")
    web_queries = [q for q in queries if "web" in q.get("target_platforms", [])]
    assert len(web_queries) == 1
    assert web_queries[0]["urls"] == ["http://example.com/a"]


def test_query_skill_generates_web_with_agent_reach_web_urls():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "enable_agent_reach": True,
        "agent_reach_web_urls": ["http://example.com/b"],
    })
    agent_reach_query_skill(ctx)
    queries = ctx.get("search_queries")
    web_queries = [q for q in queries if "web" in q.get("target_platforms", [])]
    assert len(web_queries) == 1
    assert web_queries[0]["urls"] == ["http://example.com/b"]


def test_query_skill_default_targets_only_phase0_platforms():
    ctx = SkillContext(input={"stock_name": "黑芝麻智能", "enable_agent_reach": True})
    agent_reach_query_skill(ctx)
    queries = ctx.get("search_queries")
    for q in queries:
        for platform in q.get("target_platforms", []):
            assert platform in ("rss", "web")


def test_query_skill_allows_rss_feeds_override():
    custom_feeds = ["http://custom.feed/rss"]
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "enable_agent_reach": True,
        "agent_reach_rss_feeds": custom_feeds,
    })
    agent_reach_query_skill(ctx)
    queries = ctx.get("search_queries")
    rss_query = [q for q in queries if q.get("query") == "rss_poll"][0]
    assert rss_query["rss_feeds"] == custom_feeds


def test_generate_agent_reach_queries_backward_compatible_without_ctx():
    queries = generate_agent_reach_queries("黑芝麻智能", "02533")
    assert isinstance(queries, list)
    assert not any(q["query"] == "rss_poll" for q in queries)  # default feeds are empty in Phase 0B


def test_generate_agent_reach_queries_skips_rss_without_filter_terms():
    queries = generate_agent_reach_queries("", "")
    assert queries == []


def test_generate_agent_reach_queries_allows_web_without_filter_terms():
    ctx = SkillContext(input={"agent_reach_urls": ["http://example.com/article"]})
    queries = generate_agent_reach_queries("", "", ctx=ctx)
    assert len(queries) == 1
    assert queries[0]["query"] == "web_read"
    assert queries[0]["target_platforms"] == ["web"]


def test_query_skill_passes_official_domains_to_web_query():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "enable_agent_reach": True,
        "agent_reach_urls": ["http://example.com/a"],
        "agent_reach_official_domains": ["example.com"],
    })
    agent_reach_query_skill(ctx)
    queries = ctx.get("search_queries")
    web_queries = [q for q in queries if "web" in q.get("target_platforms", [])]
    assert len(web_queries) == 1
    assert web_queries[0].get("official_domains") == ["example.com"]


def test_generate_agent_reach_queries_passes_official_domains():
    ctx = SkillContext(input={
        "agent_reach_urls": ["http://example.com/a"],
        "agent_reach_official_domains": ["example.com", "black.com"],
    })
    queries = generate_agent_reach_queries("黑芝麻智能", "02533", ctx=ctx)
    web_queries = [q for q in queries if q.get("query") == "web_read"]
    assert len(web_queries) == 1
    assert web_queries[0].get("official_domains") == ["example.com", "black.com"]


# --- Fetch skill status mapping tests ---

def test_fetch_skill_disabled_sets_empty():
    ctx = SkillContext(input={"stock_name": "黑芝麻智能", "enable_agent_reach": False})
    agent_reach_fetch_skill(ctx)
    assert ctx.get("agent_reach_status") == "disabled"
    assert ctx.get("agent_reach_items") == []
    assert ctx.get("agent_reach_warnings") == []


def test_fetch_skill_empty_no_queries():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "search_queries": [],
    })
    agent_reach_fetch_skill(ctx)
    assert ctx.get("agent_reach_status") == "empty"
    assert ctx.get("agent_reach_items") == []


def test_fetch_skill_missing_binary_all_unavailable():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "search_queries": [
            {"query": "rss_poll", "target_platforms": ["rss"], "rationale": "test"},
        ],
    })
    with patch.object(RSSConnector, "check_deps", return_value=(False, "feedparser missing")):
        agent_reach_fetch_skill(ctx)
    assert ctx.get("agent_reach_status") == "missing_binary"
    assert ctx.get("agent_reach_items") == []


def test_fetch_skill_empty_available_but_no_records():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "search_queries": [
            {"query": "rss_poll", "target_platforms": ["rss"], "rationale": "test", "rss_filter_terms": ["test"]},
        ],
    })
    with patch.object(RSSConnector, "check_deps", return_value=(True, "")), \
         patch.object(RSSConnector, "run", return_value=([], [])):
        agent_reach_fetch_skill(ctx)
    assert ctx.get("agent_reach_status") == "empty"
    assert ctx.get("agent_reach_items") == []


def test_fetch_skill_error_available_but_runtime_failure():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "search_queries": [
            {"query": "rss_poll", "target_platforms": ["rss"], "rationale": "test"},
        ],
    })
    with patch.object(RSSConnector, "check_deps", return_value=(True, "")), \
         patch.object(RSSConnector, "run", return_value=([], ["[rss] parse/runtime error for x: y"])):
        agent_reach_fetch_skill(ctx)
    assert ctx.get("agent_reach_status") == "error"
    assert ctx.get("agent_reach_items") == []


def test_fetch_skill_ok_with_records():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "search_queries": [
            {"query": "rss_poll", "target_platforms": ["rss"], "rationale": "test", "rss_filter_terms": ["黑芝麻"]},
        ],
    })
    mock_records = [
        {"_platform": "rss", "title": "t1", "content": "c1", "url": "http://a", "author": "a1"},
    ]
    with patch.object(RSSConnector, "check_deps", return_value=(True, "")), \
         patch.object(RSSConnector, "run", return_value=(mock_records, [])):
        agent_reach_fetch_skill(ctx)
    assert ctx.get("agent_reach_status") == "ok"
    items = ctx.get("agent_reach_items")
    assert len(items) == 1
    assert isinstance(items[0], SynthesisItem)
    assert items[0].title == "t1"
    assert items[0].source_platform == "AgentReach(rss)"


def test_fetch_skill_timeout_with_records_and_budget():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "search_queries": [
            {"query": "rss_poll", "target_platforms": ["rss"], "rationale": "test", "rss_filter_terms": ["黑芝麻"]},
            {"query": "rss_poll", "target_platforms": ["rss"], "rationale": "test2", "rss_filter_terms": ["黑芝麻"]},
        ],
    })
    mock_records = [
        {"_platform": "rss", "title": "t1", "content": "c1", "url": "http://a", "author": "a1"},
    ]
    with patch.object(RSSConnector, "check_deps", return_value=(True, "")), \
         patch.object(RSSConnector, "run", return_value=(mock_records, [])), \
         patch("report_skills.agent_reach_skill.time.time", side_effect=[0, 0, 0, 0, 61, 61, 61]):
        agent_reach_fetch_skill(ctx)
    assert ctx.get("agent_reach_status") == "timeout"
    assert len(ctx.get("agent_reach_items")) == 1


def test_fetch_skill_unknown_platform_warns():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "search_queries": [
            {"query": "q", "target_platforms": ["unknown_xyz"], "rationale": "test"},
        ],
    })
    agent_reach_fetch_skill(ctx)
    assert ctx.get("agent_reach_status") == "missing_binary"
    warnings = ctx.get("agent_reach_warnings")
    assert any("unknown platform" in w for w in warnings)


def test_fetch_skill_unsupported_platform_warns():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "search_queries": [
            {"query": "q", "target_platforms": ["twitter"], "rationale": "test"},
        ],
    })
    agent_reach_fetch_skill(ctx)
    warnings = ctx.get("agent_reach_warnings")
    assert any("unsupported platform" in w for w in warnings)


def test_fetch_skill_explicit_youtube_detection_only():
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "search_queries": [
            {"query": "q", "target_platforms": ["youtube"], "rationale": "test"},
        ],
    })
    agent_reach_fetch_skill(ctx)
    warnings = ctx.get("agent_reach_warnings")
    assert any("detection-only" in w or "unavailable" in w for w in warnings)
    assert ctx.get("agent_reach_items") == []


# --- Fetch skill functional tests ---

def test_fetch_skill_applies_total_cap():
    # Use multiple queries so per-query cap (10) doesn't prevent reaching total cap (100)
    search_queries = [
        {"query": f"rss_poll_{i}", "target_platforms": ["rss"], "rationale": f"test{i}", "rss_filter_terms": ["x"]}
        for i in range(12)
    ]

    call_count = [0]

    def _mock_run(q_spec):
        idx = call_count[0]
        call_count[0] += 1
        records = [
            {"_platform": "rss", "title": f"q{idx}t{i}", "content": "c", "url": f"http://q{idx}/{i}", "author": "a"}
            for i in range(12)
        ]
        return records, []

    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "search_queries": search_queries,
    })
    with patch.object(RSSConnector, "check_deps", return_value=(True, "")), \
         patch.object(RSSConnector, "run", side_effect=_mock_run):
        agent_reach_fetch_skill(ctx)
    assert ctx.get("agent_reach_status") == "ok"
    assert len(ctx.get("agent_reach_items")) == 100


def test_fetch_skill_dedupes_by_url():
    mock_records = [
        {"_platform": "rss", "title": "t1", "content": "c1", "url": "http://dup", "author": "a1"},
        {"_platform": "rss", "title": "t2", "content": "c2", "url": "http://dup", "author": "a2"},
    ]
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "search_queries": [
            {"query": "rss_poll", "target_platforms": ["rss"], "rationale": "test", "rss_filter_terms": ["x"]},
        ],
    })
    with patch.object(RSSConnector, "check_deps", return_value=(True, "")), \
         patch.object(RSSConnector, "run", return_value=(mock_records, [])):
        agent_reach_fetch_skill(ctx)
    items = ctx.get("agent_reach_items")
    assert len(items) == 1


def test_fetch_skill_per_query_cap():
    mock_records = [
        {"_platform": "rss", "title": f"t{i}", "content": "c", "url": f"http://{i}", "author": "a"}
        for i in range(15)
    ]
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "search_queries": [
            {"query": "rss_poll", "target_platforms": ["rss"], "rationale": "test", "rss_filter_terms": ["x"]},
        ],
    })
    with patch.object(RSSConnector, "check_deps", return_value=(True, "")), \
         patch.object(RSSConnector, "run", return_value=(mock_records, [])):
        agent_reach_fetch_skill(ctx)
    assert len(ctx.get("agent_reach_items")) == 10


def test_fetch_skill_output_items_are_synthesis_item():
    mock_records = [
        {"_platform": "rss", "title": "t1", "content": "c1", "url": "http://a", "author": "a1"},
    ]
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "search_queries": [
            {"query": "rss_poll", "target_platforms": ["rss"], "rationale": "test", "rss_filter_terms": ["x"]},
        ],
    })
    with patch.object(RSSConnector, "check_deps", return_value=(True, "")), \
         patch.object(RSSConnector, "run", return_value=(mock_records, [])):
        agent_reach_fetch_skill(ctx)
    items = ctx.get("agent_reach_items")
    assert all(isinstance(item, SynthesisItem) for item in items)


# --- Downstream contract tests ---

def test_quality_skill_accepts_produced_items():
    from report_skills.agent_reach_quality_skill import agent_reach_quality_skill

    item = SynthesisItem(
        title="黑芝麻智能2026年Q1财报分析：营收同比增长35%",
        content="因为自动驾驶芯片行业景气度回升，所以黑芝麻智能Q1营收达到12.5亿元，同比增长35%。根据公司公告，ADAS芯片出货量达到120万颗。客户包括比亚迪、理想等头部车企。",
        author="@industry_analyst",
        source_platform="AgentReach(rss)",
        url="http://a",
        publish_time="",
        interaction_score=150,
        extra={"raw": {"verified": True}},
    )
    ctx = SkillContext(input={
        "stock_name": "黑芝麻智能",
        "agent_reach_enabled": True,
        "agent_reach_status": "ok",
        "agent_reach_items": [item],
        "search_queries": [],
    })
    agent_reach_quality_skill(ctx)
    assert ctx.get("agent_reach_quality_status") == "ok"
    # Should be kept (score >= 60) given rich content, data metrics, stock name, verified source
    assert len(ctx.get("agent_reach_keep_items")) >= 1


def test_evidence_renderer_accepts_produced_items():
    from reporter.sections.agent_reach_evidence_renderer import AgentReachEvidenceRenderer

    item = SynthesisItem(
        title="黑芝麻智能量产",
        content="芯片量产良率95%",
        author="",
        source_platform="AgentReach(rss)",
        url="http://a",
        publish_time="2026-06-10",
        interaction_score=50,
        extra={},
    )
    quality_result = {
        "title": "黑芝麻智能量产",
        "source": "AgentReach(rss)",
        "action": "keep",
        "score": 72,
        "reasons": ["包含股票名称", "有URL"],
        "url": "http://a",
        "fetch_status": "ok",
        "quality_status": "ok",
    }
    ctx = SkillContext(input={
        "agent_reach_enabled": True,
        "agent_reach_status": "ok",
        "agent_reach_quality_status": "ok",
        "agent_reach_keep_items": [item],
        "agent_reach_demote_items": [],
        "agent_reach_discard_items": [],
        "agent_reach_quality_results": [quality_result],
        "agent_reach_warnings": [],
        "agent_reach_quality_summary": {
            "keep": 1,
            "demote": 0,
            "discard": 0,
            "total": 1,
            "fetch_status": "ok",
            "quality_status": "ok",
        },
    })
    renderer = AgentReachEvidenceRenderer()
    result = renderer.render(ctx)
    assert "本期外部证据概览" in result
    assert "高优先级证据：1 条" in result


# --- Phase 0B query calibration tests ---

def test_generate_no_rss_query_without_feeds():
    """With empty default feeds and no override, no RSS query should be generated."""
    queries = generate_agent_reach_queries("黑芝麻智能", "02533")
    assert queries == []


def test_generate_rss_query_with_feed_override():
    """Providing agent_reach_rss_feeds should generate an RSS query."""
    ctx = SkillContext(input={"agent_reach_rss_feeds": ["http://example.com/feed"]})
    queries = generate_agent_reach_queries("黑芝麻智能", "02533", ctx=ctx)
    assert len(queries) == 1
    assert queries[0]["query"] == "rss_poll"
    assert queries[0]["rss_feeds"] == ["http://example.com/feed"]
    assert "黑芝麻智能" in queries[0]["rss_filter_terms"]
    assert "02533" in queries[0]["rss_filter_terms"]


def test_filter_terms_no_industry_keywords():
    """Filter terms should not include standalone industry keywords like 科技."""
    ctx = SkillContext(input={"agent_reach_rss_feeds": ["http://example.com/feed"]})
    queries = generate_agent_reach_queries("澜起科技", "688008", ctx=ctx)
    terms = queries[0]["rss_filter_terms"]
    assert "澜起科技" in terms
    assert "688008" in terms
    # "科技" should NOT appear as a standalone term
    assert "科技" not in terms


def test_filter_terms_explicit_override():
    """agent_reach_rss_filter_terms should bypass auto-generation."""
    ctx = SkillContext(input={
        "agent_reach_rss_feeds": ["http://example.com/feed"],
        "agent_reach_rss_filter_terms": ["自定义关键词", "A股"],
    })
    queries = generate_agent_reach_queries("澜起科技", "688008", ctx=ctx)
    terms = queries[0]["rss_filter_terms"]
    assert terms == ["自定义关键词", "A股"]


def test_web_query_without_rss():
    """Web query should still be generated even when RSS is absent."""
    ctx = SkillContext(input={"agent_reach_urls": ["http://example.com/article"]})
    queries = generate_agent_reach_queries("", "", ctx=ctx)
    assert len(queries) == 1
    assert queries[0]["query"] == "web_read"


def test_empty_stock_no_feeds_no_urls_returns_empty():
    """No stock, no feeds, no URLs → no queries at all."""
    queries = generate_agent_reach_queries("", "")
    assert queries == []
