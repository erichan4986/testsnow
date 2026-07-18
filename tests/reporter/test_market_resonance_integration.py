"""市场/板块共振集成测试 — 验证个股 vs 指数趋势共振链路。"""

import pytest
import numpy as np
import pandas as pd


def _make_uptrend_df(close_start=100.0, days=60, up=True):
    """生成一个简单趋势日K数据。"""
    dates = pd.date_range(end=pd.Timestamp("2026-06-08"), periods=days, freq="B")
    drift = 0.002 if up else -0.002
    closes = close_start * np.exp(np.cumsum(np.full(days, drift)))
    opens = closes * 0.998
    highs = closes * 1.01
    lows = closes * 0.99
    df = pd.DataFrame({
        "date": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.full(days, 10000),
    })
    return df


def test_analyzer_wires_market_resonance_with_index_data(monkeypatch):
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_analyzer import advanced_medium_term_resonance

    # 个股：上升趋势（价格 > MA20 > MA60）
    stock_df = _make_uptrend_df(close_start=100.0, days=120, up=True)
    # 把 MA 拉开形成多头排列
    stock_df["close"] = stock_df["close"] * 1.0

    # Mock 指数获取：市场指数也是上升趋势
    def _fake_fetch_index(symbol, days=120):
        return _make_uptrend_df(close_start=200.0, days=days, up=True)

    monkeypatch.setattr("technical_analyzer._fetch_index_kline", _fake_fetch_index)

    result = advanced_medium_term_resonance(
        df_daily=stock_df,
        quote={"code": "688008", "adjustment": "raw", "data_source": "test"},
    )
    resonance = result.get("resonance", {})
    mr = resonance.get("market_resonance")
    assert mr is not None
    assert mr.get("state") not in [None, "未知"], f"共振状态不应为未知：{mr}"
    assert "market_trend" in mr
    assert mr["market_trend"] is not None
    assert "theme_trend" in mr


def test_renderer_shows_market_resonance_with_impact_and_relative():
    from scripts.utils.reporter.sections.technical_renderer import TechnicalRenderer

    ctx = {
        "stock_name": "测试",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "close": 100,
                    "_resonance": {
                        "trend_state": {"primary_state": "上升趋势", "stage": "主升期"},
                        "trend_health": {"score": 75, "grade": "健康"},
                        "invalidation": {
                            "hard_invalid_price": 90,
                            "hard_invalid_source": "MA60",
                            "current_distance_to_invalid": "11.1%",
                            "status": "safe",
                            "message": "位于MA60上方",
                        },
                        "key_levels": {"support_zone": None, "resistance_zone": None},
                        "advisors": {
                            "macd": {"state": "多头延续", "meaning": "仅作趋势确认"},
                            "rsi": {"state": "正常", "meaning": "强趋势中不单独构成卖出信号"},
                            "bias": {"state": "正常", "meaning": "价格与均线偏离适中"},
                            "boll": {"state": "正常", "meaning": "中轨附近，波动正常"},
                        },
                        "bottom_signal": {"state": "none"},
                        "divergence_scan": None,
                        "market_resonance": {
                            "state": "顺风共振",
                            "confidence": "高",
                            "impact": "趋势信号可信度上调",
                            "relative_strength": "强于行业",
                            "evidence": ["个股趋势：主升期", "大盘趋势：主升期", "行业趋势：主升期"],
                            "missing": [],
                            "action_hint": "趋势跟随",
                        },
                    },
                },
            },
        },
        "technical_render_mode": "compact",
    }
    renderer = TechnicalRenderer()
    output = renderer.render(ctx)
    assert "顺风共振" in output, f"应显示共振状态：\n{output}"
    assert "趋势信号可信度上调" in output, f"应显示影响：\n{output}"
    assert "强于行业" in output, f"应显示相对强弱：\n{output}"
    assert "趋势跟随" in output, f"应显示提示：\n{output}"


def test_renderer_hides_unavailable_market_resonance_placeholder():
    from scripts.utils.reporter.sections.technical_renderer import TechnicalRenderer

    ctx = {
        "stock_name": "测试",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "close": 100,
                    "_resonance": {
                        "trend_state": {"primary_state": "上升趋势", "stage": "主升期"},
                        "trend_health": {"score": 75, "grade": "健康"},
                        "invalidation": {
                            "hard_invalid_price": 90,
                            "hard_invalid_source": "MA60",
                            "current_distance_to_invalid": "11.1%",
                            "status": "safe",
                            "message": "位于MA60上方",
                        },
                        "key_levels": {"support_zone": None, "resistance_zone": None},
                        "advisors": {
                            "macd": {"state": "多头延续", "meaning": "仅作趋势确认"},
                            "rsi": {"state": "正常", "meaning": "强趋势中不单独构成卖出信号"},
                            "bias": {"state": "正常", "meaning": "价格与均线偏离适中"},
                            "boll": {"state": "正常", "meaning": "中轨附近，波动正常"},
                        },
                        "bottom_signal": {"state": "none"},
                        "divergence_scan": None,
                        "market_resonance": {
                            "state": "未知",
                            "confidence": "低",
                            "impact": "暂未接入完整市场/行业数据，本次共振分析仅作占位。",
                            "relative_strength": "未知",
                            "evidence": [],
                            "missing": ["market index data missing", "sector index data missing"],
                            "action_hint": "继续观察",
                        },
                    },
                },
            },
        },
        "technical_render_mode": "compact",
    }
    renderer = TechnicalRenderer()
    output = renderer.render(ctx)
    assert "市场/板块共振" not in output, f"缺失共振数据不应占用正文：\n{output}"
    assert "占位" not in output, f"不应显示占位分析：\n{output}"
