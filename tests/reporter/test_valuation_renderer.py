"""Tests for ValuationRenderer."""

import pytest
from unittest.mock import patch
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


def test_render_keeps_peer_table_but_omits_valuation_chart():
    renderer = ValuationRenderer()
    ctx = {
        "stock_name": "TestStock",
        "stock_codes": {"TestStock": "000001"},
        "quote": {
            "price": 10.0,
            "pe_ttm": -1.0,
            "pb": 2.0,
            "mcap_yi": 100.0,
            "change_pct": 1.5,
            "float_mcap_yi": 80.0,
        },
        "consensus": {},
        "chart_paths": {"valuation": "/tmp/valuation.png"},
    }

    with patch(
        "scripts.utils.reporter.data_fetcher.fetch_latest_quarterly_financials",
        return_value=None,
    ), patch(
        "scripts.utils.reporter.data_fetcher.fetch_competitor_metrics",
        return_value={"TestStock": {"forward_pe": None, "ps": 2.0, "peg": None}},
    ), patch(
        "scripts.utils.reporter.data_fetcher.competitor_metrics_table",
        return_value="### 同业估值对比\n\n| 公司 | PS |\n|---|---|\n| TestStock | 2.0 |",
    ):
        result = renderer.render(ctx)

    assert "### 同业估值对比" in result
    assert "| TestStock | 2.0 |" in result
    assert "![TestStock 估值对比]" not in result
    assert "/tmp/valuation.png" not in result
