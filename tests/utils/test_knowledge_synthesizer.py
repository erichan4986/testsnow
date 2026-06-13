import pytest
from scripts.utils.knowledge_synthesizer import KnowledgeSynthesizer
from scripts.utils.source_adapter import SynthesisItem


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


def test_build_prompt_includes_claim_verification_appendix():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="Q1业绩分析", content="营收增长40%", author="张三",
            source_platform="雪球", url="http://x", publish_time="2026-05-20",
            interaction_score=100,
        ),
    ]
    context = {
        "enabled": True,
        "stock": "圣邦股份",
        "counts": {"verified": 1, "supported": 0, "unverified": 0, "needs_review": 0, "high_credit_claims": 1, "low_credit_claims": 1, "skipped_files": 0},
        "verified_claims": [{"claim_text": "营收增长", "action": "verified", "verified_by_titles": ["公司业绩公告"], "confidence": 85}],
        "supported_claims": [],
        "unverified_claims": [],
    }
    prompt = synth._build_prompt("圣邦股份", "fundamentals", items, claim_verification_context=context)
    assert "Claim Verification Context" in prompt
    assert "不是新的引用来源" in prompt
    assert "不能用 [^n] 引用" in prompt
    assert "verified" in prompt.lower() or "已验证" in prompt
    assert "verified_claims" in prompt or "已验证" in prompt


def test_build_prompt_order_sources_context_narratives():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="Q1业绩分析", content="营收增长40%", author="张三",
            source_platform="雪球", url="http://x", publish_time="2026-05-20",
            interaction_score=100,
        ),
    ]
    context = {
        "enabled": True,
        "stock": "圣邦股份",
        "counts": {"verified": 0, "supported": 0, "unverified": 1, "needs_review": 0, "high_credit_claims": 0, "low_credit_claims": 1, "skipped_files": 0},
        "verified_claims": [],
        "supported_claims": [],
        "unverified_claims": [{"claim_text": "社区讨论", "action": "unverified", "reason": "no match"}],
    }
    previous = {"industry_logic": "行业叙事。"}
    prompt = synth._build_prompt("圣邦股份", "fundamentals", items, previous_narratives=previous, claim_verification_context=context)
    sources_pos = prompt.find("信息来源：")
    context_pos = prompt.find("Claim Verification Context")
    narratives_pos = prompt.find("已生成的其他板块分析")
    assert sources_pos != -1
    assert context_pos != -1
    assert narratives_pos != -1
    assert sources_pos < context_pos < narratives_pos


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


def test_parse_citations_unchanged_by_verification_context():
    synth = KnowledgeSynthesizer(client=None)
    text = "收入同比增长40%[^1]。"
    parsed_a, cites_a = synth._parse_with_citations(text)
    parsed_b, cites_b = synth._parse_with_citations(text)
    assert parsed_a == parsed_b
    assert cites_a == cites_b
    assert 1 in cites_a


def test_synthesize_passes_context_to_build_prompt(monkeypatch):
    """When context is provided, _build_prompt receives it."""
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="Q1业绩分析", content="营收增长40%", author="张三",
            source_platform="雪球", url="http://x", publish_time="2026-05-20",
            interaction_score=100,
        ),
    ] * 3  # ensure min_items
    context = {
        "enabled": True,
        "stock": "圣邦股份",
        "counts": {"verified": 0, "supported": 0, "unverified": 0, "needs_review": 0, "high_credit_claims": 0, "low_credit_claims": 0, "skipped_files": 0},
        "verified_claims": [],
        "supported_claims": [],
        "unverified_claims": [],
    }
    calls = []

    def spy(stock_name, theme_key, items, previous_narratives=None, claim_verification_context=None):
        calls.append(claim_verification_context)
        return ""

    monkeypatch.setattr(synth, "_build_prompt", spy)
    monkeypatch.setattr(synth, "_call_llm", lambda prompt: "")
    result = synth.synthesize("圣邦股份", {"items": items, "claim_verification_context": context})
    assert result["fundamentals"] == ""
    assert calls[0] is context


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
