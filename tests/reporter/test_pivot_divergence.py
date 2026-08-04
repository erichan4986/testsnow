import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd

import technical_patterns


def _series_fixture(kind="bullish", second_index=20, second_price=None, periods=30):
    dates = pd.date_range("2026-01-01", periods=periods, freq="B")
    close = [100.0] * periods
    high = [101.0] * periods
    low = [99.0] * periods
    rsi = pd.Series([50.0] * periods)
    hist = pd.Series([0.0] * periods)
    first = 10
    if kind == "bullish":
        low[first], close[first], rsi.iloc[first], hist.iloc[first] = 90.0, 92.0, 20.0, -2.0
        low[second_index] = 85.0 if second_price is None else second_price
        close[second_index], rsi.iloc[second_index], hist.iloc[second_index] = low[second_index] + 2, 30.0, -1.0
    else:
        high[first], close[first], rsi.iloc[first], hist.iloc[first] = 110.0, 108.0, 80.0, 2.0
        high[second_index] = 116.0 if second_price is None else second_price
        close[second_index], rsi.iloc[second_index], hist.iloc[second_index] = high[second_index] - 2, 70.0, 1.0
    df = pd.DataFrame({
        "date": dates, "open": close, "high": high, "low": low,
        "close": close, "volume": [1000.0] * periods,
    })
    return df, rsi, hist


def _config(max_signal_age=10):
    return {"technical": {"divergence": {
        "lookback": 80, "swing_left": 2, "swing_right": 2,
        "min_matched": 2, "max_signal_age": max_signal_age,
        "price_tolerance_pct": 0.01, "price_atr_multiplier": 0.5,
    }}}


def test_confirmed_lower_low_with_higher_rsi_and_macd_is_bullish_divergence():
    df, rsi, hist = _series_fixture("bullish")

    result = technical_patterns.detect_pivot_divergence(df, rsi, hist, _config())

    assert result["family"] == "pivot_divergence"
    assert result["type"] == "底背离观察"
    assert result["matched"] == 3
    assert result["pivots"][1]["price"] == 85.0


def test_confirmed_higher_high_with_lower_rsi_and_macd_is_bearish_divergence():
    df, rsi, hist = _series_fixture("bearish")

    result = technical_patterns.detect_pivot_divergence(df, rsi, hist, _config())

    assert result["type"] == "顶背离观察"
    assert result["matched"] == 3


def test_immaterial_price_change_is_not_divergence():
    df, rsi, hist = _series_fixture("bullish", second_price=89.7)

    assert technical_patterns.detect_pivot_divergence(df, rsi, hist, _config()) is None


def test_lower_price_low_without_opposite_momentum_is_not_divergence():
    df, rsi, hist = _series_fixture("bullish")
    rsi.iloc[20], hist.iloc[20] = 15.0, -3.0

    assert technical_patterns.detect_pivot_divergence(df, rsi, hist, _config()) is None


def test_one_available_momentum_series_can_confirm_without_emitting_nan():
    df, rsi, hist = _series_fixture("bullish")
    hist.iloc[20] = float("nan")

    result = technical_patterns.detect_pivot_divergence(df, rsi, hist, _config())

    assert result["matched"] == 2
    assert result["pivots"][1]["macd_hist"] is None
    assert "macd" in result["missing"]


def test_non_positive_pivot_price_fails_closed():
    df, rsi, hist = _series_fixture("bullish", second_price=0.0)

    assert technical_patterns.detect_pivot_divergence(df, rsi, hist, _config()) is None


def test_unconfirmed_right_edge_pivot_is_ignored():
    df, rsi, hist = _series_fixture("bullish", second_index=28)

    assert technical_patterns.detect_pivot_divergence(df, rsi, hist, _config()) is None


def test_stale_confirmed_pivot_is_ignored():
    df, rsi, hist = _series_fixture("bullish", second_index=20, periods=40)

    assert technical_patterns.detect_pivot_divergence(df, rsi, hist, _config(max_signal_age=10)) is None
