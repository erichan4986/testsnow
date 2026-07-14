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


def test_compact_rendering():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=True, mode="compact")
    output = renderer.render(ctx)
    assert "中期趋势提醒" in output
    assert "主升期" in output
    assert "72/100" in output
    assert "趋势失效条件" in output
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
