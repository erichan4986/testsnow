import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
from technical_analyzer import detect_boll_overextension


def _make_df(close_list):
    return pd.DataFrame({
        "close": close_list,
        "open": close_list,
        "high": [c * 1.01 for c in close_list],
        "low": [c * 0.99 for c in close_list],
        "volume": [1000] * len(close_list),
    })


def test_no_overextension():
    close = [100.0 + i * 0.5 for i in range(50)]
    df = _make_df(close)
    indicators = {
        "close": close[-1], "boll_upper": close[-1] * 1.02, "boll_mid": close[-1], "boll_lower": close[-1] * 0.98,
        "macd": 1.0, "macd_hist": 0.5, "rsi_14": 55.0,
    }
    result = detect_boll_overextension(df, indicators, weekly_trend="单边上涨")
    assert result is None


def test_boll_overextension_detected():
    """价格远高于上轨 + RSI 高位 = 预警。"""
    close = [100.0] * 30
    close.extend([110.0] * 5)
    df = _make_df(close)
    indicators = {
        "close": 110.0,
        "boll_upper": 105.0, "boll_mid": 102.0, "boll_lower": 100.0,
        "macd": 0.8, "macd_hist": 0.3,
        "rsi_14": 78.0,
    }
    result = detect_boll_overextension(df, indicators, weekly_trend="单边上涨")
    assert result is not None
    assert result["type"] == "超买预警"
    assert result["confidence"] in ["中度", "强烈"]
