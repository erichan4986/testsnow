import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd

from technical_state_machine import (
    classify_trend_state, apply_previous_state,
    compute_trend_health, compute_invalidation,
    evaluate_bias_extreme,
    detect_false_rebound, detect_false_breakout,
)


def test_classify_trend_state_basic():
    result = classify_trend_state(
        weekly_trend="单边上涨",
        daily_structure={"price_vs_ma20": "站上", "price_vs_ma60": "站上", "ma20_direction": "向上", "ma60_direction": "向上"},
        indicators={"close": 105, "ma_20": 100, "ma_60": 95, "boll_state": "正常", "rsi_14": 50},
        divergence=None,
    )
    assert "stage" in result
    assert result["stage"] in ["破坏期", "转弱期", "高位钝化期", "加速期", "主升期", "启动期", "盘整期"]


def test_apply_previous_state():
    ts = {"stage": "主升期"}
    apply_previous_state(ts, {"trend_state": {"stage": "启动期"}})
    assert ts["state_changed"] is True
    assert ts["previous_state"] == "启动期"


def test_compute_trend_health_basic():
    result = compute_trend_health(
        weekly_trend="单边上涨",
        daily_structure={"ma20_direction": "向上", "ma60_direction": "向上", "price_vs_ma20": "站上", "structure_type": "上升通道"},
        indicators={"boll_state": "开口", "rsi_14": 60, "bias_5": 2},
    )
    assert "score" in result
    assert 0 <= result["score"] <= 100
    assert "grade" in result


def test_compute_invalidation_basic():
    result = compute_invalidation(close=100, ma20=95, ma60=90, support_zone=None)
    assert "soft_warning" in result
    assert "hard_invalid" in result


def test_old_import_path_still_works():
    """technical_analyzer re-exports classify_trend_state etc."""
    from technical_analyzer import classify_trend_state, compute_trend_health, compute_invalidation
    assert callable(classify_trend_state)
    assert callable(compute_trend_health)
    assert callable(compute_invalidation)


def test_evaluate_bias_extreme_high():
    result = evaluate_bias_extreme(
        bias_5=5.5, bias_5_extreme_high=True, bias_5_extreme_low=False,
        bias_10=4.2, bias_10_extreme_high=False, bias_10_extreme_low=False,
    )
    assert result is not None
    assert result["direction"] == "high"
    assert "超买" in result["warning"]


def test_evaluate_bias_extreme_low():
    result = evaluate_bias_extreme(
        bias_5=-5.5, bias_5_extreme_high=False, bias_5_extreme_low=True,
        bias_10=-4.2, bias_10_extreme_high=False, bias_10_extreme_low=False,
    )
    assert result is not None
    assert result["direction"] == "low"
    assert "超卖" in result["warning"]


def test_evaluate_bias_extreme_none():
    result = evaluate_bias_extreme(
        bias_5=1.0, bias_5_extreme_high=False, bias_5_extreme_low=False,
    )
    assert result is None


def test_evaluate_bias_extreme_both_prefers_high():
    # Defensive: both flags set — prefer high for safety
    result = evaluate_bias_extreme(
        bias_5=5.5, bias_5_extreme_high=True, bias_5_extreme_low=True,
    )
    assert result is not None
    assert result["direction"] == "high"


def test_detect_false_rebound_insufficient_data():
    df = pd.DataFrame({
        "open": [100, 101, 102],
        "close": [101, 102, 103],
        "volume": [1000, 1000, 1000],
    })
    result = detect_false_rebound(df, "正常", 1000)
    assert result is None


def test_detect_false_rebound_detected():
    # Single positive day after negative, BOLL not open, volume below avg
    df = pd.DataFrame({
        "open":  [100, 100, 100, 100, 100, 99],
        "close": [99,  99,  99,  99,  99,  102],  # last day positive
        "volume": [1000, 1000, 1000, 1000, 1000, 1000],
    })
    result = detect_false_rebound(df, "正常", 1500)
    assert result is not None
    assert result["type"] == "假反弹预警"


def test_detect_false_rebound_boll_open_excluded():
    df = pd.DataFrame({
        "open":  [100, 100, 100, 100, 100, 99],
        "close": [99,  99,  99,  99,  99,  102],
        "volume": [1000, 1000, 1000, 1000, 1000, 1000],
    })
    result = detect_false_rebound(df, "开口", 1500)
    assert result is None


def test_detect_false_breakout_detected():
    result = detect_false_breakout(
        close=98, ma5=100,
        prev_close=102, prev_ma5=100,
    )
    assert result is not None
    assert result["type"] == "假突破预警"
    assert "停止加仓" in result["signal"]


def test_detect_false_breakout_no_break():
    result = detect_false_breakout(
        close=102, ma5=100,
        prev_close=98, prev_ma5=100,
    )
    assert result is None
