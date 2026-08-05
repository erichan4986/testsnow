import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from unittest.mock import patch

from skill_pipeline import SkillContext
from report_skills.data_skills import (
    competitor_fetching_skill,
    data_loading_skill,
    quality_gate_skill,
    quote_fetching_skill,
)


def test_data_loading_skill():
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stocks_data": {"测试股": [{"title": "t1"}, {"title": "t2"}]},
        "raw_data": {"测试股": {"technical": {"days": 10}}},
    })
    result = data_loading_skill(ctx)
    assert result.get("all_posts") == [{"title": "t1"}, {"title": "t2"}]
    assert result.get("stock_raw") == {"technical": {"days": 10}}


def test_data_loading_skill_missing_stock():
    ctx = SkillContext(input={
        "stock_name": "不存在",
        "stocks_data": {},
        "raw_data": {},
    })
    result = data_loading_skill(ctx)
    assert result.get("all_posts") == []
    assert result.get("stock_raw") == {}


def test_quality_gate_skill_filters_posts():
    posts = [
        {"title": "好", "content": "优质内容" * 50, "like": 100, "comment": 50},
        {"title": "差", "content": "短", "like": 1, "comment": 0},
    ]
    ctx = SkillContext(input={"all_posts": posts})
    result = quality_gate_skill(ctx)
    assert "keep_posts" in result.output
    assert "demote_posts" in result.output
    assert "discard_posts" in result.output


def test_quality_gate_skill_forwards_no_llm_policy(monkeypatch):
    calls = {}

    class _Gate:
        def process_xueqiu_posts(self, posts, use_llm=True):
            calls["use_llm"] = use_llm
            return []

    monkeypatch.setattr("report_skills.data_skills.ContentQualityGate", _Gate)
    quality_gate_skill(SkillContext(input={"all_posts": [], "report_llm_enabled": False}))

    assert calls["use_llm"] is False


def test_quote_fetching_skill_with_code():
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_codes": {"测试股": "000001"},
    })
    result = quote_fetching_skill(ctx)
    # quote may be None in test env, but key should exist
    assert "quote" in result.output
    assert "consensus" in result.output
    assert "ind_fwd_pe" in result.output
    assert "ps" in result.output


def test_competitor_fetching_failure_does_not_abort_pipeline():
    ctx = SkillContext(input={
        "stock_name": "测试股",
        "stock_codes": {"测试股": "000001"},
    })

    with patch(
        "report_skills.data_skills.fetch_competitor_metrics",
        side_effect=RuntimeError("network unavailable"),
    ):
        result = competitor_fetching_skill(ctx)

    assert result.get("competitor_metrics") is None
    assert result.get("competitor_metrics_error") == "network unavailable"


def test_competitor_fetching_passes_stock_config_to_fetcher():
    ctx = SkillContext(input={
        "stock_name": "复旦微电",
        "stock_codes": {"复旦微电": "688385"},
        "stock_config": {
            "competitors": ["紫光国微"],
            "peer_codes": {"紫光国微": "002049"},
        },
    })

    with patch("report_skills.data_skills.fetch_competitor_metrics", return_value={"复旦微电": {}}) as mock_fetch:
        competitor_fetching_skill(ctx)

    mock_fetch.assert_called_once_with(
        "复旦微电",
        {"复旦微电": "688385"},
        stock_config=ctx.get("stock_config"),
    )
