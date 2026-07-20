import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils" / "reporter" / "sections"))

from technical_renderer import TechnicalRenderer


def _make_ctx(with_new_fields=True, mode="full"):
    ctx = {
        "stock_name": "测试股",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend": "多头",
                        "composite_score": 7.2,
                    } if not with_new_fields else {
                        "trend": "多头",
                        "composite_score": 7.2,
                        "trend_state": {
                            "primary_state": "上升趋势",
                            "stage": "主升期",
                            "action_hint": "持有跟踪",
                            "summary": "测试摘要",
                        },
                        "trend_health": {
                            "score": 72,
                            "grade": "健康",
                            "summary": "健康",
                            "components": {
                                "weekly_structure": {"score": 20, "max": 30, "evidence": "MA多头排列"},
                                "daily_ma_alignment": {"score": 22, "max": 25, "evidence": "站上MA20"},
                                "price_structure": {"score": 10, "max": 15, "evidence": "上升趋势"},
                                "volume_confirmation": {"score": 8, "max": 10, "evidence": "放量"},
                                "volatility_condition": {"score": 12, "max": 20, "evidence": "正常"},
                            },
                        },
                        "analysis_confidence": {"level": "高", "reasons": [], "limitations": []},
                        "weekly_background": {"trend": "单边上涨"},
                        "daily_structure": {
                            "ma20_direction": "向上", "ma60_direction": "向上",
                            "structure_type": "上升通道", "boll_state": "开口",
                        },
                        "structure_health": {
                            "state": "低点抬升", "is_healthy": True, "confidence": "中",
                            "evidence": ["最近两个回调低点抬升"],
                        },
                        "channel_status": {
                            "state": "上升通道", "confidence": "中", "position": "中部",
                            "breakout_status": "未突破",
                        },
                        "key_levels": {
                            "support_zone": {"zone_low": 90, "zone_high": 92, "strength": "强"},
                            "resistance_zone": {"zone_low": 110, "zone_high": 112, "strength": "中"},
                        },
                        "invalidation": {
                            "soft_warning": "跌破MA20",
                            "hard_invalid": "跌破MA60",
                            "hard_invalid_price": 90.0,
                            "current_distance_to_invalid": "5%",
                        },
                        "advisors": {
                            "macd": {"state": "多头延续", "meaning": "仅参考"},
                            "rsi": {"value": 55, "state": "正常", "meaning": "仅参考"},
                            "bias": {"state": "正常", "meaning": "仅参考"},
                            "boll": {"state": "开口", "meaning": "仅参考"},
                        },
                    },
                },
            },
        },
        "chart_paths": {},
        "technical_render_mode": mode,
    }
    return ctx


def _add_v22_projection_inputs(ctx, terminal_status="ready"):
    technical = ctx["stock_raw"]["technical"]
    indicators = technical["indicators"]
    resonance = indicators["_resonance"]
    indicators.update({"close": 100.0, "ma_20": 105.0, "ma_60": 110.0})
    resonance.update({
        "price_data_lineage": {"effective_adjustment": "qfq", "price_adjustment_applied": True},
        "structure_path": {
            "status": "ready", "as_of": "2026-07-19", "limitations": [], "pivot_sequence": [],
            "segments": [
                {"start_date": "2026-07-08", "end_date": "2026-07-10", "move": "up", "change_pct": 0.03, "end_kind": "high"},
                {"start_date": "2026-07-10", "end_date": "2026-07-15", "move": "down", "change_pct": -0.04, "end_kind": "low"},
            ],
        },
        "terminal_shock": {
            "status": terminal_status, "direction": "down", "facts": ["收盘接近日内低位", "量能比1.8×此前20日均量"],
        },
    })


def _action_line(output):
    return next(line for line in output.splitlines() if line.startswith("**当前行动**"))


