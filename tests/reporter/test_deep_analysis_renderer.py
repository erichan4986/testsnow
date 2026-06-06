"""Tests for DeepAnalysisRenderer."""

import pytest
from scripts.utils.reporter.sections import DeepAnalysisRenderer


def test_required_keys():
    renderer = DeepAnalysisRenderer()
    assert renderer.required_keys() == ["stock_name", "synthesis"]


def test_render_missing_keys():
    renderer = DeepAnalysisRenderer()
    assert renderer.render({}) == ""
    assert renderer.render({"stock_name": "Test"}) == ""


def test_render_basic():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "行业逻辑内容。",
            "fundamentals": "基本面内容。",
            "valuation_debate": "估值辩论内容。",
            "funding_sentiment": "资金面内容。",
            "events_catalysts": "催化剂内容。",
            "citations": {},
        },
    }
    result = renderer.render(ctx)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "## 四、深度分析" in result
    assert "4.1 产业逻辑与竞争格局" in result


def test_render_with_core_facts():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "行业逻辑。",
            "citations": {1: {"source": "雪球", "author": "张三", "title": "测试"}},
        },
        "core_facts": [
            {"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高"},
        ],
    }
    result = renderer.render(ctx)
    assert "## 三、核心事实基座" in result
    assert "营收增长" in result
