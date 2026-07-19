import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
from technical_analyzer import _build_advisors, detect_boll_overextension
import technical_patterns


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


def test_macd_histogram_classifier_uses_adjacent_direction():
    classify = technical_patterns.classify_macd_histogram
    assert classify(-0.5, -0.2) == "空头柱扩张"
    assert classify(-0.2, -0.5) == "空头柱收缩"
    assert classify(0.5, 0.2) == "多头柱扩张"
    assert classify(0.2, 0.5) == "多头柱收缩"
    assert classify(0.2, 0.2) == "方向未确认"
    assert classify(None, 0.2) == "方向未确认"


def test_negative_expanding_histogram_does_not_confirm_oversold_repair():
    df = _make_df([100.0] * 30)
    indicators = {
        "close": 90.0, "boll_upper": 110.0, "boll_lower": 95.0,
        "rsi_14": 20.0, "macd_hist": -0.5, "macd_hist_prev": -0.2,
    }

    result = detect_boll_overextension(df, indicators, weekly_trend="震荡")

    assert result["family"] == "momentum_extreme"
    assert result["matched"] == 2
    assert result["confidence"] == "中度"
    assert result["evidence"]["macd"]["state"] == "空头柱扩张"


def test_negative_contracting_histogram_confirms_oversold_repair():
    df = _make_df([100.0] * 30)
    indicators = {
        "close": 90.0, "boll_upper": 110.0, "boll_lower": 95.0,
        "rsi_14": 20.0, "macd_hist": -0.2, "macd_hist_prev": -0.5,
    }

    result = detect_boll_overextension(df, indicators, weekly_trend="震荡")

    assert result["matched"] == 3
    assert result["confidence"] == "强烈"
    assert result["evidence"]["macd"]["state"] == "空头柱收缩"


def test_advisor_and_scan_share_macd_histogram_state():
    indicators = {
        "close": 90.0, "boll_upper": 110.0, "boll_lower": 95.0,
        "rsi_14": 20.0, "macd": -1.0,
        "macd_hist": -0.5, "macd_hist_prev": -0.2,
    }
    scan = detect_boll_overextension(_make_df([100.0] * 30), indicators, weekly_trend="震荡")

    assert _build_advisors(indicators)["macd"]["state"] == "空头柱扩张"
    assert scan["evidence"]["macd"]["state"] == "空头柱扩张"


def test_positive_histogram_contraction_but_not_expansion_confirms_exhaustion():
    df = _make_df([100.0] * 30)
    base = {
        "close": 110.0, "boll_upper": 105.0, "boll_lower": 90.0,
        "rsi_14": 80.0,
    }

    expanding = detect_boll_overextension(
        df, {**base, "macd_hist": 0.5, "macd_hist_prev": 0.2}, weekly_trend="单边上涨",
    )
    contracting = detect_boll_overextension(
        df, {**base, "macd_hist": 0.2, "macd_hist_prev": 0.5}, weekly_trend="单边上涨",
    )

    assert expanding["matched"] == 2
    assert contracting["matched"] == 3
