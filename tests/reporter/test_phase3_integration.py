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
