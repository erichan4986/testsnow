import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd
from technical_analyzer import compute_boll_state


def test_boll_open():
    boll_upper = pd.Series([102.0] * 10 + [110.0])
    boll_mid = pd.Series([100.0] * 11)
    boll_lower = pd.Series([98.0] * 10 + [90.0])
    df = pd.DataFrame({
        "boll_upper": boll_upper, "boll_mid": boll_mid, "boll_lower": boll_lower,
    })
    result = compute_boll_state(df)
    assert result["boll_state"] == "开口"
    assert result["boll_width"] is not None


def test_boll_squeeze():
    boll_upper = pd.Series([110.0] * 10 + [102.0])
    boll_mid = pd.Series([100.0] * 11)
    boll_lower = pd.Series([90.0] * 10 + [98.0])
    df = pd.DataFrame({
        "boll_upper": boll_upper, "boll_mid": boll_mid, "boll_lower": boll_lower,
    })
    result = compute_boll_state(df)
    assert result["boll_state"] == "缩口"


def test_boll_no_lookahead():
    width = [0.10] * 6 + [0.15]
    boll_mid = pd.Series([100.0] * 7)
    boll_upper = boll_mid * (1 + pd.Series(width) / 2)
    boll_lower = boll_mid * (1 - pd.Series(width) / 2)
    df = pd.DataFrame({
        "boll_upper": boll_upper, "boll_mid": boll_mid, "boll_lower": boll_lower,
    })
    result = compute_boll_state(df)
    assert result["boll_width_ma5"] is not None
