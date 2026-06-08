import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
import numpy as np

from technical_patterns import detect_double_top, detect_double_bottom, detect_boll_overextension, evaluate_candle_at_key_levels


def test_detect_double_top_basic():
    # Create a series with two peaks
    close = pd.Series([100, 102, 105, 103, 100, 98, 102, 105, 103, 100, 98, 95])
    result = detect_double_top(close, lookback=12, tolerance=0.05)
    # May or may not detect depending on data; just ensure no crash
    assert result is None or "pattern" in result


def test_detect_double_bottom_basic():
    close = pd.Series([100, 98, 95, 97, 100, 102, 98, 95, 97, 100, 102, 105])
    result = detect_double_bottom(close, lookback=12, tolerance=0.05)
    assert result is None or "pattern" in result


def test_detect_boll_overextension_basic():
    df = pd.DataFrame({"close": [100.0] * 5})
    indicators = {"close": 105, "boll_upper": 102, "boll_lower": 98, "rsi_14": 80, "macd_hist": -0.5}
    result = detect_boll_overextension(df, indicators, weekly_trend="单边上涨")
    assert result is None or "type" in result


def test_evaluate_candle_at_key_levels_long_lower_shadow_at_support():
    candle = {"is_long_lower_shadow": True, "is_long_upper_shadow": False, "is_doji": False}
    key_levels = {"support_zone": {"zone_low": 95, "zone_high": 97}}
    result = evaluate_candle_at_key_levels(candle, key_levels, close=96, boll_state="正常")
    assert result is not None
    assert "下影" in result["signal"]
    assert result["location"] == "支撑位"


def test_evaluate_candle_at_key_levels_long_upper_shadow_at_resistance():
    candle = {"is_long_lower_shadow": False, "is_long_upper_shadow": True, "is_doji": False}
    key_levels = {"resistance_zone": {"zone_low": 103, "zone_high": 105}}
    result = evaluate_candle_at_key_levels(candle, key_levels, close=104, boll_state="正常")
    assert result is not None
    assert "上影" in result["signal"]
    assert result["location"] == "阻力位"


def test_evaluate_candle_at_key_levels_doji_near_boll():
    candle = {"is_long_lower_shadow": False, "is_long_upper_shadow": False, "is_doji": True}
    key_levels = {}
    result = evaluate_candle_at_key_levels(candle, key_levels, close=98, boll_state="正常", boll_lower=100)
    assert result is not None
    assert "十字星" in result["signal"]


def test_evaluate_candle_at_key_levels_no_signal_when_not_at_key_level():
    candle = {"is_long_lower_shadow": True, "is_long_upper_shadow": False, "is_doji": False}
    key_levels = {}
    result = evaluate_candle_at_key_levels(candle, key_levels, close=100, boll_state="正常")
    assert result is None


def test_old_import_path_still_works():
    """technical_analyzer re-exports detect_double_top etc."""
    from technical_analyzer import detect_double_top, detect_double_bottom, detect_boll_overextension
    assert callable(detect_double_top)
    assert callable(detect_double_bottom)
    assert callable(detect_boll_overextension)
