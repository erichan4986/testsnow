"""Tests for CompositeScoreRenderer."""

import pytest
from scripts.utils.reporter.sections import CompositeScoreRenderer


def test_required_keys():
    renderer = CompositeScoreRenderer()
    assert renderer.required_keys() == ["stock_name"]


def test_render_missing_stock_name():
    renderer = CompositeScoreRenderer()
    assert renderer.render({}) == ""


def test_render_basic():
    renderer = CompositeScoreRenderer()
    ctx = {
        "stock_name": "TestStock",
        "posts": [],
        "stock_raw": {},
    }
    result = renderer.render(ctx)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "## 一、综合评分与推荐" in result


def test_render_with_pillar():
    renderer = CompositeScoreRenderer()
    ctx = {
        "stock_name": "TestStock",
        "posts": [],
        "stock_raw": {},
        "pillar": {
            "valuation": 7.0,
            "technical": 6.5,
            "sentiment": 5.0,
            "fundamental": 8.0,
            "fundflow": 4.0,
            "price": 100.0,
            "bullish_pct": 55.0,
            "bearish_pct": 20.0,
            "has_fund": True,
            "indicators": {"rsi_14": 55.0, "macd": 0.5},
        },
    }
    result = renderer.render(ctx)
    assert "综合评分" in result
    assert "估值健康度" in result
