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


def test_render_marks_inconsistent_float_market_cap_as_na():
    renderer = ValuationRenderer()
    ctx = {
        "stock_name": "复旦微电",
        "stock_codes": {"复旦微电": "688385"},
        "quote": {
            "price": 69.48,
            "pe_ttm": 120.0,
            "pb": 6.0,
            "mcap_yi": 374.8,
            "change_pct": 1.5,
            "float_mcap_yi": 572.3,
            "market_cap_quality": "market_cap_inconsistent",
        },
        "consensus": {},
    }

    result = renderer.render(ctx)

    assert "流通市值 572.3 亿" not in result
    assert "流通市值 N/A（口径冲突）" in result


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


def _trend_ctx():
    return {
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
        "consensus": {},
        "competitor_metrics": {"Peer": {"pe_ttm": 20.0}},
        "financial_trend_view": {
            "schema_version": "financial_trend_view.v1",
            "status": "ready",
            "display_eligible": True,
            "scoring_eligible": False,
            "stock_code": "000001",
            "years": [2023, 2024, 2025],
            "rows": [
                {"metric_key": "revenue", "label": "营业收入", "unit": "亿元",
                 "values": ["1.00", "1.20", "1.50"], "latest_growth_rate": "+25.0%"},
                {"metric_key": "net_profit", "label": "归母净利润", "unit": "亿元",
                 "values": ["0.15", "0.13", "0.10"], "latest_growth_rate": "-23.1%"},
                {"metric_key": "operating_cash_flow", "label": "经营现金流", "unit": "亿元",
                 "values": ["0.12", "0.12", "0.10"], "latest_growth_rate": "-14.5%"},
            ],
            "cash_conversion": {
                "metric_key": "operating_cash_flow_to_net_profit",
                "label": "现金转换率",
                "unit": "%",
                "values": ["80.0%", "—", "100.0%"],
                "latest_growth_rate": "—",
            },
            "summary": "营业收入连续增长，归母净利润连续下滑，经营现金流连续下滑。",
            "source_label": "东方财富结构化年度财务数据；仅用于趋势观察，不替代年报确认，不参与评分。",
        },
    }


def test_render_places_three_year_trend_after_snapshot_and_before_peers():
    renderer = ValuationRenderer()
    with patch.object(
        renderer, "_quarterly_financials_table", return_value="### 最新财务快照\n\n快照",
    ), patch(
        "scripts.utils.reporter.data_fetcher.competitor_metrics_table",
        return_value="### 同业估值对比\n\n同业",
    ):
        result = renderer.render(_trend_ctx())

    assert "### 近三年财务趋势" in result
    assert "| 营业收入（亿元） | 1.00 | 1.20 | 1.50 | +25.0% |" in result
    assert "| 现金转换率 | 80.0% | — | 100.0% | — |" in result
    assert "仅用于趋势观察，不替代年报确认，不参与评分" in result
    assert result.index("### 最新财务快照") < result.index("### 近三年财务趋势")
    assert result.index("### 近三年财务趋势") < result.index("### 同业估值对比")


def test_render_adds_optional_gross_margin_and_derivation_note():
    renderer = ValuationRenderer()
    ctx = _trend_ctx()
    ctx["financial_trend_view"]["gross_margin"] = {
        "metric_key": "gross_margin", "label": "毛利率", "unit": "%",
        "values": ["35.0%", "36.5%*", "38.1%"],
        "origins": ["direct", "derived", "direct"], "latest_change": "+1.6pct",
        "derivation_note": "* 为同源同年财务字段计算值。",
    }

    result = renderer.render(ctx)

    assert "| 毛利率 | 35.0% | 36.5%* | 38.1% | +1.6pct |" in result
    assert "* 为同源同年财务字段计算值。" in result
    assert result.index("| 现金转换率 |") < result.index("| 毛利率 |")


def test_render_ignores_invalid_optional_gross_margin_without_losing_base_table():
    renderer = ValuationRenderer()
    ctx = _trend_ctx()
    ctx["financial_trend_view"]["gross_margin"] = {"metric_key": "gross_margin", "values": ["bad"]}

    result = renderer.render(ctx)

    assert "### 近三年财务趋势" in result
    assert "| 毛利率 |" not in result

    ctx = _trend_ctx()
    ctx["financial_trend_view"]["gross_margin"] = {
        "metric_key": "gross_margin", "label": "毛利率", "unit": "%",
        "values": ["35.0%", "36.5%", "38.1%"],
        "origins": ["direct", "derived", "direct"], "latest_change": "+1.6pct",
        "derivation_note": "* 为同源同年财务字段计算值。",
    }
    assert "| 毛利率 |" not in renderer.render(ctx)


def test_render_keeps_ready_financial_trend_when_live_quote_is_unavailable():
    renderer = ValuationRenderer()
    ctx = _trend_ctx()
    ctx["quote"] = {}

    result = renderer.render(ctx)

    assert "## 二、估值与财务快照" in result
    assert "实时行情暂不可用" in result
    assert "### 近三年财务趋势" in result
    assert "### 实时估值指标" not in result


@pytest.mark.parametrize("view", [None, {}, {"schema_version": "financial_trend_view.v1", "status": "unavailable"}])
def test_render_omits_absent_or_unavailable_financial_trend_view(view):
    renderer = ValuationRenderer()
    ctx = _trend_ctx()
    ctx["financial_trend_view"] = view

    with patch.object(renderer, "_quarterly_financials_table", return_value=""):
        result = renderer.render(ctx)

    assert "### 近三年财务趋势" not in result