def test_compact_rendering():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=True, mode="compact")
    output = renderer.render(ctx)
    assert "中期趋势提醒" in output
    assert "主升期" in output
    assert "72/100" in output
    assert "趋势失效条件" in output
    assert "局部趋势结构（辅助）" in output
    assert "通道/箱体（辅助）" in output
    # 评分子项以表格形式呈现
    assert "| 维度 | 得分 | 说明 |" in output
    # 谋士团以表格形式呈现
    assert "| 指标 | 状态 | 含义 |" in output
    assert "| MACD | 多头延续 | 仅参考 |" in output


def test_full_rendering():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=True, mode="full")
    output = renderer.render(ctx)
    assert "趋势背景" in output
    assert "日线结构" in output
    # 健康度评分以表格形式在 compact 基础输出中呈现，不再单独插入 "### 3. 健康度评分" 标题
    assert "趋势健康度" in output


def test_full_renderer_projects_path_shock_and_scenarios_without_raw_selection():
    ctx = _make_ctx(with_new_fields=True, mode="full")
    _add_v22_projection_inputs(ctx)

    output = TechnicalRenderer().render(ctx)

    assert "**结构演变**" in output
    assert "**末端异常K线**" in output
    assert "**情景阶梯**" in output
    assert output.count("| 阶段 | 变动 | 含义 |") == 1


def test_ordinary_terminal_bar_has_no_placeholder_and_compact_keeps_action():
    full_ctx = _make_ctx(with_new_fields=True, mode="full")
    compact_ctx = _make_ctx(with_new_fields=True, mode="compact")
    _add_v22_projection_inputs(full_ctx, terminal_status="ordinary")
    _add_v22_projection_inputs(compact_ctx, terminal_status="ordinary")

    full, compact = TechnicalRenderer().render(full_ctx), TechnicalRenderer().render(compact_ctx)

    assert "末端异常K线" not in full
    assert "| 阶段 | 变动 | 含义 |" not in compact
    assert "**结构演变**" in compact and "**情景阶梯**" in compact
    assert _action_line(full) == _action_line(compact)


def test_fallback_to_legacy():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=False, mode="compact")
    output = renderer.render(ctx)
    assert "技术面分析" in output
    assert "composite_score" in output or "综合评分" in output


def test_missing_support_resistance():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=True, mode="compact")
    ctx["stock_raw"]["technical"]["indicators"]["_resonance"]["key_levels"]["support_zone"] = None
    output = renderer.render(ctx)
    assert "暂无可靠支撑区" in output


def test_string_daily_structure_does_not_break_rendering():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=True, mode="compact")
    ctx["stock_raw"]["technical"]["indicators"]["_resonance"]["daily_structure"] = "日线沿20日均线上行。"

    output = renderer.render(ctx)

    assert "中期趋势提醒" in output
    assert "日线沿20日均线上行" in output


def test_unavailable_judgment_suppresses_legacy_precision_targets():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=True, mode="compact")
    tech = ctx["stock_raw"]["technical"]
    tech["price_target"] = {
        "status": "ready", "direction": "bullish", "conservative": 110.0,
        "base": 115.0, "aggressive": 120.0, "stop_loss": "97.0",
        "trigger_conditions": {"price": "旧触发条件"},
        "failure_conditions": ["旧失效条件"],
        "time_estimate": {"base": "10日"},
    }
    tech["indicators"]["_resonance"]["judgment"] = {
        "schema": "technical_judgment.v1",
        "trend": {"state": "unknown"},
        "target": {
            "direction": "neutral", "producer_status": "unavailable",
            "reason_code": "untrusted_or_malformed_judgment",
            "structure_confidence": "unavailable",
            "effective_confidence": "unavailable", "execution_state": "unavailable",
            "display_mode": "unavailable",
        },
        "action": {"state": "unavailable"},
    }

    output = renderer.render(ctx)

    assert "| 目标 | 价格 |" not in output
    assert "止损" not in output
    assert "旧触发条件" not in output
    assert "旧失效条件" not in output
    assert "时间预期" not in output


