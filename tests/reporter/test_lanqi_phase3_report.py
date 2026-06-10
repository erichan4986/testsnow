"""澜起科技 Phase 3 报告回归测试 — 验证 patch 文档中的修正。"""

import pytest
import numpy as np
import pandas as pd


def _make_channel_df(lower=62.0, upper=76.0, close=63.2, days=40):
    """生成一个水平箱体数据，close 靠近下轨或上轨。"""
    np.random.seed(42)
    dates = pd.date_range(end=pd.Timestamp("2026-06-08"), periods=days, freq="B")
    closes = np.full(days, close)
    opens = closes * 0.998
    # high 在 upper 附近小幅波动，low 在 lower 附近小幅波动
    highs = np.full(days, upper) + np.random.normal(0, 0.2, days)
    lows = np.full(days, lower) + np.random.normal(0, 0.2, days)
    highs = np.maximum(highs, np.maximum(opens, closes) * 1.005)
    lows = np.minimum(lows, np.minimum(opens, closes) * 0.995)
    df = pd.DataFrame({
        "date": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.random.poisson(50000, days),
    })
    return df


# --------------- 1. 通道位置使用距离比例 -------------

def test_channel_position_near_lower_when_close_near_lower():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_structure import detect_channel_or_box_structure

    df = _make_channel_df(lower=62.0, upper=76.0, close=63.2, days=40)
    ch = detect_channel_or_box_structure(df)
    assert ch["state"] != "无明显通道"
    assert ch["position"] == "接近下轨", f"close={df['close'].iloc[-1]}，期望接近下轨，实际 {ch['position']}"


def test_channel_position_near_upper_when_close_near_upper():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_structure import detect_channel_or_box_structure

    df = _make_channel_df(lower=62.0, upper=76.0, close=75.5, days=40)
    ch = detect_channel_or_box_structure(df)
    assert ch["state"] != "无明显通道"
    assert ch["position"] == "接近上轨", f"close={df['close'].iloc[-1]}，期望接近上轨，实际 {ch['position']}"


# --------------- 2. BOLL advisor 距离化识别 -------------

def test_boll_advisor_near_lower_with_distance_logic():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_analyzer import _build_advisors

    indicators = {
        "close": 63.2,
        "boll_state": "开口",
        "boll_lower": 62.5,
        "boll_upper": 76.5,
        "macd": 0.5,
        "macd_hist": -0.1,
        "rsi_14": 55,
        "bias_5": 0,
    }
    adv = _build_advisors(indicators)
    assert "接近下轨" in adv["boll"]["meaning"], f"BOLL advisor 未识别接近下轨：{adv['boll']}"


def test_boll_advisor_near_upper_with_distance_logic():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_analyzer import _build_advisors

    indicators = {
        "close": 76.0,
        "boll_state": "缩口",
        "boll_lower": 62.5,
        "boll_upper": 76.5,
        "macd": 0.5,
        "macd_hist": 0.1,
        "rsi_14": 60,
        "bias_5": 0,
    }
    adv = _build_advisors(indicators)
    assert "接近上轨" in adv["boll"]["meaning"], f"BOLL advisor 未识别接近上轨：{adv['boll']}"


# --------------- 3. MACD advisor：DIF>0 但 hist<0 应输出多头动能衰减 -------------

def test_macd_advisor_bull_momentum_decay_when_dif_positive_hist_negative():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_analyzer import _build_advisors

    indicators = {
        "close": 63.2,
        "boll_state": "正常",
        "boll_lower": 60,
        "boll_upper": 70,
        "macd": 0.3,
        "macd_hist": -0.05,
        "rsi_14": 55,
        "bias_5": 0,
    }
    adv = _build_advisors(indicators)
    assert adv["macd"]["state"] == "多头动能衰减", f"MACD advisor 状态错误：{adv['macd']}"


def test_macd_advisor_bull_continue_when_dif_and_hist_positive():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_analyzer import _build_advisors

    indicators = {
        "close": 63.2,
        "boll_state": "正常",
        "boll_lower": 60,
        "boll_upper": 70,
        "macd": 0.3,
        "macd_hist": 0.1,
        "rsi_14": 55,
        "bias_5": 0,
    }
    adv = _build_advisors(indicators)
    assert adv["macd"]["state"] == "多头延续", f"MACD advisor 状态错误：{adv['macd']}"


# --------------- 4. Renderer 在支撑/压力区缺失时补充 MA 观察位 -------------

def test_renderer_shows_ma_levels_when_sr_zones_empty():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from sections.technical_renderer import TechnicalRenderer

    ctx = {
        "stock_name": "澜起科技",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "close": 63.2,
                    "ma_5": 64.1,
                    "ma_10": 65.0,
                    "ma_20": 66.5,
                    "ma_60": 62.0,
                    "_resonance": {
                        "trend_state": {"primary_state": "震荡转弱", "stage": "回撤观察期"},
                        "trend_health": {"score": 55, "grade": "转弱观察"},
                        "invalidation": {
                            "hard_invalid_price": 62.0,
                            "hard_invalid_source": "MA60",
                            "distance_pct": 1.94,
                            "status": "safe",
                            "message": "当前收盘价位于MA60（62.00）上方，距离约 1.94%。",
                            "current_distance_to_invalid": "1.94%",
                        },
                        "key_levels": {"support_zone": None, "resistance_zone": None},
                        "advisors": {
                            "macd": {"state": "多头动能衰减", "meaning": "仅作趋势确认"},
                            "rsi": {"state": "正常", "meaning": "强趋势中不单独构成卖出信号"},
                            "bias": {"state": "正常", "meaning": "价格与均线偏离适中"},
                            "boll": {"state": "开口", "meaning": "接近下轨，波动有所放大"},
                        },
                        "bottom_signal": {"state": "none"},
                        "divergence_scan": None,
                    },
                },
            },
        },
        "technical_render_mode": "compact",
    }
    renderer = TechnicalRenderer()
    output = renderer.render(ctx)
    assert "MA5：约 64.10" in output or "MA5：约 64.1" in output, f"渲染结果缺少 MA5 观察位：\n{output}"
    assert "MA60：约 62.00" in output or "MA60：约 62.0" in output, f"渲染结果缺少 MA60 观察位：\n{output}"


