import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd

from technical_analyzer import compute_trend_health, compute_invalidation


def _volume_df(*, latest_close=101.0, latest_volume=150.0, baseline=None):
    baseline = baseline or [100.0] * 20
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=21, freq="B"),
        "open": [100.0] * 21,
        "high": [102.0] * 21,
        "low": [98.0] * 21,
        "close": [100.0] * 20 + [latest_close],
        "volume": baseline + [latest_volume],
    })


def _trend_health(df, price_vs_ma20, *, volume_reliable=True):
    return compute_trend_health(
        weekly_trend="震荡",
        daily_structure={
            "ma20_direction": "走平",
            "ma60_direction": "走平",
            "price_vs_ma20": price_vs_ma20,
            "price_vs_ma60": "站上",
        },
        indicators={"rsi_14": 50, "boll_state": "正常"},
        df_daily=df,
        volume_reliable=volume_reliable,
    )["components"]["volume_confirmation"]


def test_trend_health_clamped():
    result = compute_trend_health(
        weekly_trend="单边上涨",
        daily_structure={"ma20_direction": "向上", "price_vs_ma20": "站上"},
        indicators={"rsi_14": 50, "boll_state": "正常"},
    )
    assert 0 <= result["score"] <= 100
    assert result["grade"] in ["趋势强健", "健康", "转弱观察", "破坏风险高", "趋势失效"]
    assert "components" in result
    assert "penalties" in result


def test_invalidation_basic():
    result = compute_invalidation(
        close=100.0, ma20=95.0, ma60=90.0,
        support_zone={"zone_low": 85.0},
    )
    assert "soft_warning" in result
    assert "hard_invalid" in result
    assert "hard_invalid_price" in result
    assert result["hard_invalid_price"] == 90.0
    assert result["current_distance_to_invalid"] is not None


def test_same_volume_ratio_scores_bullish_and_bearish_context_differently():
    bullish = _trend_health(_volume_df(latest_close=101.0), "站上")
    bearish = _trend_health(_volume_df(latest_close=99.0), "跌破")

    assert bullish["score"] == 9
    assert "放量上涨确认" in bullish["evidence"]
    assert bearish["score"] == 1
    assert "放量下跌确认" in bearish["evidence"]


def test_mixed_volume_context_is_neutral():
    component = _trend_health(_volume_df(latest_close=101.0), "跌破")

    assert component["score"] == 5
    assert "方向混合" in component["evidence"]


def test_volume_baseline_excludes_current_bar():
    component = _trend_health(
        _volume_df(latest_close=101.0, latest_volume=120.0),
        "站上",
    )

    assert component["score"] == 7
    assert "1.2" in component["evidence"]


def test_short_or_unreliable_volume_history_is_neutral():
    short = _volume_df().tail(10)

    assert _trend_health(short, "站上")["score"] == 5
    unreliable = _trend_health(_volume_df(), "站上", volume_reliable=False)
    assert unreliable["score"] == 5
    assert unreliable["status"] == "unreliable"


def test_monotonic_five_day_volume_does_not_change_matrix_score():
    flat = _trend_health(
        _volume_df(latest_close=101.0, latest_volume=120.0),
        "站上",
    )
    monotonic = _trend_health(
        _volume_df(
            latest_close=101.0,
            latest_volume=120.0,
            baseline=[90.5 + i for i in range(20)],
        ),
        "站上",
    )

    assert flat["score"] == monotonic["score"] == 7


def test_explicit_volume_context_preserves_direction_aware_score_matrix():
    context = {
        "status": "ready",
        "ratio": 1.5,
        "price_change": -1.0,
        "context": "bearish",
    }

    result = compute_trend_health(
        weekly_trend="震荡",
        daily_structure={
            "ma20_direction": "走平",
            "ma60_direction": "走平",
            "price_vs_ma20": "跌破",
            "price_vs_ma60": "站上",
        },
        indicators={"rsi_14": 50, "boll_state": "正常"},
        volume_context=context,
    )

    component = result["components"]["volume_confirmation"]
    assert component["score"] == 1
    assert "放量下跌确认" in component["evidence"]
