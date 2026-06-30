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


def test_build_prompt_includes_credit_usage_rules_before_sources():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="Q1业绩分析", content="营收增长40%", author="张三",
            source_platform="雪球", url="http://x", publish_time="2026-05-20",
            interaction_score=100,
        ),
    ]
    prompt = synth._build_prompt("圣邦股份", "valuation_debate", items)
    rules_pos = prompt.find("证据信用与写法规则")
    sources_pos = prompt.find("信息来源：")
    assert rules_pos != -1
    assert sources_pos != -1
    assert rules_pos < sources_pos
    assert "不得写成公司确认" in prompt
    assert "Phase 1 不使用 corroborated schema" in prompt


def test_build_prompt_uses_prose_structure_contract_not_legacy_long_prose():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="中际旭创深度研报",
            content="800G 与 1.6T 光模块需求高景气，毛利率和订单兑现仍需跟踪。",
            author="券商",
            source_platform="研报",
            url="http://report",
            publish_time="2026-06-01",
        )
    ]

    prompt = synth._build_prompt("中际旭创", "fundamentals", items)

    assert "不要写成一整段长文" in prompt
    assert "每段不超过260个中文字符" in prompt
    assert "优先使用 Markdown 表格" in prompt
    assert "不要重复展开4.1" in prompt
    assert "400-600 字" not in prompt
    assert "不要分点罗列" not in prompt


def test_parse_with_citations_splits_long_prose_paragraph_but_preserves_refs():
    synth = KnowledgeSynthesizer(client=None)
    sentence_a = "第一句说明行业需求来自正式研报并保留引用，且补充客户资本开支、产品迭代、交付节奏、供给瓶颈、价格弹性、海外云厂商扩张、国内算力集群建设和供应链国产化八个变量[^1]"
    sentence_b = "第二句说明订单兑现需要跟踪并保留引用，且补充毛利率、费用率、产能扩张节奏、客户集中度、产品结构、存货变化、预付款变化和产线利用率八个变量[^2]"
    sentence_c = "第三句说明毛利率变化需要验证并保留引用，且补充价格竞争、产品结构、供应链瓶颈、技术迭代、库存周期、客户认证节奏、良率变化和资本开支八个变量[^3]"
    sentence_d = "第四句说明若上述变量无法兑现，估值分歧会重新放大，但该判断仍必须保留来源引用并等待后续报告验证[^4]"
    text = f"{sentence_a}。{sentence_b}。{sentence_c}。{sentence_d}。"

    parsed, cites = synth._parse_with_citations(text)

    assert "\n\n" in parsed
    assert "[^1]" in parsed
    assert "[^2]" in parsed
    assert "[^3]" in parsed
    assert "[^4]" in parsed
    assert set(cites) == {1, 2, 3, 4}


def test_parse_with_citations_preserves_markdown_tables_with_citations():
    synth = KnowledgeSynthesizer(client=None)
    table = """
| 变量 | 当前证据 | 含义 |
|------|----------|------|
| 订单 | 800G 放量[^1] | 支撑营收 |
| 毛利率 | 产品结构改善[^2] | 支撑盈利 |
"""

    parsed, cites = synth._parse_with_citations(table)

    assert "| 订单 | 800G 放量[^1] | 支撑营收 |" in parsed
    assert "| 毛利率 | 产品结构改善[^2] | 支撑盈利 |" in parsed
    assert "\n\n| 订单" not in parsed
    assert set(cites) == {1, 2}


def test_build_prompt_source_line_includes_credit_label():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="一季报", content="营收增长40%", author="公司",
            source_platform="公告", url="", publish_time="2026-04-30",
        ),
        SynthesisItem(
            title="研报", content="目标价", author="券商",
            source_platform="研报", url="", publish_time="2026-05-01",
        ),
        SynthesisItem(
            title="新闻", content="行业动态", author="媒体",
            source_platform="新闻", url="", publish_time="2026-05-02",
        ),
        SynthesisItem(
            title="帖子", content="社区观点", author="用户",
            source_platform="雪球", url="", publish_time="2026-05-03",
        ),
    ]
    prompt = synth._build_prompt("圣邦股份", "valuation_debate", items)
    assert "信用层: high" in prompt
    assert "可用方式: core_fact_allowed" in prompt
    assert "信用层: medium" in prompt
    assert "可用方式: professional_observation" in prompt
    assert "信用层: low" in prompt
    assert "可用方式: discussion_only" in prompt


def test_build_prompt_claim_verification_appendix_has_new_wording():
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
    assert "已验证讨论线索" in prompt
    assert "部分支持讨论线索" in prompt
    assert "未验证市场讨论" in prompt
    assert "Phase 1 不输出 corroborated bucket" in prompt
    assert "社区共振/市场关注" in prompt