def test_contradictory_cached_judgment_cannot_render_precision_targets():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=True, mode="compact")
    tech = ctx["stock_raw"]["technical"]
    tech["price_target"] = {
        "status": "ready", "direction": "bullish", "conservative": 110.0,
        "base": 115.0, "aggressive": 120.0,
    }
    tech["indicators"]["_resonance"]["judgment"] = {
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

    output = renderer.render(ctx)

    assert "| 目标 | 价格 |" not in output
    assert "110.0" not in output
    assert "120.0" not in output


def test_renderer_resolves_judgment_inside_utils_package_context(tmp_path):
    script = """
from utils.reporter.sections.technical_renderer import TechnicalRenderer
ctx = {"stock_name": "测试股", "stock_raw": {"technical": {"price_target": {}, "indicators": {
    "_resonance": {
        "trend_state": {"primary_state": "上升趋势", "stage": "主升期"},
        "trend_health": {"score": 72, "grade": "健康"},
        "analysis_confidence": {"level": "高"},
    }
}}}}
assert "## 技术面分析" in TechnicalRenderer().render(ctx)
"""
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).parents[2] / "scripts"))
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env=env,
        capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr


def test_broken_regime_renders_controlling_and_counter_evidence_without_second_conclusion():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=True, mode="compact")
    tech = ctx["stock_raw"]["technical"]
    resonance = tech["indicators"]["_resonance"]
    resonance.update({
        "trend_state": {"primary_state": "下降趋势", "stage": "破坏期", "summary": "日线结构已经转弱"},
        "trend_health": {"score": 38, "grade": "破坏风险高"},
        "weekly_background": {"trend": "震荡", "ma_structure": "周线均线走平"},
        "daily_structure": {"price_vs_ma20": "跌破", "price_vs_ma60": "跌破", "ma20_direction": "向下"},
        "structure_health": {
            "is_healthy": True, "state": "低点抬升",
            "evidence": ["最近两个低点抬升", "回调低点逐步抬高，上升趋势结构健康"],
        },
        "bias_extreme": {"direction": "low", "level": "严重", "warning": "BIAS超卖"},
    })
    tech["price_target"] = {
        "status": "observe", "reason_code": "structure_observation", "direction": "bearish",
        "structure_confidence": "observation",
    }

    output = renderer.render(ctx)

    assert "中期趋势偏空，风险控制优先" in output
    assert "**主导证据**" in output
    assert "**反向线索**" in output
    assert "低点抬升，但尚不足以改变" in output
    assert "当前仅形成观察结构" in output
    assert "当前目标被阻断" not in output
    assert "structure_observation" not in output
    assert "**结论**" not in output
    assert "上升趋势结构健康" not in output


def test_invalid_regime_labels_triggered_conditions_and_dedupes_primary_evidence():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=True, mode="compact")
    tech = ctx["stock_raw"]["technical"]
    resonance = tech["indicators"]["_resonance"]
    resonance.update({
        "trend_state": {"primary_state": "下降趋势", "stage": "破坏期"},
        "trend_health": {"score": 34, "grade": "破坏风险高"},
        "invalidation": {
            "status": "broken", "is_invalidated": True,
            "soft_warning": "日线连续3日收盘跌破MA20",
            "hard_invalid": "周线收盘跌破MA10，或日线有效跌破MA60",
        },
    })
    tech["price_target"] = {
        "status": "invalid", "reason_code": "timeframe_direction_conflict", "direction": "bullish",
        "structure_confidence": "high",
    }

    output = renderer.render(ctx)

    assert "**已触发的破坏条件**" in output
    assert "- 已触发：日线连续3日收盘跌破MA20" in output
    assert output.count("周线收盘跌破MA10，或日线有效跌破MA60") == 1
    assert "- 失效：" not in output


