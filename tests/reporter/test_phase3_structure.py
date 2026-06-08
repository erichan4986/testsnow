import pandas as pd
import numpy as np
from scripts.utils.reporter.technical_structure import (
    detect_trend_structure_health,
    detect_channel_or_box_structure,
)


def test_higher_lows():
    """低点逐步抬升"""
    dates = pd.date_range("2026-04-01", periods=60, freq="B")
    prices = np.ones(60) * 200
    # 构造3个低点：160, 170, 180，中间有间隔
    prices[10] = 160; prices[11] = 165; prices[12] = 170
    prices[30] = 170; prices[31] = 175; prices[32] = 180
    prices[50] = 180; prices[51] = 185; prices[52] = 190
    df = pd.DataFrame({
        "date": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices, "volume": np.ones(60) * 10000,
    })
    result = detect_trend_structure_health(df)
    assert result["state"] == "低点抬升"
    assert result["is_healthy"] is True
    assert result["last_low_relation"] == "higher"
    assert len(result["swing_lows"]) >= 2


def test_lower_lows():
    """低点逐步下移"""
    dates = pd.date_range("2026-04-01", periods=60, freq="B")
    prices = np.ones(60) * 200
    prices[10] = 190; prices[30] = 180; prices[50] = 170
    df = pd.DataFrame({
        "date": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices, "volume": np.ones(60) * 10000,
    })
    result = detect_trend_structure_health(df)
    assert result["state"] == "低点下移"
    assert result["is_healthy"] is False
    assert result["last_low_relation"] == "lower"


def test_flat_lows():
    """低点差异小于 tolerance"""
    dates = pd.date_range("2026-04-01", periods=60, freq="B")
    prices = np.ones(60) * 200
    prices[10] = 180; prices[30] = 180.5; prices[50] = 181
    df = pd.DataFrame({
        "date": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices, "volume": np.ones(60) * 10000,
    })
    result = detect_trend_structure_health(df, tolerance_pct=0.01)
    assert result["state"] == "低点走平"
    assert result["is_healthy"] is None


def test_insufficient_swings():
    """swing lows 不足 2 个"""
    dates = pd.date_range("2026-04-01", periods=10, freq="B")
    prices = np.ones(10) * 200
    df = pd.DataFrame({
        "date": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices, "volume": np.ones(10) * 10000,
    })
    result = detect_trend_structure_health(df)
    assert result["state"] == "无法判断"
    assert result["missing"] != []


def test_last_bar_not_confirmed():
    """最近一根 K 线不能作为 confirmed low"""
    dates = pd.date_range("2026-04-01", periods=60, freq="B")
    prices = np.ones(60) * 200
    prices[-1] = 150  # 最低点在最后，但无右侧确认
    df = pd.DataFrame({
        "date": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices, "volume": np.ones(60) * 10000,
    })
    result = detect_trend_structure_health(df)
    # 最后的低点不应被计入
    if result["swing_lows"]:
        last_swing_date = pd.Timestamp(result["swing_lows"][-1]["date"])
        assert last_swing_date != dates[-1]


def test_short_gap_lowers_confidence():
    """间隔 <5 日时 confidence 不得为'高'"""
    dates = pd.date_range("2026-04-01", periods=60, freq="B")
    prices = np.ones(60) * 200
    prices[10] = 160; prices[13] = 170; prices[16] = 180
    df = pd.DataFrame({
        "date": dates, "open": prices * 0.99, "high": prices * 1.01,
        "low": prices * 0.98, "close": prices, "volume": np.ones(60) * 10000,
    })
    result = detect_trend_structure_health(df, min_gap_days=3)
    assert result["state"] == "低点抬升"
    assert result["confidence"] != "高"


def test_horizontal_box():
    """水平箱体"""
    dates = pd.date_range("2026-04-01", periods=30, freq="B")
    closes = np.ones(30) * 250
    # 波动极小，保持水平
    highs = closes + 3
    lows = closes - 3
    df = pd.DataFrame({
        "date": dates,
        "open": closes - 1,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.ones(30) * 10000,
    })
    result = detect_channel_or_box_structure(df, lookback=30)
    assert result["state"] == "水平箱体"
    assert result["position"] in ["中部", "接近上轨", "接近下轨"]


def test_ascending_channel():
    """上升通道：高低点均抬升"""
    dates = pd.date_range("2026-04-01", periods=40, freq="B")
    base = np.linspace(200, 250, 40)
    wave = np.sin(np.arange(40) / 2.0) * 6
    closes = base + wave
    highs = closes + 5
    lows = closes - 5
    df = pd.DataFrame({
        "date": dates,
        "open": closes - 1,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.ones(40) * 10000,
    })
    result = detect_channel_or_box_structure(df, lookback=30)
    assert result["state"] == "上升通道"


def test_breakout_above():
    """向上突破"""
    dates = pd.date_range("2026-04-01", periods=30, freq="B")
    closes = np.ones(30) * 250
    highs = np.ones(30) * 252
    lows = np.ones(30) * 248
    # 后3日明显突破上轨
    closes[-3:] = 265
    highs[-3:] = 267
    lows[-3:] = 263
    df = pd.DataFrame({
        "date": dates,
        "open": closes - 1,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.ones(30) * 10000,
    })
    result = detect_channel_or_box_structure(df, lookback=30, confirm_days=2)
    assert result["breakout_status"] in ["向上突破待确认", "向上突破确认"]
