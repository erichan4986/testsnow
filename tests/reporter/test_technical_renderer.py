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


def test_full_rendering():
    renderer = TechnicalRenderer()
    ctx = _make_ctx(with_new_fields=True, mode="full")
    output = renderer.render(ctx)
    assert "趋势背景" in output
    assert "日线结构" in output
    assert "健康度评分" in output


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