def test_full_and_compact_share_judgment_semantics_and_do_not_duplicate_sell_assessment():
    renderer = TechnicalRenderer()
    compact_ctx = _make_ctx(with_new_fields=True, mode="compact")
    full_ctx = _make_ctx(with_new_fields=True, mode="full")
    for ctx in (compact_ctx, full_ctx):
        resonance = ctx["stock_raw"]["technical"]["indicators"]["_resonance"]
        resonance["weekly_background"] = {"trend": "单边上涨", "ma_structure": "周线多头"}
        resonance["daily_structure"].update({"price_vs_ma20": "站上", "price_vs_ma60": "站上"})
        resonance["price_data_lineage"] = {"effective_adjustment": "raw", "price_adjustment_applied": False}
        resonance["trigger_checks"] = {
            name: {"status": "pass", "detail": "已确认"}
            for name in ("price", "trend", "volume", "momentum")
        }
        resonance["sell_assessment"] = {"met_count": 2, "recommendation": "控制仓位", "factors": ["跌破均线", "估值偏高"]}
        ctx["stock_raw"]["technical"]["price_target"] = {
            "status": "ready", "reason_code": "target_ready", "direction": "bullish",
            "structure_confidence": "high", "targets": {"conservative": 110.0, "base": 115.0},
        }

    compact, full = renderer.render(compact_ctx), renderer.render(full_ctx)

    for text in ("趋势与确认条件一致，可继续跟踪", "**当前行动**：", "**价格目标分析**"):
        assert text in compact
        assert text in full
    assert compact.count("卖出三要素") <= 1
    assert full.count("卖出三要素") <= 1
    assert "控制仓位" not in compact
    assert "控制仓位" not in full
    assert "### 1. 趋势背景" in full
    assert "### 2. 日线结构" in full


def test_unavailable_market_and_raw_level_diagnostics_are_hidden():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=True, mode="compact")
    resonance = ctx["stock_raw"]["technical"]["indicators"]["_resonance"]
    resonance["market_resonance"] = {
        "state": "未知", "evidence": [], "missing": ["market index data missing"],
        "impact": "本次共振分析仅作占位。",
    }
    resonance["key_levels"]["support_zone"] = None
    resonance["key_levels"]["resistance_zone"] = None
    resonance["key_levels"]["diagnostics"] = {
        "reason": "支撑特定原因", "raw_valleys": 7, "raw_peaks": 9,
        "valid_support_touches": 1, "valid_resistance_touches": 1, "required_touches": 2,
    }

    output = renderer.render(ctx)

    assert "市场/板块共振" not in output
    assert "占位" not in output
    assert "原始极值点" not in output
    assert "支撑特定原因" not in output
    assert "7 个谷点" not in output


def test_valid_core_only_cache_uses_safe_minimal_projection():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=False, mode="compact")
    ctx["chart_paths"]["technical"] = "/tmp/core-only-technical.png"
    resonance = ctx["stock_raw"]["technical"]["indicators"]["_resonance"]
    resonance["judgment"] = {
        "schema": "technical_judgment.v1",
        "trend": {"state": "unknown", "label": "未知", "stage": "", "summary": "证据不足"},
        "target": {
            "direction": "neutral", "producer_status": "unavailable",
            "reason_code": "untrusted_or_malformed_judgment", "structure_confidence": "unavailable",
            "effective_confidence": "unavailable", "execution_state": "unavailable",
            "display_mode": "unavailable", "trigger_checks": {
                name: {"status": "unknown", "detail": "数据不足"}
                for name in ("price", "trend", "volume", "momentum")
            },
        },
        "action": {"state": "unavailable", "summary": "技术证据不足，无法形成可执行判断"},
        "limitations": [],
    }
    resonance["divergence_scan"] = {"type": "单一预警", "confidence": "轻度"}

    output = renderer.render(ctx)

    assert "技术证据不足，无法形成可执行判断" in output
    assert "证据不足，暂不展示目标价" in output
    assert "单一预警" not in output
    assert "谋士团" not in output
    assert "![测试股 技术面分析](/tmp/core-only-technical.png)" in output


def test_renderer_has_no_secondary_conclusion_or_priority_owner():
    assert not hasattr(TechnicalRenderer, "_build_conclusion")
    assert not hasattr(TechnicalRenderer, "_pick_priority_signal")
