import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
import numpy as np

from technical_structure import (
    compute_bias, compute_boll_state, compute_candle_features,
    compute_ma_direction, resample_daily_to_weekly,
    compute_weekly_trend, find_support_resistance,
    evaluate_sr_transformation,
)


def test_compute_bias_basic():
    df = pd.DataFrame({
        "close": [100.0 + i for i in range(30)],
    })
    result = compute_bias(df)
    assert "bias_5" in result
    assert "bias_10" in result
    assert "bias_20" in result


def test_compute_boll_state_basic():
    df = pd.DataFrame({
        "boll_upper": [110.0] * 10,
        "boll_mid": [100.0] * 10,
        "boll_lower": [90.0] * 10,
    })
    result = compute_boll_state(df)
    assert "boll_state" in result
    assert result["boll_state"] in ["开口", "缩口", "正常", "未知"]


def test_compute_candle_features_basic():
    df = pd.DataFrame({
        "open": [100.0],
        "high": [105.0],
        "low": [98.0],
        "close": [103.0],
    })
    result = compute_candle_features(df)
    assert "body_len" in result
    assert "is_doji" in result


def test_compute_ma_direction_up():
    ma = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    assert compute_ma_direction(ma) == "向上"


def test_resample_daily_to_weekly():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "open": [100.0] * 10,
        "high": [105.0] * 10,
        "low": [95.0] * 10,
        "close": [102.0] * 10,
        "volume": [1000] * 10,
    })
    weekly = resample_daily_to_weekly(df)
    assert weekly is not None
    assert len(weekly) >= 1


def test_evaluate_sr_transformation_resistance_break():
    result = evaluate_sr_transformation(
        close=110,
        support_zone=None,
        resistance_zone={"zone_high": 105, "zone_low": 103},
        recent_closes=[106, 107, 108],
    )
    assert result is not None
    assert result["primary"]["type"] == "resistance_break"
    assert result["primary"]["new_support"] == 105


def test_evaluate_sr_transformation_support_break():
    result = evaluate_sr_transformation(
        close=90,
        support_zone={"zone_high": 97, "zone_low": 95},
        resistance_zone=None,
        recent_closes=[94, 93, 92],
    )
    assert result is not None
    assert result["primary"]["type"] == "support_break"
    assert result["primary"]["new_resistance"] == 95


def test_evaluate_sr_transformation_no_break_without_3_days():
    result = evaluate_sr_transformation(
        close=110,
        support_zone=None,
        resistance_zone={"zone_high": 105},
        recent_closes=[106],  # only 1 day
    )
    assert result is None


def test_evaluate_sr_transformation_no_break_if_not_above():
    result = evaluate_sr_transformation(
        close=104,  # below resistance high
        support_zone=None,
        resistance_zone={"zone_high": 105},
        recent_closes=[104, 104, 104],
    )
    assert result is None


def test_evaluate_sr_transformation_strong_break_requires_1pct():
    result = evaluate_sr_transformation(
        close=105.5,  # only 0.5% above 105, not > 1%
        support_zone=None,
        resistance_zone={"zone_high": 105},
        recent_closes=[106, 106, 106],
    )
    assert result is None


def test_old_import_path_still_works():
    """technical_analyzer re-exports compute_bias etc."""
    from technical_analyzer import compute_bias, compute_weekly_trend, find_support_resistance
    assert callable(compute_bias)
    assert callable(compute_weekly_trend)
    assert callable(find_support_resistance)
