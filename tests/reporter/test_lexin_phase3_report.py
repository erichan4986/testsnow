"""乐鑫科技 Phase 3 报告回归测试 — 验证 patch 文档中列出的 9 项修正。"""

import pytest
import numpy as np
import pandas as pd


def _make_exrights_df(days=130, exrights_dates=None):
    """生成带有多个模拟除权除息的日K数据。"""
    np.random.seed(42)
    dates = pd.date_range(end=pd.Timestamp("2026-06-08"), periods=days, freq="B")
    base = 200.0
    prices = base * np.exp(np.cumsum(np.random.normal(0.0003, 0.015, days)))

    if exrights_dates:
        for gap_date, ratio in exrights_dates:
            for i, d in enumerate(dates):
                if str(d.date()) == gap_date:
                    prices[i:] = prices[i:] / ratio
                    break

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


# --------------- 1. 多个除权断点检测 ---------------

def test_adjustment_warning_reports_latest_gap():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from price_adjustment_validator import validate_adjustment

    # 手动构造两个大跳变，确保超过 25% 阈值
    dates = pd.date_range("2025-01-01", periods=300, freq="B")
    close = np.ones(300) * 100.0
    # 选两个 business day 作为跳变日
    idx1 = 100  # 约 2025-05 中旬
    close[idx1] = 65.0  # 前一日 100 -> 当日 65，跳变 35%
    close[idx1+1:] = 65.0  # 之后保持复权后价格
    idx2 = 250  # 约 2026-01 中旬
    close[idx2] = 70.0  # 前一日 65 -> 当日 70，跳变 7.7% — 不够大
    # 改用更大跳变：idx2 处从 65 跳到 45
    close[idx2] = 45.0
    close[idx2+1:] = 45.0

    df = pd.DataFrame({
        "date": dates,
        "open": close * 1.01,
        "close": close,
        "high": close * 1.02,
        "low": close * 0.98,
        "volume": np.ones(300) * 10000,
    })

    result = validate_adjustment(df, adjustment="raw")

    gaps = result["price_gaps"]
    assert len(gaps["all_detected_gaps"]) >= 2, f"应检测到至少2个断点，实际 {len(gaps.get('all_detected_gaps', []))}"
    assert gaps["latest_gap"] is not None
    assert gaps["latest_gap"]["date"] == str(dates[idx2])
    assert result["latest_gap"]["date"] == str(dates[idx2])
    assert result["largest_gap"]["date"] == str(dates[idx1])

    # warning_message 应优先使用 latest_gap
    assert str(dates[idx2]) in result["warning_message"]
    assert str(dates[idx1]) not in result["warning_message"]


# --------------- 2. 中期失效参考必须包含价格 ---------------

def test_invalidation_contains_price_and_distance():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_state_machine import compute_invalidation

    inv = compute_invalidation(close=118.0, ma20=125.0, ma60=116.0, support_zone=None)
    assert "hard_invalid_price" in inv
    assert "hard_invalid_source" in inv
    assert "distance_pct" in inv
    assert "status" in inv
    assert "message" in inv
    assert inv["hard_invalid_source"] == "MA60"
    assert inv["status"] == "near_or_slightly_broken"  # 118 > 116 且 118 < 116*1.03=119.48


def test_invalidation_status_safe_when_far_above():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_state_machine import compute_invalidation

    inv = compute_invalidation(close=150.0, ma20=125.0, ma60=116.0, support_zone=None)
    assert inv["status"] == "safe"
    assert "位于MA60" in inv["message"]


def test_invalidation_status_broken_when_below():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_state_machine import compute_invalidation

    inv = compute_invalidation(close=100.0, ma20=125.0, ma60=116.0, support_zone=None)
    assert inv["status"] == "broken"
    assert inv["is_invalidated"] is True


# --------------- 3. BIAS 负偏离不得输出追高 ---------------

