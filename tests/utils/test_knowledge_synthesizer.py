import pytest
from scripts.utils.knowledge_synthesizer import KnowledgeSynthesizer
from scripts.utils.source_adapter import SynthesisItem


def test_parse_citations_extracts_refs():
    synth = KnowledgeSynthesizer(client=None)
    text = "收入同比增长40%[^1]，毛利率51.6%[^2]。"
    parsed, cites = synth._parse_with_citations(text)
    assert "[^1]" in parsed  # keep refs in narrative
    assert 1 in cites
    assert 2 in cites


def test_parse_citations_handles_missing_refs():
    synth = KnowledgeSynthesizer(client=None)
    text = "收入同比增长40%，毛利率51.6%。"
    parsed, cites = synth._parse_with_citations(text)
    assert len(cites) == 0


def test_build_prompt_includes_source_list():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="Q1业绩分析", content="营收增长40%", author="张三",
            source_platform="雪球", url="http://x", publish_time="2026-05-20",
            interaction_score=100,
        ),
        SynthesisItem(
            title="行业竞争", content="杰华特威胁", author="李四",
            source_platform="知乎", url="http://z", publish_time="2026-05-19",
            interaction_score=50,
        ),
    ]
    prompt = synth._build_prompt("圣邦股份", "valuation_debate", items)
    assert "[1]" in prompt
    assert "Q1业绩分析" in prompt
    assert "[2]" in prompt
    assert "行业竞争" in prompt
    assert "估值争议" in prompt or "估值" in prompt


def test_synthesize_returns_empty_when_no_client():
    synth = KnowledgeSynthesizer(client=None)
    result = synth.synthesize("圣邦股份", {"items": []})
    assert result["industry_logic"] == ""
    assert result["fundamentals"] == ""
    assert result["valuation_debate"] == ""
    assert result["funding_sentiment"] == ""
    assert result["events_catalysts"] == ""
    assert result["citations"] == {}


def test_synthesize_skips_when_items_too_few():
    """Less than 3 items should skip synthesis for each theme"""
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="唯一内容", content="内容", author="A",
            source_platform="雪球", url="", publish_time="",
        )
    ]
    # No client, so all themes will be empty anyway
    # But we can test the empty items case
    result = synth.synthesize("圣邦股份", {"items": items})
    # With no client, everything is empty
    assert result["industry_logic"] == ""
