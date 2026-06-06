"""Tests for ValuationRenderer."""

import pytest
from scripts.utils.reporter.sections import ValuationRenderer


def test_required_keys():
    renderer = ValuationRenderer()
    assert renderer.required_keys() == ["stock_name"]


def test_render_missing_stock_name():
    renderer = ValuationRenderer()
    assert renderer.render({}) == ""


def test_render_missing_code():
    renderer = ValuationRenderer()
    ctx = {"stock_name": "UnknownStock", "stock_codes": {}}
    assert renderer.render(ctx) == ""


def test_render_basic():
    renderer = ValuationRenderer()
    ctx = {
        "stock_name": "TestStock",
        "stock_codes": {"TestStock": "000001"},
        "quote": {
            "price": 10.0,
            "pe_ttm": 15.0,
            "pb": 2.0,
            "mcap_yi": 100.0,
            "change_pct": 1.5,
            "float_mcap_yi": 80.0,
        },
        "consensus": {
            "eps_current": 0.5,
            "year_current": "2026",
        },
    }
    result = renderer.render(ctx)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "## 二、估值与财务快照" in result
    assert "实时估值指标" in result
