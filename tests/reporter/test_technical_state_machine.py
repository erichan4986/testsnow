import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

from technical_state_machine import (
    classify_trend_state, apply_previous_state,
    compute_trend_health, compute_invalidation,
)


def test_classify_trend_state_basic():
    result = classify_trend_state(
        weekly_trend="单边上涨",
        daily_structure={"price_vs_ma20": "站上", "price_vs_ma60": "站上", "ma20_direction": "向上", "ma60_direction": "向上"},
        indicators={"close": 105, "ma_20": 100, "ma_60": 95, "boll_state": "正常", "rsi_14": 50},
        divergence=None,
    )
    assert "stage" in result
    assert result["stage"] in ["破坏期", "转弱期", "高位钝化期", "加速期", "主升期", "启动期", "盘整期"]


def test_apply_previous_state():
    ts = {"stage": "主升期"}
    apply_previous_state(ts, {"trend_state": {"stage": "启动期"}})
    assert ts["state_changed"] is True
    assert ts["previous_state"] == "启动期"


def test_compute_trend_health_basic():
    result = compute_trend_health(
        weekly_trend="单边上涨",
        daily_structure={"ma20_direction": "向上", "ma60_direction": "向上", "price_vs_ma20": "站上", "structure_type": "上升通道"},
        indicators={"boll_state": "开口", "rsi_14": 60, "bias_5": 2},
    )
    assert "score" in result
    assert 0 <= result["score"] <= 100
    assert "grade" in result


def test_compute_invalidation_basic():
    result = compute_invalidation(close=100, ma20=95, ma60=90, support_zone=None)
    assert "soft_warning" in result
    assert "hard_invalid" in result


def test_old_import_path_still_works():
    """technical_analyzer re-exports classify_trend_state etc."""
    from technical_analyzer import classify_trend_state, compute_trend_health, compute_invalidation
    assert callable(classify_trend_state)
    assert callable(compute_trend_health)
    assert callable(compute_invalidation)
