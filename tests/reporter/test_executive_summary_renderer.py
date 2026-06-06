"""Tests for ExecutiveSummaryRenderer."""

import pytest
from scripts.utils.reporter.sections import ExecutiveSummaryRenderer


def test_required_keys():
    renderer = ExecutiveSummaryRenderer()
    assert renderer.required_keys() == ["stock_name", "synthesis"]


def test_render_missing_keys_returns_empty():
    renderer = ExecutiveSummaryRenderer()
    assert renderer.render({}) == ""
    assert renderer.render({"stock_name": "Test"}) == ""


def test_render_basic():
    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "valuation_debate": "估值合理，增长空间大。",
            "fundamentals": "基本面稳健，业绩持续增长。",
        },
    }
    result = renderer.render(ctx)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "## 执行摘要" in result
    assert "核心投资论点" in result


def test_render_with_pillar():
    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "valuation_debate": "估值合理。",
            "fundamentals": "基本面稳健。",
        },
        "pillar": {
            "valuation": 7.0,
            "technical": 6.5,
            "sentiment": 5.0,
            "fundamental": 8.0,
            "fundflow": 4.0,
        },
    }
    result = renderer.render(ctx)
    assert "综合评分" in result