def test_negative_bias_advisor_no_chasing():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_analyzer import _build_advisors

    indicators = {
        "bias_5": -2.5,
        "bias_10": -1.0,
        "macd": -0.5,
        "rsi_14": 40,
        "close": 100,
        "boll_state": "正常",
        "boll_lower": 95,
        "boll_upper": 105,
    }
    adv = _build_advisors(indicators)
    assert "追高" not in adv["bias"]["meaning"]
    assert "偏高" not in adv["bias"]["meaning"]
    assert "负偏离" in adv["bias"]["state"]


def test_positive_bias_advisor_uses_chasing():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_analyzer import _build_advisors

    indicators = {
        "bias_5": 5.0,
        "bias_10": 3.0,
        "macd": 0.5,
        "rsi_14": 60,
        "close": 100,
        "boll_state": "正常",
        "boll_lower": 90,
        "boll_upper": 110,
    }
    adv = _build_advisors(indicators)
    assert "偏高" in adv["bias"]["state"]
    assert "追高" in adv["bias"]["meaning"]


# --------------- 4. BOLL advisor 输出当前状态 ---------------

def test_boll_advisor_shows_position_not_template():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_analyzer import _build_advisors

    indicators = {
        "close": 92,
        "boll_state": "开口",
        "boll_lower": 95,
        "boll_upper": 105,
        "macd": -0.5,
        "rsi_14": 40,
        "bias_5": 0,
    }
    adv = _build_advisors(indicators)
    assert "接近下轨" in adv["boll"]["meaning"]
    assert "开口=趋势加速" not in adv["boll"]["meaning"]
    assert "波动有所放大" in adv["boll"]["meaning"]


def test_boll_advisor_shows_upper_when_near_top():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_analyzer import _build_advisors

    indicators = {
        "close": 104,
        "boll_state": "缩口",
        "boll_lower": 90,
        "boll_upper": 105,
        "macd": 0.5,
        "rsi_14": 60,
        "bias_5": 0,
    }
    adv = _build_advisors(indicators)
    assert "接近上轨" in adv["boll"]["meaning"]
    assert "缩口=等待方向" not in adv["boll"]["meaning"]


# --------------- 5. 底部区域区分盘中跌破和收盘跌破 ---------------

def test_bottom_signal_distinguishes_intraday_and_close_break():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_structure import evaluate_bottoming_region

    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=30, freq="B"),
        "open": [100.0] * 30,
        "high": [102.0] * 30,
        "low": [98.0] * 29 + [90.0],  # 最后一天盘中低点 90，已跌破 swing_low 95
        "close": [100.0] * 29 + [96.0],  # 最后一天收盘 96，高于 swing_low 95
        "volume": [10000] * 30,
    })

    indicators = {"close": 96.0, "volume": 10000, "bias_5": -1.0, "ma_5": 99.0, "ma_10": 99.0}
    structure_health = {
        "swing_lows": [
            {"date": "2026-01-15", "price": 95.0},
            {"date": "2026-01-20", "price": 98.0},
        ]
    }

    bottom = evaluate_bottoming_region(
        df, None, indicators,
        trend_state={"primary_state": "震荡"},
        structure_health=structure_health,
    )

    status = bottom.get("swing_low_status")
    assert status is not None
    assert status["close_broke"] is False
    assert status["intraday_broke"] is True
    assert any("收盘未有效跌破" in ev for ev in bottom["evidence"])


# --------------- 6. 趋势状态：震荡转弱而非下降趋势 ---------------

def test_trend_state_shakes_weak_not_down_when_ma60_up():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_state_machine import classify_trend_state

    result = classify_trend_state(
        weekly_trend="震荡",
        daily_structure={
            "price_vs_ma20": "跌破",
            "price_vs_ma60": "站上",
            "ma20_direction": "向下",
            "ma60_direction": "向上",
        },
        indicators={"boll_state": "正常", "rsi_14": 40, "close": 118, "ma_20": 125, "ma_60": 116},
        divergence=None,
    )
    assert result["primary_state"] == "震荡转弱"
    assert "临界" in result["stage"]
    assert "MA60" in result["summary"] or "收回" in result["summary"]


