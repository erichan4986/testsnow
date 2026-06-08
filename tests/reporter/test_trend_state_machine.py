import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

from technical_analyzer import classify_trend_state, apply_previous_state


def _base_indicators():
    return {
        "close": 100.0, "ma_5": 99.0, "ma_10": 98.0, "ma_20": 96.0, "ma_60": 90.0,
        "rsi_14": 55.0, "boll_state": "正常",
    }


def test_uptrend_main_rise():
    result = classify_trend_state(
        weekly_trend="单边上涨",
        daily_structure={"price_vs_ma20": "站上", "price_vs_ma60": "站上", "ma20_direction": "向上", "ma60_direction": "向上"},
        indicators=_base_indicators(),
        divergence=None,
    )
    assert result["stage"] == "主升期"
    assert result["primary_state"] == "上升趋势"


def test_destruction_priority():
    """破坏期应优先于其他状态。price_vs_ma60=='跌破' 即判定。"""
    indicators = _base_indicators()
    indicators["rsi_14"] = 75
    result = classify_trend_state(
        weekly_trend="单边上涨",
        daily_structure={"price_vs_ma20": "跌破", "price_vs_ma60": "跌破", "ma20_direction": "向下"},
        indicators=indicators,
        divergence=None,
    )
    assert result["stage"] == "破坏期"


def test_weak_over_pretty():
    """转弱期优先于高位钝化期。"""
    indicators = _base_indicators()
    indicators["rsi_14"] = 78
    indicators["boll_state"] = "开口"
    result = classify_trend_state(
        weekly_trend="单边上涨",
        daily_structure={"price_vs_ma20": "跌破", "price_vs_ma60": "站上", "ma20_direction": "走平"},
        indicators=indicators,
        divergence=None,
    )
    assert result["stage"] == "转弱期"


def test_apply_previous_state_first_time():
    """首次分析时 previous_state=None，state_changed=None。"""
    trend_state = {"stage": "主升期", "primary_state": "上升趋势"}
    apply_previous_state(trend_state, None)
    assert trend_state["state_changed"] is None
    assert trend_state["previous_state"] is None


def test_apply_previous_state_changed():
    """状态变化时标记 state_changed=True。"""
    trend_state = {"stage": "转弱期", "primary_state": "上升趋势"}
    prev = {"trend_state": {"stage": "主升期"}}
    apply_previous_state(trend_state, prev)
    assert trend_state["state_changed"] is True
    assert trend_state["previous_state"] == "主升期"
