import json
import pandas as pd
import numpy as np
from scripts.utils.reporter.technical_resonance import (
    evaluate_market_resonance,
    load_market_index_map,
    _prefix_fallback,
    analyze_index_trend,
)


def test_prefix_fallback_shanghai():
    """600/601 前缀 fallback 到上证综指"""
    result = _prefix_fallback("600519")
    assert result["market"]["code"] == "000001"


def test_prefix_fallback_star():
    """688 前缀 fallback 到科创50"""
    result = _prefix_fallback("688008")
    assert result["market"]["code"] == "000001"
    assert result["thematic"]["code"] == "000688"


def test_load_map_missing_stock():
    """不在 map 中的股票走 prefix fallback"""
    result = load_market_index_map("999999", map_path=None)
    assert result["market"] is not None


def test_market_resonance_all_strong():
    """个股+行业+大盘均强 → 顺风共振"""
    stock = {"stage": "主升期", "primary_state": "上升趋势"}
    market = {"stage": "主升期", "primary_state": "上升趋势"}
    sector = {"stage": "主升期", "primary_state": "上升趋势"}
    result = evaluate_market_resonance(stock, market, sector)
    assert result["state"] == "顺风共振"
    assert result["confidence"] == "高"


def test_market_resonance_independent():
    """个股强，行业大盘弱 → 逆风独立"""
    stock = {"stage": "主升期", "primary_state": "上升趋势"}
    market = {"stage": "破坏期", "primary_state": "下降趋势"}
    sector = {"stage": "破坏期", "primary_state": "下降趋势"}
    result = evaluate_market_resonance(stock, market, sector)
    assert result["state"] == "逆风独立"


def test_market_resonance_missing_data():
    """数据缺失时降级"""
    stock = {"stage": "主升期", "primary_state": "上升趋势"}
    result = evaluate_market_resonance(stock, None, None)
    assert result["state"] == "未知"
    assert result["confidence"] == "低"


def test_market_resonance_theme_missing_still_works():
    """theme 缺失但 market/sector 存在时仍应输出有效共振状态"""
    stock = {"stage": "主升期", "primary_state": "上升趋势"}
    market = {"stage": "主升期", "primary_state": "上升趋势"}
    sector = {"stage": "主升期", "primary_state": "上升趋势"}
    result = evaluate_market_resonance(stock, market, sector, theme_trend_state=None)
    assert result["state"] != "未知"
    assert "theme index data missing" in result["missing"]


def test_analyze_index_trend_returns_trend_state():
    """指数趋势分析返回标准结构"""
    dates = pd.date_range("2026-01-01", periods=120, freq="B")
    prices = np.linspace(100, 130, 120)
    df = pd.DataFrame({
        "date": dates,
        "open": prices - 1,
        "high": prices + 1,
        "low": prices - 1,
        "close": prices,
        "volume": np.ones(120) * 10000,
    })
    result = analyze_index_trend(df)
    assert "trend_state" in result
    assert "weekly_background" in result
    assert "daily_structure" in result
    assert "trend_health" in result