def test_extract_core_facts_prompt_excludes_professional_and_community_claims():
    synth = KnowledgeSynthesizer(client=object())
    llm_output = '[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": []}]'
    captured = []

    def spy_call_llm(prompt):
        captured.append(prompt)
        return llm_output

    synth._call_llm = spy_call_llm
    synth.extract_core_facts("测试股", {"industry_logic": "营收增长。"})
    prompt = captured[0]
    assert "不要提取券商/媒体观点本身" in prompt
    assert "社区讨论观点本身" in prompt
    assert "多源低信用社区共振线索" in prompt
    assert "可能、预计、推测、若...则..." in prompt
    assert "公告/官方/交易所/巨潮/高信用 confirmed" in prompt
    assert "研报、新闻、雪球、知乎、微信公众号、AgentReach、资金流向" in prompt


def test_parse_citations_sanitizes_non_numeric_markers():
    synth = KnowledgeSynthesizer(client=None)
    text = "收入同比增长40%[^1]，社区讨论[^supported]，毛利率51.6%[^needs_review]。"
    parsed, cites = synth._parse_with_citations(text)
    assert "[^supported]" not in parsed
    assert "[^needs_review]" not in parsed
    assert "[^1]" in parsed
    assert 1 in cites
    assert len(cites) == 1


def test_parse_citations_normalizes_plain_numeric_markers():
    synth = KnowledgeSynthesizer(client=None)
    text = (
        "| 变量 | 证据 | 来源 |\n"
        "|------|------|------|\n"
        "| 订单 | 800G 放量 | [1][23] |\n\n"
        "毛利率仍需跟踪[4]。"
    )

    parsed, cites = synth._parse_with_citations(text)

    assert "[1]" not in parsed
    assert "[23]" not in parsed
    assert "[4]" not in parsed
    assert "[^1][^23]" in parsed
    assert "跟踪[^4]" in parsed
    assert set(cites) == {1, 4, 23}


def test_parse_citations_removes_llm_role_preface():
    synth = KnowledgeSynthesizer(client=None)
    text = (
        "好的，作为资深半导体行业分析师，现基于您提供的多源信息，"
        "对中际旭创的产业逻辑进行综合解读。\n\n"
        "800G 光模块需求仍需跟踪[^1]。"
    )

    parsed, cites = synth._parse_with_citations(text)

    assert "好的，作为资深" not in parsed
    assert "现基于您提供的多源信息" not in parsed
    assert parsed.startswith("800G 光模块需求")
    assert set(cites) == {1}


def test_extract_core_facts_sanitizes_non_numeric_markers():
    synth = KnowledgeSynthesizer(client=object())
    llm_output = (
        '[{"fact_id": 1, "fact": "营收增长[^supported]", "data": "10%[^needs_review]", '
        '"confidence": "高", "source_refs": [1]}]'
    )
    synth._call_llm = lambda prompt: llm_output
    result = synth.extract_core_facts("测试股", {"industry_logic": "营收增长。"})
    assert len(result) == 1
    assert "[^supported]" not in result[0]["fact"]
    assert "[^needs_review]" not in result[0]["data"]
    assert result[0]["fact"] == "营收增长"
    assert result[0]["data"] == "10%"


# --- original tests continue below ---


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
    # Bypass the client check so we can spy on _build_prompt without a real API key.
    synth.client = object()
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


# --- source_refs normalization tests ---

def test_extract_core_facts_normalizes_source_refs():
    """LLM output with source_refs is normalized to ints and capped."""
    synth = KnowledgeSynthesizer(client=object())
    llm_output = (
        '[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1, "2", 3, 4]}]'
    )
    synth._call_llm = lambda prompt: llm_output
    result = synth.extract_core_facts("测试股", {"industry_logic": "营收增长[^1][^2]，毛利提升[^3][^4]。"})
    assert len(result) == 1
    assert result[0]["source_refs"] == [1, 2, 3]


def test_extract_core_facts_missing_source_refs_becomes_empty():
    synth = KnowledgeSynthesizer(client=object())
    llm_output = '[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高"}]'
    synth._call_llm = lambda prompt: llm_output
    result = synth.extract_core_facts("测试股", {"industry_logic": "营收增长。"})
    assert len(result) == 1
    assert result[0]["source_refs"] == []


def test_extract_core_facts_drops_invalid_and_duplicate_refs():
    synth = KnowledgeSynthesizer(client=object())
    llm_output = (
        '[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1, -1, 0, "abc", 1, 2.7, true, "2"]}]'
    )
    synth._call_llm = lambda prompt: llm_output
    result = synth.extract_core_facts("测试股", {"industry_logic": "营收增长[^1][^2]。"})
    assert len(result) == 1
    assert result[0]["source_refs"] == [1, 2]


def test_extract_core_facts_strips_inline_citation_markers():
    synth = KnowledgeSynthesizer(client=object())
    llm_output = (
        '[{"fact_id": 1, "fact": "营收增长[1][^2]", "data": "10% [^3]", "confidence": "高", "source_refs": []}]'
    )
    synth._call_llm = lambda prompt: llm_output
    result = synth.extract_core_facts("测试股", {"industry_logic": "营收增长。"})
    assert len(result) == 1
    assert "[1]" not in result[0]["fact"]
    assert "[^2]" not in result[0]["fact"]
    assert "[^3]" not in result[0]["data"]
    assert result[0]["fact"] == "营收增长"
    assert result[0]["data"] == "10%"
