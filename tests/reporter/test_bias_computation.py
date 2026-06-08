import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import numpy as np
import pandas as pd
from technical_analyzer import compute_bias


def _make_df(close_list):
    return pd.DataFrame({
        "close": close_list,
        "open": close_list,
        "high": close_list,
        "low": close_list,
        "volume": [1000] * len(close_list),
    })


def test_bias_basic():
    df = _make_df([100.0] * 30)
    result = compute_bias(df)
    assert "bias_5" in result
    assert result["bias_5"] == 0.0


def test_bias_extreme_no_lookahead():
    """BIAS 极值判断不应使用当天数据参与历史极值。"""
    close = list(range(1, 121))
    close.extend([150.0] * 10)
    df = _make_df(close)
    result = compute_bias(df)
    assert isinstance(result["bias_5_extreme_high"], bool)
    assert isinstance(result["bias_5_extreme_low"], bool)


def test_bias_extreme_high_detected():
    """构造一个 BIAS(5) 创历史新高的场景。"""
    np.random.seed(42)
    close = [100.0]
    for _ in range(1, 125):
        close.append(close[-1] * (1 + np.random.normal(0, 0.01)))
    close[-1] = close[-1] * 1.15
    df = _make_df(close)
    result = compute_bias(df, lookback=120)
    assert result["bias_5"] is not None
    assert result["bias_5"] > 0
