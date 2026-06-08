import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

from technical_analyzer import compute_trend_health, compute_invalidation


def test_trend_health_clamped():
    result = compute_trend_health(
        weekly_trend="单边上涨",
        daily_structure={"ma20_direction": "向上", "price_vs_ma20": "站上"},
        indicators={"rsi_14": 50, "boll_state": "正常"},
    )
    assert 0 <= result["score"] <= 100
    assert result["grade"] in ["趋势强健", "健康", "转弱观察", "破坏风险高", "趋势失效"]
    assert "components" in result
    assert "penalties" in result


def test_invalidation_basic():
    result = compute_invalidation(
        close=100.0, ma20=95.0, ma60=90.0,
        support_zone={"zone_low": 85.0},
    )
    assert "soft_warning" in result
    assert "hard_invalid" in result
    assert "hard_invalid_price" in result
    assert result["hard_invalid_price"] == 90.0
    assert result["current_distance_to_invalid"] is not None
