import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
from technical_analyzer import analyze


def _make_df(close_list):
    return pd.DataFrame({
        "close": close_list,
        "open": [c * 0.99 for c in close_list],
        "high": [c * 1.01 for c in close_list],
        "low": [c * 0.98 for c in close_list],
        "volume": [1000] * len(close_list),
    })


def test_analyze_returns_backward_compatible_shape():
    close = [100.0]
    for _ in range(1, 150):
        close.append(close[-1] * (1 + (0.01 if _ % 2 == 0 else -0.005)))
    df = _make_df(close)
    result = analyze(df)
    assert "indicators" in result
    assert "resonance" in result
    assert "patterns" in result
    assert "levels" in result
    # backward compatible fields
    res = result["resonance"]
    assert "trend" in res
    assert "composite_score" in res
    assert "trend_state" in res
    # old indicator fields must exist
    ind = result["indicators"]
    assert "rsi_14" in ind
    assert "macd" in ind
    assert "ma_20" in ind
    assert "boll_upper" in ind
    assert "atr_14" in ind


def test_analyze_schema_stable_after_refactor():
    """Verify analyze() returns the exact dict schema expected by consumers."""
    close = [100.0]
    for _ in range(1, 150):
        close.append(close[-1] * (1 + (0.01 if _ % 2 == 0 else -0.005)))
    df = _make_df(close)

    result = analyze(df)

    # Top-level keys
    assert "indicators" in result
    assert "resonance" in result
    assert "patterns" in result
    assert "levels" in result

    indicators = result["indicators"]
    required_indicator_keys = [
        "close", "volume", "macd", "macd_signal", "macd_hist",
        "rsi_14", "adx", "plus_di", "minus_di",
        "ma_5", "ma_10", "ma_20", "ma_60",
        "boll_upper", "boll_mid", "boll_lower", "atr_14",
    ]
    for key in required_indicator_keys:
        assert key in indicators, f"missing indicator key: {key}"

    resonance = result["resonance"]
    required_resonance_keys = [
        "trend", "momentum", "volume_price", "composite_score",
        "signals", "trend_state", "trend_health", "invalidation",
    ]
    for key in required_resonance_keys:
        assert key in resonance, f"missing resonance key: {key}"
