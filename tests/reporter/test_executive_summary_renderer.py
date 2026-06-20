"""Tests for ExecutiveSummaryRenderer."""

import pytest
from scripts.utils.reporter.sections import ExecutiveSummaryRenderer


def test_required_keys():
    renderer = ExecutiveSummaryRenderer()
    assert renderer.required_keys() == ["stock_name", "synthesis"]


def test_render_missing_keys_returns_empty():
    renderer = ExecutiveSummaryRenderer()
    assert renderer.render({}) == ""
    assert renderer.render({"stock_name": "Test"}) == ""


def test_render_basic():
    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "valuation_debate": "估值合理，增长空间大。",
            "fundamentals": "基本面稳健，业绩持续增长。",
        },
    }
    result = renderer.render(ctx)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "## 执行摘要" in result
    assert "核心投资论点" in result


def test_render_with_pillar():
    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "valuation_debate": "估值合理。",
            "fundamentals": "基本面稳健。",
        },
        "pillar": {
            "valuation": 7.0,
            "technical": 6.5,
            "sentiment": 5.0,
            "fundamental": 8.0,
            "fundflow": 4.0,
        },
    }
    result = renderer.render(ctx)
    assert "综合评分" in result


def test_extract_thesis_points_sanitizes_status_markers(monkeypatch):
    """Non-numeric citation markers must be stripped before LLM extraction."""
    captured = []

    def spy_llm_extract_thesis(text):
        captured.append(text)
        return {"bullish": [{"text": "增长", "stars": 3}], "bearish": [], "conclusion": ""}

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._llm_extract_thesis",
        spy_llm_extract_thesis,
    )

    from scripts.utils.reporter.sections.executive_summary_renderer import (
        _extract_thesis_points,
    )

    text = "收入增长[^1]，社区讨论[^supported]，风险[^needs_review]。"
    _extract_thesis_points(text, "bullish")

    assert len(captured) == 1
    assert "[^supported]" not in captured[0]
    assert "[^needs_review]" not in captured[0]
    assert "[^1]" in captured[0]


def test_llm_extract_thesis_prompt_excludes_unverified_for_bullish(monkeypatch):
    """The LLM prompt must instruct that only verified high-credit facts are bullish confirmed."""
    import os

    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key-for-test")

    captured = []

    class FakeChoice:
        def __init__(self):
            self.message = type("M", (), {"content": '{"bullish": [], "bearish": [], "conclusion": ""}'})()

    class FakeCompletions:
        def create(self, **kwargs):
            captured.append(kwargs)
            return type("R", (), {"choices": [FakeChoice()]})()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", FakeClient)

    from scripts.utils.reporter.sections.executive_summary_renderer import _llm_extract_thesis

    _llm_extract_thesis("some text")

    assert len(captured) == 1
    prompt = captured[0]["messages"][1]["content"]
    assert "verified" in prompt or "已验证" in prompt
    assert "supported" in prompt or "部分支持" in prompt
    assert "unverified" in prompt or "未验证" in prompt
    assert "needs_review" in prompt or "需复核" in prompt
    assert "看多" in prompt


def test_render_marks_supported_claim_bullish_point_as_non_official(monkeypatch):
    """Supported claim content must not render as an unqualified bullish fact."""
    def fake_llm_extract_thesis(text):
        return {
            "bullish": [
                {"text": "2026年一季报净利润同比增长106.96%，业绩弹性释放", "stars": 3},
            ],
            "bearish": [],
            "conclusion": "",
        }

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._llm_extract_thesis",
        fake_llm_extract_thesis,
    )

    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "圣邦股份",
        "synthesis": {
            "valuation_debate": "估值争议。",
            "fundamentals": "该线索获得部分支持，但仍非官方确认。",
        },
        "claim_verification_summary": {
            "supported_claims": [
                {
                    "claim_text": "圣邦 2026 年一季报净利润 1.24 亿元，同比增长 106.96%",
                    "confidence": 54,
                }
            ]
        },
    }

    result = renderer.render(ctx)

    assert "2026年一季报净利润同比增长106.96%" in result
    assert "部分支持，非官方确认" in result


def test_render_prefers_synthesis_display(monkeypatch):
    captured = []

    def spy_extract(text, direction, claim_verification_summary=None):
        captured.append(text)
        return []

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._extract_thesis_points",
        spy_extract,
    )
    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._extract_conclusion",
        lambda stock_name, text: "",
    )

    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "valuation_debate": "baseline 估值。",
            "fundamentals": "baseline 基本面。",
        },
        "synthesis_display": {
            "valuation_debate": "enhanced 年报全文 估值。",
            "fundamentals": "enhanced 年报全文 基本面。",
        },
    }
    renderer.render(ctx)

    assert captured
    assert any("enhanced 年报全文" in t for t in captured)
    assert all("baseline" not in t for t in captured)


def test_render_falls_back_to_synthesis_when_no_display(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._extract_thesis_points",
        lambda text, direction, claim_verification_summary=None: captured.append(text) or [],
    )
    monkeypatch.setattr(
        "scripts.utils.reporter.sections.executive_summary_renderer._extract_conclusion",
        lambda stock_name, text: "",
    )

    renderer = ExecutiveSummaryRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "valuation_debate": "baseline 估值。",
            "fundamentals": "baseline 基本面。",
        },
    }
    renderer.render(ctx)

    assert any("baseline" in t for t in captured)
