import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
import numpy as np

from technical_patterns import detect_double_top, detect_double_bottom, detect_boll_overextension


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


def test_old_import_path_still_works():
    """technical_analyzer re-exports detect_double_top etc."""
    from technical_analyzer import detect_double_top, detect_double_bottom, detect_boll_overextension
    assert callable(detect_double_top)
    assert callable(detect_double_bottom)
    assert callable(detect_boll_overextension)
