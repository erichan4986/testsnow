import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))

import pandas as pd

from technical_state_machine import (
    classify_trend_state, apply_previous_state,
    compute_trend_health, compute_invalidation,
    evaluate_bias_extreme, evaluate_sell_three_factors,
    detect_false_rebound, detect_false_breakout,
    build_technical_judgment, ensure_technical_judgment,
    resolve_target_display_mode,
)


def _target_payload(**overrides):
    target = {
        "status": "ready",
        "reason_code": "target_ready",
        "direction": "bullish",
        "structure_confidence": "high",
        "structure_evidence": {"method_family": "dual_pattern"},
        "profit_risk": {
            "pass": True,
            "ratio": 2.0,
            "direction": "bullish",
            "neckline": 100.0,
            "daily_atr": 2.0,
            "trigger_price": 100.6,
            "stop_price": 97.0,
            "potential_gain": 9.4,
            "initial_risk": 3.6,
        },
        "targets": {"conservative": 110.0, "base": 115.0, "aggressive": 120.0},
    }
    target.update(overrides)
    return target


def _resonance_payload(target=None, **overrides):
    resonance = {
        "trend_state": {"primary_state": "上升趋势", "stage": "主升期"},
        "trend_health": {"score": 80, "grade": "健康"},
        "invalidation": {"status": "safe", "is_invalidated": False},
        "price_data_lineage": {"effective_adjustment": "raw", "price_adjustment_applied": False},
        "weekly_trend": {"direction": "多头", "adx": 30, "plus_di": 30, "minus_di": 15},
        "structure_evidence": {"method_family": "dual_pattern"},
        "trigger_checks": {
            "price": {"status": "pass"},
            "trend": {"status": "pass"},
            "volume": {"status": "pass"},
            "momentum": {"status": "pass"},
        },
    }
    resonance.update(overrides)
    return resonance


def test_build_technical_judgment_has_stable_contract_and_copies_target_status():
    judgment = build_technical_judgment(
        resonance=_resonance_payload(),
        price_target=_target_payload(),
        indicators={"analysis_confidence": {"level": "高"}, "close": 105.0},
        daily_data={"open": [101.0], "close": [105.0], "volume": [200.0]},
        market="cn",
    )

    assert judgment["schema"] == "technical_judgment.v1"
    assert judgment["target"]["producer_status"] == "ready"
    assert judgment["target"]["reason_code"] == "target_ready"
    assert judgment["target"]["effective_confidence"] == "high"
    assert judgment["action"]["state"] in {"follow", "wait_for_confirmation", "unavailable"}


def test_judgment_low_confidence_does_not_trigger_and_display_resolver_fails_closed():
    resonance = _resonance_payload(
        trigger_checks={"price": {"status": "pass"}, "trend": {"status": "pass"}, "volume": {"status": "pass"}, "momentum": {"status": "pass"}},
    )
    judgment = build_technical_judgment(
        resonance=resonance,
        price_target=_target_payload(structure_confidence="low"),
        indicators={"analysis_confidence": {"level": "高"}},
        daily_data={"open": [101.0], "close": [105.0], "volume": [200.0]},
    )
    assert judgment["target"]["trigger_checks"]["price"]["status"] == "unknown"
    checks = judgment["target"]["trigger_checks"]
    assert checks["trend"]["status"] == "pass"
    assert checks["volume"]["status"] == "pass"
    assert checks["momentum"]["status"] == "pass"
    assert judgment["target"]["execution_state"] != "triggered"
    assert resolve_target_display_mode("bullish", "low", "triggered") == "unavailable"
    assert resolve_target_display_mode("observation", "observation", "blocked") == "blocked"


def test_empty_inputs_build_complete_unavailable_judgment():
    judgment = build_technical_judgment({}, {})

    assert judgment["schema"] == "technical_judgment.v1"
    assert judgment["trend"]["state"] == "unknown"
    assert judgment["target"]["direction"] == "neutral"
    assert judgment["target"]["producer_status"] == "unavailable"
    assert judgment["target"]["reason_code"] == "untrusted_or_malformed_judgment"
    assert judgment["target"]["structure_confidence"] == "unavailable"
    assert judgment["target"]["effective_confidence"] == "unavailable"
    assert judgment["target"]["execution_state"] == "unavailable"
    assert judgment["target"]["display_mode"] == "unavailable"
    assert judgment["action"]["state"] == "unavailable"
    assert set(judgment["target"]["trigger_checks"]) == {
        "price", "trend", "volume", "momentum",
    }
    assert all(
        check["status"] == "unknown"
        for check in judgment["target"]["trigger_checks"].values()
    )


