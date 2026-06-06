"""Tests for RiskRenderer."""

import pytest
from scripts.utils.reporter.sections import RiskRenderer


def test_required_keys():
    renderer = RiskRenderer()
    assert renderer.required_keys() == ["stock_name", "all_posts"]


def test_render_missing_keys():
    renderer = RiskRenderer()
    assert renderer.render({}) == ""
    # With stock_name but no all_posts (or empty list), risk_score_section still returns output
    assert renderer.render({"stock_name": "Test", "all_posts": []}) != ""


def test_render_basic():
    renderer = RiskRenderer()
    ctx = {
        "stock_name": "黑芝麻智能",
        "all_posts": [],
    }
    result = renderer.render(ctx)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "风险提示与关注要点" in result


def test_render_unknown_stock():
    renderer = RiskRenderer()
    ctx = {
        "stock_name": "UnknownStock",
        "all_posts": [],
    }
    result = renderer.render(ctx)
    # Unknown stocks have no predefined risk text, but may still have risk_score_section output
    assert isinstance(result, str)
