import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
import numpy as np
from technical_analyzer import compute_candle_features, compute_ma_direction, resample_daily_to_weekly


def test_candle_features_basic():
    df = pd.DataFrame({
        "open": [100.0], "high": [105.0], "low": [98.0], "close": [103.0],
    })
    result = compute_candle_features(df)
    assert result["body_len"] == 3.0
    assert result["upper_shadow"] == 2.0
    assert result["lower_shadow"] == 2.0
    assert result["is_doji"] == False


def test_candle_features_long_shadow():
    df = pd.DataFrame({
        "open": [100.0], "high": [110.0], "low": [99.0], "close": [100.5],
    })
    result = compute_candle_features(df)
    assert result["is_long_upper_shadow"] == True
    assert result["is_long_lower_shadow"] == False


def test_ma_direction_up():
    ma = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    assert compute_ma_direction(ma, lookback=5, flat_threshold=0.005) == "向上"


def test_ma_direction_flat():
    ma = pd.Series([100.0] * 6)
    assert compute_ma_direction(ma, lookback=5, flat_threshold=0.005) == "走平"


def test_ma_direction_down():
    ma = pd.Series([105.0, 104.0, 103.0, 102.0, 101.0, 100.0])
    assert compute_ma_direction(ma, lookback=5, flat_threshold=0.005) == "向下"


def test_resample_daily_to_weekly():
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "open": [100.0] * 30,
        "high": [105.0] * 30,
        "low": [95.0] * 30,
        "close": list(range(100, 130)),
        "volume": [1000] * 30,
    })
    weekly = resample_daily_to_weekly(df)
    assert len(weekly) >= 4
    assert "open" in weekly.columns
    assert "high" in weekly.columns
    assert "low" in weekly.columns
    assert "close" in weekly.columns
    assert "volume" in weekly.columns