def test_ensure_technical_judgment_malformed_cache_is_unavailable():
    judgment = ensure_technical_judgment(
        {"schema": "unknown", "target": {"direction": "bullish"}},
        resonance={"trend_state": {}, "trigger_checks": {}},
    )
    assert judgment["schema"] == "technical_judgment.v1"
    assert judgment["target"]["direction"] == "neutral"
    assert judgment["target"]["producer_status"] == "unavailable"
    assert judgment["target"]["reason_code"] == "untrusted_or_malformed_judgment"
    assert judgment["target"]["display_mode"] == "unavailable"
    assert judgment["action"]["state"] == "unavailable"


def test_ensure_technical_judgment_rejects_contradictory_v1_cache():
    cached = {
        "schema": "technical_judgment.v1",
        "trend": {"state": "unknown"},
        "target": {
            "direction": "neutral", "producer_status": "unavailable",
            "reason_code": "stale_cache", "structure_confidence": "unavailable",
            "effective_confidence": "unavailable", "execution_state": "unavailable",
            "display_mode": "full_targets",
            "trigger_checks": {
                name: {"status": "pass"}
                for name in ("price", "trend", "volume", "momentum")
            },
        },
        "action": {"state": "follow"},
    }

    judgment = ensure_technical_judgment(cached)

    assert judgment is not cached
    assert judgment["target"]["display_mode"] == "unavailable"
    assert judgment["action"]["state"] == "unavailable"


def test_invalid_supplied_trigger_status_is_recalculated_fail_closed():
    resonance = _resonance_payload(trigger_checks={
        name: {"status": "trusted"}
        for name in ("price", "trend", "volume", "momentum")
    })

    judgment = build_technical_judgment(
        resonance=resonance,
        price_target=_target_payload(),
        indicators={"analysis_confidence": {"level": "高"}},
    )

    assert all(
        check["status"] != "trusted"
        for check in judgment["target"]["trigger_checks"].values()
    )


def test_judgment_calculates_trigger_checks_from_market_data():
    daily = pd.DataFrame({
        "open": [100.0] * 20 + [102.0],
        "close": [100.0] * 20 + [105.0],
        "volume": [100.0] * 20 + [200.0],
    })
    resonance = _resonance_payload(trigger_checks={})
    judgment = build_technical_judgment(
        resonance=resonance,
        price_target=_target_payload(),
        indicators={"analysis_confidence": {"level": "高"}, "macd": 1.0, "macd_signal": 0.5, "rsi_14": 55.0},
        daily_data=daily,
        market="cn",
    )

    assert {check["status"] for check in judgment["target"]["trigger_checks"].values()} == {"pass"}
    assert judgment["target"]["trigger_checks"]["volume"]["detail"] == "成交额未核验"
    assert judgment["target"]["execution_state"] == "triggered"
    assert judgment["action"]["state"] == "follow"


def test_judgment_uses_hk_volume_ratio_threshold():
    daily = pd.DataFrame({
        "open": [100.0] * 20 + [102.0],
        "close": [100.0] * 20 + [105.0],
        "volume": [100.0] * 20 + [140.0],
    })
    resonance = _resonance_payload(trigger_checks={})
    kwargs = {
        "resonance": resonance,
        "price_target": _target_payload(),
        "indicators": {"analysis_confidence": {"level": "高"}, "macd": 1.0, "macd_signal": 0.5, "rsi_14": 55.0},
        "daily_data": daily,
    }

    assert build_technical_judgment(**kwargs, market="hk")["target"]["trigger_checks"]["volume"]["status"] == "pass"
    assert build_technical_judgment(**kwargs, market="cn")["target"]["trigger_checks"]["volume"]["status"] == "pending"


def test_uptrend_with_health_below_fifty_is_transition():
    judgment = build_technical_judgment(
        resonance=_resonance_payload(trend_health={"score": 49, "grade": "破坏风险高"}),
        price_target=_target_payload(),
        indicators={"analysis_confidence": {"level": "高"}},
    )

    assert judgment["trend"]["state"] == "transition"


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


