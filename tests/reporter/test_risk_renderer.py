"""Tests for RiskRenderer."""

import pytest
from scripts.utils.reporter.sections import RiskRenderer


def test_required_keys():
    renderer = RiskRenderer()
    assert renderer.required_keys() == ["stock_name", "all_posts"]


def test_render_missing_keys():
    renderer = RiskRenderer()
    assert renderer.render({}) == ""
    # With stock_name but no all_posts (or empty list), risk_score_section still returns output
    assert renderer.render({"stock_name": "Test", "all_posts": []}) != ""


def test_render_basic():
    renderer = RiskRenderer()
    ctx = {
        "stock_name": "黑芝麻智能",
        "all_posts": [],
    }
    result = renderer.render(ctx)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "风险提示与关注要点" in result
    assert "预置风险库" in result
    assert "后续关注要点" in result
    assert "下周关注要点" not in result
    assert "风险库记录市值" in result


def test_render_unknown_stock():
    renderer = RiskRenderer()
    ctx = {
        "stock_name": "UnknownStock",
        "all_posts": [],
    }
    result = renderer.render(ctx)
    # Unknown stocks have no predefined risk text, but may still have risk_score_section output
    assert isinstance(result, str)


def test_renderer_passes_structured_risk_signals(monkeypatch):
    renderer = RiskRenderer()
    captured = {}

    def fake_risk_score_section(*args, **kwargs):
        captured["signals"] = kwargs.get("structured_risk_signals")
        captured["score_keywords"] = kwargs.get("score_llm_keyword_risks")
        return ""

    monkeypatch.setattr("scripts.utils.reporter.scoring_engine.risk_score_section", fake_risk_score_section)
    ctx = {
        "stock_name": "测试股",
        "all_posts": [],
        "structured_risk_signals": [{"name": "竞争格局恶化"}],
    }
    renderer.render(ctx)
    assert captured["signals"] == [{"name": "竞争格局恶化"}]


def test_renderer_passes_score_llm_keyword_risks(monkeypatch):
    renderer = RiskRenderer()
    captured = {}

    def fake_risk_score_section(*args, **kwargs):
        captured["score_keywords"] = kwargs.get("score_llm_keyword_risks")
        return ""

    monkeypatch.setattr("scripts.utils.reporter.scoring_engine.risk_score_section", fake_risk_score_section)
    ctx = {
        "stock_name": "测试股",
        "all_posts": [],
        "score_llm_keyword_risks": True,
    }
    renderer.render(ctx)
    assert captured["score_keywords"] is True


def test_renderer_default_context_safe(monkeypatch):
    renderer = RiskRenderer()
    captured = {}

    def fake_risk_score_section(*args, **kwargs):
        captured["signals"] = kwargs.get("structured_risk_signals")
        captured["score_keywords"] = kwargs.get("score_llm_keyword_risks")
        return ""

    monkeypatch.setattr("scripts.utils.reporter.scoring_engine.risk_score_section", fake_risk_score_section)
    ctx = {
        "stock_name": "测试股",
        "all_posts": [],
    }
    renderer.render(ctx)
    assert captured["signals"] == []
    assert captured["score_keywords"] is False


def test_renderer_end_to_end_severe_guardrail_note():
    renderer = RiskRenderer()
    ctx = {
        "stock_name": "测试股",
        "all_posts": [],
        "stock_raw": {
            "technical": {
                "indicators": {
                    "close": 10.0,
                    "ma_20": 15.0,
                    "avg_amount_yi": 2.0,
                    "_resonance": {
                        "trend_state": {"stage": "破坏期", "primary_state": "下降趋势"},
                        "trend_health": {"score": 26, "grade": "趋势失效"},
                    },
                }
            }
        },
    }
    result = renderer.render(ctx)
    assert "趋势破坏期，以观望或防守仓位为主，建议 0-5%" in result
    assert "仓位约束" in result
    assert "技术状态为 下降趋势 / 破坏期" in result
