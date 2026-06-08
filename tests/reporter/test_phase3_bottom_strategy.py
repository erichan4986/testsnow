import pandas as pd
import numpy as np
from scripts.utils.reporter.technical_structure import evaluate_bottoming_region


def _make_bottoming_daily_df():
    """确定性底部日线数据：前40日大振幅，后40日小振幅收敛。"""
    dates = pd.date_range("2026-01-01", periods=80, freq="B")
    prices = np.zeros(80)
    prices[:40] = 200 + np.sin(np.arange(40)) * 25
    prices[40:] = 200 + np.sin(np.arange(40)) * 3
    return pd.DataFrame({
        "date": dates,
        "open": prices - 1,
        "high": prices + 2,
        "low": prices - 2,
        "close": prices,
        "volume": np.ones(80) * 10000,
    })


def _make_bottoming_weekly_df():
    """确定性底部周线数据。"""
    dates = pd.date_range("2025-01-03", periods=70, freq="W-FRI")
    prices = np.ones(70) * 200
    return pd.DataFrame({
        "date": dates,
        "open": prices - 1,
        "high": prices + 2,
        "low": prices - 2,
        "close": prices,
        "volume": np.ones(70) * 10000,
    })


def _make_structure_health():
    return {
        "state": "低点走平",
        "swing_lows": [
            {"date": "2026-05-15", "price": 190.0},
            {"date": "2026-06-01", "price": 191.0},
        ],
        "last_low_relation": "flat",
        "evidence": ["低点未继续下移"],
        "missing": [],
    }


def test_bottom_watch():
    """满足3条条件 → bottom_watch"""
    df_d = _make_bottoming_daily_df()
    df_w = _make_bottoming_weekly_df()
    # close < ma5 使条件5不满足；不传入 bias_5 使条件3不计分
    indicators = {"ma_5": 198, "ma_10": 199, "close": 195}
    trend_state = {"stage": "盘整期", "primary_state": "震荡趋势"}
    structure_health = _make_structure_health()
    weekly_background = {"trend": "震荡"}
    result = evaluate_bottoming_region(
        df_d, df_w, indicators, trend_state,
        structure_health=structure_health,
        weekly_background=weekly_background,
    )
    assert result["state"] == "bottom_watch"
    assert result["confidence"] == "低"


def test_bottom_candidate():
    """满足4条且周线非单边下跌 → bottom_candidate"""
    df_d = _make_bottoming_daily_df()
    df_w = _make_bottoming_weekly_df()
    indicators = {"bias_5": -2.0, "ma_5": 198, "ma_10": 199, "close": 200, "volume": 15000}
    trend_state = {"stage": "盘整期", "primary_state": "震荡趋势"}
    structure_health = _make_structure_health()
    weekly_background = {"trend": "震荡"}
    result = evaluate_bottoming_region(
        df_d, df_w, indicators, trend_state,
        structure_health=structure_health,
        weekly_background=weekly_background,
    )
    assert result["state"] == "bottom_candidate"
    assert result["confidence"] == "中"


def test_no_bottom_in_downtrend():
    """周线单边下跌时不得升级"""
    df_d = _make_bottoming_daily_df()
    df_w = _make_bottoming_weekly_df()
    indicators = {"bias_5": -2.0, "ma_5": 198, "ma_10": 199, "close": 200, "volume": 15000}
    trend_state = {"stage": "破坏期", "primary_state": "下降趋势"}
    structure_health = _make_structure_health()
    weekly_background = {"trend": "单边下跌"}
    result = evaluate_bottoming_region(
        df_d, df_w, indicators, trend_state,
        structure_health=structure_health,
        weekly_background=weekly_background,
    )
    # 即使满足4条，周线单边下跌也不得 bottom_candidate
    assert result["state"] != "bottom_candidate"


def test_swing_lows_missing():
    """structure_health 缺失时 swing_low 条件计入 missing"""
    df_d = _make_bottoming_daily_df()
    df_w = _make_bottoming_weekly_df()
    indicators = {"bias_5": -2.0, "ma_5": 198, "ma_10": 199, "close": 200}
    trend_state = {"stage": "盘整期", "primary_state": "震荡趋势"}
    result = evaluate_bottoming_region(
        df_d, df_w, indicators, trend_state,
        structure_health=None,
        weekly_background={"trend": "震荡"},
    )
    assert any(
        "swing" in str(m).lower() or "low" in str(m).lower()
        for m in result.get("missing", [])
    )


from scripts.utils.reporter.technical_strategy import evaluate_dart_strategy


def test_dart_strategy_active():
    """满足条件触发"""
    bottom = {"state": "bottom_candidate"}
    trend = {"stage": "盘整期", "primary_state": "震荡趋势"}
    indicators = {"close": 200, "ma_5": 198}
    inv = {"hard_invalid_price": 180}
    result = evaluate_dart_strategy(bottom, trend, indicators, inv)
    assert result is not None
    assert result["state"] == "active"
    for step in result["steps"]:
        assert "买入" not in step["action"]
        assert "建仓" not in step["action"]
        assert "加仓" not in step["action"]
        assert "满仓" not in step["action"]


def test_dart_strategy_no_buy_words():
    """不得出现买入/建仓/加仓/满仓"""
    bottom = {"state": "bottom_candidate"}
    trend = {"stage": "盘整期", "primary_state": "震荡趋势"}
    indicators = {"close": 200, "ma_5": 198}
    inv = {"hard_invalid_price": 180}
    result = evaluate_dart_strategy(bottom, trend, indicators, inv)
    text = str(result)
    assert "买入" not in text
    assert "建仓" not in text
    assert "加仓" not in text
    assert "满仓" not in text


def test_dart_strategy_not_triggered_below_ma5():
    """价格低于MA5不触发"""
    bottom = {"state": "bottom_candidate"}
    trend = {"stage": "盘整期", "primary_state": "震荡趋势"}
    indicators = {"close": 195, "ma_5": 198}
    inv = {"hard_invalid_price": 180}
    result = evaluate_dart_strategy(bottom, trend, indicators, inv)
    assert result is None


def test_dart_strategy_not_triggered_in_downtrend():
    """周线破坏期不触发"""
    bottom = {"state": "bottom_candidate"}
    trend = {"stage": "破坏期", "primary_state": "下降趋势"}
    indicators = {"close": 200, "ma_5": 198}
    inv = {"hard_invalid_price": 180}
    result = evaluate_dart_strategy(bottom, trend, indicators, inv)
    assert result is None