def test_evaluate_bias_extreme_high():
    result = evaluate_bias_extreme(
        bias_5=5.5, bias_5_extreme_high=True, bias_5_extreme_low=False,
        bias_10=4.2, bias_10_extreme_high=False, bias_10_extreme_low=False,
    )
    assert result is not None
    assert result["direction"] == "high"
    assert "超买" in result["warning"]


def test_evaluate_bias_extreme_low():
    result = evaluate_bias_extreme(
        bias_5=-5.5, bias_5_extreme_high=False, bias_5_extreme_low=True,
        bias_10=-4.2, bias_10_extreme_high=False, bias_10_extreme_low=False,
    )
    assert result is not None
    assert result["direction"] == "low"
    assert "超卖" in result["warning"]


def test_evaluate_bias_extreme_none():
    result = evaluate_bias_extreme(
        bias_5=1.0, bias_5_extreme_high=False, bias_5_extreme_low=False,
    )
    assert result is None


def test_evaluate_bias_extreme_both_prefers_high():
    # Defensive: both flags set — prefer high for safety
    result = evaluate_bias_extreme(
        bias_5=5.5, bias_5_extreme_high=True, bias_5_extreme_low=True,
    )
    assert result is not None
    assert result["direction"] == "high"


def test_detect_false_rebound_insufficient_data():
    df = pd.DataFrame({
        "open": [100, 101, 102],
        "close": [101, 102, 103],
        "volume": [1000, 1000, 1000],
    })
    result = detect_false_rebound(df, "正常", 1000)
    assert result is None


def test_detect_false_rebound_detected():
    # Single positive day after negative, BOLL not open, volume below avg
    df = pd.DataFrame({
        "open":  [100, 100, 100, 100, 100, 99],
        "close": [99,  99,  99,  99,  99,  102],  # last day positive
        "volume": [1000, 1000, 1000, 1000, 1000, 1000],
    })
    result = detect_false_rebound(df, "正常", 1500)
    assert result is not None
    assert result["type"] == "假反弹预警"


def test_detect_false_rebound_boll_open_excluded():
    df = pd.DataFrame({
        "open":  [100, 100, 100, 100, 100, 99],
        "close": [99,  99,  99,  99,  99,  102],
        "volume": [1000, 1000, 1000, 1000, 1000, 1000],
    })
    result = detect_false_rebound(df, "开口", 1500)
    assert result is None


def test_detect_false_breakout_detected():
    result = detect_false_breakout(
        close=98, ma5=100,
        prev_close=102, prev_ma5=100,
    )
    assert result is not None
    assert result["type"] == "假突破预警"
    assert "停止加仓" in result["signal"]


def test_detect_false_breakout_no_break():
    result = detect_false_breakout(
        close=102, ma5=100,
        prev_close=98, prev_ma5=100,
    )
    assert result is None


def test_evaluate_sell_three_factors_zero_met():
    result = evaluate_sell_three_factors(
        valuation_overpriced=False, ma_breakdown=False, bias_extreme_high=False,
    )
    assert result["met_count"] == 0
    assert "观望" in result["recommendation"]


def test_evaluate_sell_three_factors_one_met():
    result = evaluate_sell_three_factors(
        valuation_overpriced=False, ma_breakdown=True, bias_extreme_high=False,
    )
    assert result["met_count"] == 1
    assert "减仓观察" in result["recommendation"]


def test_evaluate_sell_three_factors_two_met():
    result = evaluate_sell_three_factors(
        valuation_overpriced=False, ma_breakdown=True, bias_extreme_high=True,
    )
    assert result["met_count"] == 2
    assert "建议卖出" in result["recommendation"]


def test_evaluate_sell_three_factors_rsi_merged_into_deviation():
    """RSI > 80 should count as deviation extreme, not a 4th factor."""
    result = evaluate_sell_three_factors(
        valuation_overpriced=False, ma_breakdown=False, bias_extreme_high=False,
        rsi_value=85,
    )
    assert result["met_count"] == 1
    assert any("RSI" in f for f in result["factors"])
    assert len(result["factors"]) == 1


def test_evaluate_sell_three_factors_rsi_and_bias_together():
    result = evaluate_sell_three_factors(
        valuation_overpriced=False, ma_breakdown=False, bias_extreme_high=True,
        rsi_value=85,
    )
    assert result["met_count"] == 1
    assert any("且RSI" in f for f in result["factors"])
