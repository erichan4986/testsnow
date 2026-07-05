import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
import numpy as np
from technical_analyzer import compute_weekly_trend


def make_weekly_df(close_list):
    return pd.DataFrame({
        "close": close_list,
        "open": [c * 0.99 for c in close_list],
        "high": [c * 1.01 for c in close_list],
        "low": [c * 0.98 for c in close_list],
        "volume": [1000] * len(close_list),
    })


def test_weekly_uptrend():
    close = [100.0]
    for _ in range(1, 30):
        close.append(close[-1] * 1.02)
    df = make_weekly_df(close)
    result = compute_weekly_trend(df)
    assert result["weekly_trend"] == "单边上涨"
    assert result["weekly_trend_evidence"]["weeks_above_ma5_ma10"] >= 5


def test_weekly_choppy():
    close = [100.0 + (i % 4 - 2) * 5 for i in range(30)]
    df = make_weekly_df(close)
    result = compute_weekly_trend(df)
    assert result["weekly_trend"] == "震荡"


def test_weekly_downtrend():
    close = [200.0]
    for _ in range(1, 30):
        close.append(close[-1] * 0.98)
    df = make_weekly_df(close)
    result = compute_weekly_trend(df)
    assert result["weekly_trend"] == "单边下跌"


def test_weekly_insufficient_data():
    df = make_weekly_df([100.0] * 5)
    result = compute_weekly_trend(df)
    assert result["weekly_trend"] == "未知"
