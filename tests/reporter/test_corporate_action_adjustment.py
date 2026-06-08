"""回归测试：除权场景与Phase 2命名约束验证。"""

import pytest

pytestmark = pytest.mark.skip(reason="Corporate action integration not yet fully implemented")

import numpy as np
import pandas as pd


def _make_exrights_df(days=130, exrights_date="2026-06-05", split_ratio=1.4):
    """生成带有模拟除权除息的日K数据。"""
    np.random.seed(42)
    dates = pd.date_range(end=pd.Timestamp("2026-06-08"), periods=days, freq="B")
    base = 200.0
    prices = base * np.exp(np.cumsum(np.random.normal(0.0003, 0.015, days)))

    # 模拟除权：除权日后价格机械性下调
    split_idx = None
    for i, d in enumerate(dates):
        if str(d.date()) == exrights_date:
            split_idx = i
            break
    if split_idx is not None:
        prices[split_idx:] = prices[split_idx:] / split_ratio

    df = pd.DataFrame({
        "date": dates,
        "open": prices * (1 + np.random.normal(0, 0.005, days)),
        "close": prices,
        "high": prices * (1 + np.random.uniform(0.005, 0.02, days)),
        "low": prices * (1 - np.random.uniform(0.005, 0.02, days)),
        "volume": np.random.poisson(50000, days),
    })
    df["high"] = df[["open", "close", "high"]].max(axis=1)
    df["low"] = df[["open", "close", "low"]].min(axis=1)
    return df


def test_corporate_action_lowers_confidence():
    sys = pytest.importorskip("sys")
    from pathlib import Path
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_analyzer import advanced_medium_term_resonance

    df = _make_exrights_df()
    result = advanced_medium_term_resonance(
        df_daily=df,
        quote={
            "adjustment": "raw",
            "corporate_actions": [
                {"date": "2026-06-05", "type": "10转4派5"},
            ],
        },
    )
    resonance = result["resonance"]
    assert resonance["analysis_confidence"]["level"] == "低", (
        f"未使用前复权且有近期除权，confidence 应为低，实际为 {resonance['analysis_confidence']['level']}"
    )
    assert "corporate_action_warning" in resonance
    assert resonance["corporate_action_warning"]["has_recent_action"] is True


def test_qfq_maintains_medium_confidence():
    sys = pytest.importorskip("sys")
    from pathlib import Path
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_analyzer import advanced_medium_term_resonance

    df = _make_exrights_df()
    result = advanced_medium_term_resonance(
        df_daily=df,
        quote={
            "adjustment": "qfq",
            "corporate_actions": [
                {"date": "2026-06-05", "type": "10转4派5"},
            ],
        },
    )
    resonance = result["resonance"]
    # 有除权但使用 qfq，至少应为中（日线>=120）
    assert resonance["analysis_confidence"]["level"] == "中", (
        f"使用 qfq 且日线>=120，confidence 至少应为中，实际为 {resonance['analysis_confidence']['level']}"
    )


def test_no_triple_divergence_naming():
    sys = pytest.importorskip("sys")
    from pathlib import Path
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_patterns import detect_boll_overextension

    indicators = {
        "close": 100.0,
        "boll_upper": 95.0,
        "boll_lower": 80.0,
        "rsi_14": 20.0,
        "macd_hist": -0.5,
    }
    df = pd.DataFrame({"close": [100.0] * 10})
    div = detect_boll_overextension(df, indicators, weekly_trend="震荡")
    assert div is not None
    type_ = div["type"]
    assert "完整" not in type_, f"Phase 2 不得输出'完整'字样：{type_}"
    assert "三重" not in type_, f"Phase 2 不得输出'三重'字样：{type_}"
    assert "底背离" not in type_, f"Phase 2 不得输出'底背离'字样：{type_}"
    assert "顶背离" not in type_, f"Phase 2 不得输出'顶背离'字样：{type_}"


def test_invalidation_separates_price_and_distance():
    sys = pytest.importorskip("sys")
    from pathlib import Path
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_state_machine import compute_invalidation

    inv = compute_invalidation(close=100.0, ma20=110.0, ma60=120.0, support_zone=None)
    assert inv["hard_invalid_price"] == 120.0
    assert inv["hard_invalid_source"] == "MA60"
    assert inv["is_invalidated"] is True
    assert inv["current_distance_to_invalid"] is not None


def test_candle_location_strict_in_zone():
    sys = pytest.importorskip("sys")
    from pathlib import Path
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_patterns import evaluate_candle_at_key_levels

    candle = {"is_long_lower_shadow": True, "is_doji": False, "is_long_upper_shadow": False}
    key_levels = {
        "support_zone": {"zone_low": 100.0, "zone_high": 102.0},
    }

    # close 在支撑区内 -> 位置：支撑位
    sig = evaluate_candle_at_key_levels(candle, key_levels, close=101.0, boll_state="正常")
    assert sig is not None
    assert sig["location"] == "支撑位"

    # close 跌破支撑区 -> 不得输出"位置：支撑位"
    sig = evaluate_candle_at_key_levels(candle, key_levels, close=98.0, boll_state="正常")
    if sig is not None:
        assert sig["location"] != "支撑位", f"close 已跌破支撑区，不应显示支撑位：{sig}"
        assert "跌破" in sig["signal"] or "下方" in sig["location"], f"应提示已跌破原支撑区：{sig}"
