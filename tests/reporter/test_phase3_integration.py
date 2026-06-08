from scripts.utils.reporter.sections.technical_renderer import TechnicalRenderer


def test_renderer_shows_structure_health():
    """renderer 展示趋势结构"""
    ctx = {
        "stock_name": "测试",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend_state": {"stage": "主升期", "primary_state": "上升趋势"},
                        "trend_health": {"score": 80, "grade": "健康"},
                        "structure_health": {
                            "state": "低点抬升",
                            "confidence": "高",
                            "evidence": ["低点抬高"],
                            "missing": [],
                            "action_hint": "结构健康",
                        },
                        "invalidation": {},
                        "key_levels": {},
                    }
                }
            }
        },
        "technical_render_mode": "compact",
    }
    renderer = TechnicalRenderer()
    md = renderer.render(ctx)
    assert "低点抬升" in md
    assert "结构健康" in md


def test_renderer_no_bottom_confirmed():
    """renderer 不得输出底部确认"""
    ctx = {
        "stock_name": "测试",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend_state": {"stage": "盘整期"},
                        "trend_health": {"score": 50},
                        "bottom_signal": {
                            "state": "bottom_strengthened",
                            "evidence": ["信号增强"],
                            "action_hint": "底部区域进一步确认",
                        },
                        "invalidation": {},
                        "key_levels": {},
                    }
                }
            }
        },
        "technical_render_mode": "compact",
    }
    renderer = TechnicalRenderer()
    md = renderer.render(ctx)
    assert "底部确认" not in md
    assert "底部区域进一步确认" in md or "底部构筑" in md


def test_renderer_no_strategy_judgment():
    """renderer 不做策略判断"""
    ctx = {
        "stock_name": "测试",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend_state": {"stage": "盘整期"},
                        "trend_health": {"score": 50},
                        "dart_strategy": {
                            "state": "active",
                            "steps": [
                                {"level": 1, "condition": "站上MA5", "action": "进入观察清单"}
                            ],
                        },
                        "invalidation": {},
                        "key_levels": {},
                    }
                }
            }
        },
        "technical_render_mode": "compact",
    }
    renderer = TechnicalRenderer()
    md = renderer.render(ctx)
    assert "买入" not in md
    assert "建仓" not in md
    assert "观察清单" in md


def test_renderer_missing_phase3_fields_no_error():
    """缺少 Phase 3 字段时不应抛异常"""
    ctx = {
        "stock_name": "测试",
        "stock_raw": {
            "technical": {
                "indicators": {
                    "_resonance": {
                        "trend_state": {"stage": "主升期", "primary_state": "上升趋势"},
                        "trend_health": {"score": 80, "grade": "健康"},
                        "invalidation": {},
                        "key_levels": {},
                    }
                }
            }
        },
        "technical_render_mode": "compact",
    }
    renderer = TechnicalRenderer()
    md = renderer.render(ctx)
    assert "技术面分析：中期趋势提醒" in md
    assert "趋势结构" not in md
    assert "底部区域" not in md
    assert "市场共振" not in md


def test_analyzer_returns_new_fields():
    """主入口返回包含 Phase 3 新字段"""
    import pandas as pd
    import numpy as np
    from scripts.utils.reporter.technical_analyzer import advanced_medium_term_resonance

    df_daily = pd.DataFrame({
        "date": pd.date_range("2026-04-01", periods=60, freq="B"),
        "open": np.ones(60) * 200,
        "high": np.ones(60) * 205,
        "low": np.ones(60) * 195,
        "close": np.ones(60) * 200,
        "volume": np.ones(60) * 10000,
    })
    df_weekly = pd.DataFrame({
        "date": pd.date_range("2026-04-01", periods=12, freq="W-FRI"),
        "open": np.ones(12) * 200,
        "high": np.ones(12) * 205,
        "low": np.ones(12) * 195,
        "close": np.ones(12) * 200,
        "volume": np.ones(12) * 10000,
    })
    result = advanced_medium_term_resonance(
        df_daily=df_daily,
        df_weekly=df_weekly,
        quote={"code": "000001"},
    )
    resonance = (
        result.get("_resonance")
        or result.get("resonance")
        or result.get("indicators", {}).get("_resonance")
        or {}
    )
    assert "structure_health" in resonance
    assert "channel_status" in resonance
    assert "bottom_signal" in resonance
    assert "market_resonance" in resonance
