import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
from technical_analyzer import _compute_base_indicators


def _make_df(close_list):
    return pd.DataFrame({
        "close": close_list,
        "open": [c * 0.99 for c in close_list],
        "high": [c * 1.01 for c in close_list],
        "low": [c * 0.98 for c in close_list],
        "volume": [1000] * len(close_list),
    })


def test_base_indicators_contain_old_fields():
    close = [100.0 + i * 0.5 for i in range(150)]
    df = _make_df(close)
    indicators = _compute_base_indicators(df)
    required = [
        "close", "volume",
        "macd", "macd_signal", "macd_hist",
        "rsi_14", "adx", "plus_di", "minus_di",
        "boll_upper", "boll_mid", "boll_lower",
        "atr_14", "williams_r", "stoch_rsi_k", "stoch_rsi_d", "cci_20",
        "ma_5", "ma_10", "ma_20", "ma_60",
        "obv", "obv_slope_5", "price_slope_5",
    ]
    for key in required:
        assert key in indicators, f"missing {key}"
        assert indicators[key] is not None, f"{key} is None"
