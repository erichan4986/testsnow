import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
import numpy as np

from technical_structure import (
    compute_bias, compute_boll_state, compute_candle_features,
    compute_ma_direction, resample_daily_to_weekly,
    compute_weekly_trend, find_support_resistance,
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


def test_old_import_path_still_works():
    """technical_analyzer re-exports compute_bias etc."""
    from technical_analyzer import compute_bias, compute_weekly_trend, find_support_resistance
    assert callable(compute_bias)
    assert callable(compute_weekly_trend)
    assert callable(find_support_resistance)