def test_trend_state_full_down_when_ma60_down():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from technical_state_machine import classify_trend_state

    result = classify_trend_state(
        weekly_trend="单边下跌",
        daily_structure={
            "price_vs_ma20": "跌破",
            "price_vs_ma60": "跌破",
            "ma20_direction": "向下",
            "ma60_direction": "向下",
        },
        indicators={"boll_state": "开口", "rsi_14": 30, "close": 100, "ma_20": 110, "ma_60": 120},
        divergence=None,
    )
    assert result["primary_state"] == "下降趋势"


# --------------- 7. 结论模板不得包含无关内容 ---------------

def test_conclusion_no_irrelevant_overbought_template():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from sections.technical_renderer import TechnicalRenderer

    ctx = {
        "stock_name": "测试",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend_state": {"primary_state": "震荡转弱", "stage": "临界破坏观察期"},
                        "trend_health": {"score": 33, "grade": "破坏风险高"},
                        "invalidation": {"hard_invalid_price": 115.79, "distance_pct": 3.6},
                        "key_levels": {},
                        "advisors": {
                            "macd": {"state": "空头延续", "meaning": "仅作趋势确认"},
                            "rsi": {"state": "正常", "meaning": "强趋势中不单独构成卖出信号"},
                            "bias": {"state": "正常", "meaning": "价格与均线偏离适中"},
                            "boll": {"state": "正常", "meaning": "中轨附近，波动正常"},
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
    assert "RSI 超买" not in output, f"结论不应包含 RSI 超买 模板残留"
    assert "BIAS 偏高" not in output, f"结论不应包含 BIAS 偏高 模板残留"
    assert "震荡转弱" in output


# --------------- 8. Renderer 中期失效参考必须包含价格 ---------------

def test_renderer_invalidation_shows_price_and_basis():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from sections.technical_renderer import TechnicalRenderer

    ctx = {
        "stock_name": "测试",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend_state": {"primary_state": "震荡", "stage": "观察"},
                        "trend_health": {"score": 50, "grade": "一般"},
                        "invalidation": {
                            "hard_invalid_price": 115.65,
                            "hard_invalid_source": "MA60",
                            "distance_pct": -0.55,
                            "status": "near_or_slightly_broken",
                            "message": "当前收盘价已接近/略低于日线MA60",
                            "current_distance_to_invalid": "-0.55%",
                        },
                        "key_levels": {},
                        "advisors": {
                            "macd": {"state": "空头延续", "meaning": "仅作趋势确认"},
                            "rsi": {"state": "正常", "meaning": "强趋势中不单独构成卖出信号"},
                            "bias": {"state": "正常", "meaning": "价格与均线偏离适中"},
                            "boll": {"state": "正常", "meaning": "中轨附近，波动正常"},
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
    assert "MA60 约 115.65" in output, f"应显示具体价格和基准"
    assert "-0.55%" in output
    assert "当前收盘价已接近" in output
    assert "2.2%" not in output, f"不应只输出无意义的百分比"


# --------------- 9. validate_adjustment 向前兼容 ---------------

def test_detect_price_gaps_backward_compatible():
    import sys as _sys
    from pathlib import Path
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter"))
    from price_adjustment_validator import detect_price_gaps

    df = _make_exrights_df(days=50, exrights_dates=[("2026-05-20", 1.3)])
    result = detect_price_gaps(df)
    assert "possible_exrights_gap" in result
    assert "max_gap_pct" in result
    assert "gap_date" in result
    assert "gap_details" in result
    assert "latest_gap" in result
    assert "largest_gap" in result
    assert "all_detected_gaps" in result