# --------------- 5. 趋势健康度：MA20向上但价格跌破MA20 应给出一致 evidence -------------

def test_trend_health_ma20_up_price_below_evidence():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_state_machine import compute_trend_health

    th = compute_trend_health(
        weekly_trend="震荡",
        daily_structure={
            "price_vs_ma20": "跌破",
            "price_vs_ma60": "站上",
            "ma20_direction": "向上",
            "ma60_direction": "向上",
            "structure_type": "无明显结构",
        },
        indicators={"boll_state": "正常", "rsi_14": 50, "close": 63.2, "ma_20": 66.5, "ma_60": 62.0},
    )
    comp = th["components"]["daily_ma_alignment"]
    assert comp["score"] == 12, f"期望 12/25，实际 {comp}"
    assert "MA20向上，但价格跌破MA20，短线转弱" in comp["evidence"], f"evidence 不匹配：{comp}"
    assert th["grade"] != "破坏风险高", f"MA60 仍向上时不应评级为破坏风险高：{th['grade']}"


# --------------- 6. 中期失效包含价格、距离、状态 -------------

def test_invalidation_near_when_price_within_3pct_above_ma60():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_state_machine import compute_invalidation

    inv = compute_invalidation(close=63.2, ma20=66.5, ma60=62.0, support_zone=None)
    assert inv["hard_invalid_price"] == 62.0
    assert inv["hard_invalid_source"] == "MA60"
    # 63.2 位于 62.0 上方，但 63.2 < 62.0*1.03=63.86，属于接近/略低于区间
    assert inv["status"] == "near_or_slightly_broken", f"期望 near_or_slightly_broken，实际 {inv['status']}"
    assert "62.00" in inv["message"]
    assert inv["distance_pct"] == pytest.approx(1.94, abs=0.01)


def test_invalidation_safe_when_price_far_above_ma60():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_state_machine import compute_invalidation

    inv = compute_invalidation(close=70.0, ma20=66.5, ma60=62.0, support_zone=None)
    assert inv["status"] == "safe"
    assert inv["distance_pct"] == pytest.approx(12.90, abs=0.01)


# --------------- 7. 趋势状态：高位回撤但MA60仍向上 → 震荡转弱/回撤观察期 -------------

def test_trend_state_pullback_when_ma20_breaks_but_ma60_up():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_state_machine import classify_trend_state

    result = classify_trend_state(
        weekly_trend="震荡",
        daily_structure={
            "price_vs_ma20": "跌破",
            "price_vs_ma60": "站上",
            "ma20_direction": "向上",
            "ma60_direction": "向上",
        },
        indicators={"boll_state": "正常", "rsi_14": 50, "close": 63.2, "ma_20": 66.5, "ma_60": 62.0},
        divergence=None,
    )
    assert result["primary_state"] == "震荡转弱"
    assert "回撤" in result["stage"]
    assert "MA60仍向上" in result["summary"]


# --------------- 8. Renderer 中期失效参考必须包含价格和距离 -------------

def test_renderer_invalidation_shows_price_distance_and_status():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from sections.technical_renderer import TechnicalRenderer

    ctx = {
        "stock_name": "澜起科技",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "close": 63.2,
                    "_resonance": {
                        "trend_state": {"primary_state": "震荡转弱", "stage": "回撤观察期"},
                        "trend_health": {"score": 55, "grade": "转弱观察"},
                        "invalidation": {
                            "hard_invalid_price": 62.0,
                            "hard_invalid_source": "MA60",
                            "distance_pct": 1.94,
                            "status": "safe",
                            "message": "当前收盘价位于MA60（62.00）上方，距离约 1.94%。",
                            "current_distance_to_invalid": "1.94%",
                        },
                        "key_levels": {"support_zone": None, "resistance_zone": None},
                        "advisors": {
                            "macd": {"state": "多头动能衰减", "meaning": "仅作趋势确认"},
                            "rsi": {"state": "正常", "meaning": "强趋势中不单独构成卖出信号"},
                            "bias": {"state": "正常", "meaning": "价格与均线偏离适中"},
                            "boll": {"state": "开口", "meaning": "接近下轨，波动有所放大"},
                        },
                        "bottom_signal": {"state": "none"},
                        "divergence_scan": None,
                    },
                },
            },
        },
        "technical_render_mode": "compact",
    }
    renderer = TechnicalRenderer()
    output = renderer.render(ctx)
    assert "MA60 约 62.00" in output or "MA60 约 62.0" in output, f"应显示 MA60 价格：\n{output}"
    assert "1.94%" in output, f"应显示距离百分比：\n{output}"
