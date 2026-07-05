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


def test_build_prompt_includes_topic_ownership_contract_for_final_section():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="业绩路径",
            content="800G 放量带动营收增长，毛利率仍需跟踪。",
            author="券商",
            source_platform="研报",
            url="http://report",
            publish_time="2026-06-01",
        )
    ]

    prompt = synth._build_prompt("中际旭创", "fundamentals", items)

    assert "最终报告章节: 4.2" in prompt
    assert "同属最终章节的内部主题: fundamentals, valuation_debate" in prompt
    assert "本主题拥有: 营收、利润、毛利率、费用率、订单兑现、客户结构、业绩指引" in prompt
    assert "禁止重复展开: 完整产业背景、资金流、融资余额、交易情绪" in prompt
    assert "借用主题预算" in prompt
    assert "不超过110个中文字符" in prompt
    assert "不要输出 ## 或 ### 子标题" in prompt


def test_financial_fact_pack_is_appended_only_to_fundamentals_prompt():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="年度报告",
            content="公司披露年度报告。",
            author="公司",
            source_platform="公告",
            url="http://notice",
            publish_time="2026-04-30",
        )
    ]
    fact_pack = {
        "facts": [
            {"metric": "营业收入", "value": "39.82亿元", "period": "2025年annual", "source": "年报"},
            {"metric": "归母净利润", "value": "2.32亿元", "period": "2025年annual", "source": "年报"},
        ]
    }

    fundamentals = synth._build_prompt(
        "复旦微电",
        "fundamentals",
        items,
        formal_financial_fact_pack=fact_pack,
    )
    industry = synth._build_prompt(
        "复旦微电",
        "industry_logic",
        items,
        formal_financial_fact_pack=fact_pack,
    )
    funding = synth._build_prompt(
        "复旦微电",
        "funding_sentiment",
        items,
        formal_financial_fact_pack=fact_pack,
    )

    assert "正式财务事实包（仅供4.2使用，非新增引用）" in fundamentals
    assert "营业收入: 39.82亿元" in fundamentals
    assert "归母净利润: 2.32亿元" in fundamentals
    assert "不得写“未提供营收/利润数据”" in fundamentals
    assert "正式财务事实包" not in industry
    assert "正式财务事实包" not in funding


def test_events_catalysts_prompt_filters_out_sector_background_industry_news():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="存储概念低开",
            content="存储概念板块回调。",
            author="东方财富资讯",
            source_platform="行业资讯",
            url="http://news/sector",
            publish_time="2026-06-01",
            extra={
                "source_type": "mainstream_media",
                "relevance_class": "sector_background",
                "allowed_sections": ["4.1"],
            },
        ),
        SynthesisItem(
            title="存储产品涨价带动晶圆厂产能紧张",
            content="CIS 排产变化是待验证变量。",
            author="东方财富资讯",
            source_platform="行业资讯",
            url="http://news/chain",
            publish_time="2026-06-01",
            extra={
                "source_type": "mainstream_media",
                "relevance_class": "industry_chain_relevant",
                "allowed_sections": ["4.1"],
                "relevance_chain": {"chain_id": "memory_capacity_to_cis_pricing", "confidence": 0.8, "hops": []},
            },
        ),
        SynthesisItem(
            title="公司发布业绩预告",
            content="公司公告披露净利润变化。",
            author="公司",
            source_platform="公告",
            url="http://notice",
            publish_time="2026-06-01",
        ),
    ]

    budget = synth._build_theme_material_budget("韦尔股份", items, {})
    source_rows = [(ref_id, items[ref_id - 1]) for ref_id in budget["themes"]["events_catalysts"]["source_refs"]]
    prompt = synth._build_prompt("韦尔股份", "events_catalysts", source_rows, budget["themes"]["events_catalysts"])

    assert "存储概念低开" not in prompt
    assert "存储产品涨价带动晶圆厂产能紧张" not in prompt
    assert "公司发布业绩预告" in prompt


def test_funding_sentiment_prompt_filters_out_sector_background_industry_news():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="半导体设备走弱",
            content="板块性抛压扩大。",
            author="东方财富资讯",
            source_platform="行业资讯",
            url="http://news/sector",
            publish_time="2026-06-01",
            extra={
                "source_type": "mainstream_media",
                "relevance_class": "sector_background",
                "allowed_sections": ["4.1"],
            },
        ),
        SynthesisItem(
            title="公司发布回购计划",
            content="公司公告披露回购安排。",
            author="公司",
            source_platform="公告",
            url="http://notice",
            publish_time="2026-06-01",
        ),
    ]

    budget = synth._build_theme_material_budget("测试股", items, {})
    source_rows = [(ref_id, items[ref_id - 1]) for ref_id in budget["themes"]["funding_sentiment"]["source_refs"]]
    prompt = synth._build_prompt("测试股", "funding_sentiment", source_rows, budget["themes"]["funding_sentiment"])

    assert "半导体设备走弱" not in prompt
    assert "公司发布回购计划" in prompt


def test_industry_logic_prompt_filters_out_non_direct_sector_background_with_stock_config():
    synth = KnowledgeSynthesizer(client=None)
    stock_config = {
        "product_exposure_terms": ["FPGA", "MCU", "EEPROM"],
        "competitors": ["紫光国微", "安路科技"],
    }
    items = [
        SynthesisItem(
            title="AI服务器带动 MLCC 需求增长",
            content="复旦微电主要产品为 FPGA 与存储芯片，不直接涉及 MLCC 技术路线。",
            author="行业资讯",
            source_platform="行业资讯",
            url="http://news/mlcc",
            publish_time="2026-07-02",
        ),
        SynthesisItem(
            title="FPGA 行业研究报告",
            content="高可靠 FPGA 需求仍需跟踪。",
            author="iwencai",
            source_platform="行业研报",
            url="http://report/fpga",
            publish_time="2026-07-02",
        ),
        SynthesisItem(
            title="紫光国微竞争格局",
            content="紫光国微是军工特种 IC 重要同行。",
            author="iwencai",
            source_platform="行业研报",
            url="http://report/peer",
            publish_time="2026-07-02",
        ),
    ]

    budget = synth._build_theme_material_budget("复旦微电", items, {"stock_config": stock_config})
    source_rows = [(ref_id, items[ref_id - 1]) for ref_id in budget["themes"]["industry_logic"]["source_refs"]]
    prompt = synth._build_prompt("复旦微电", "industry_logic", source_rows, budget["themes"]["industry_logic"], stock_config=stock_config)

    assert "AI服务器带动 MLCC 需求增长" not in prompt
    assert "MLCC 技术路线" not in prompt
    assert "FPGA 行业研究报告" in prompt
    assert "紫光国微竞争格局" in prompt


def test_fundamentals_prompt_uses_keywords_fallback_without_generic_terms():
    synth = KnowledgeSynthesizer(client=None)
    stock_config = {
        "keywords": ["半导体", "芯片", "光模块", "CPO"],
    }
    items = [
        SynthesisItem(
            title="半导体行业周报",
            content="半导体板块震荡。",
            author="行业资讯",
            source_platform="行业资讯",
            url="http://news/generic",
            publish_time="2026-07-02",
        ),
        SynthesisItem(
            title="光模块行业研究报告",
            content="800G 光模块需求增长。",
            author="iwencai",
            source_platform="行业研报",
            url="http://report/optical",
            publish_time="2026-07-02",
        ),
    ]

    budget = synth._build_theme_material_budget("中际旭创", items, {"stock_config": stock_config})
    source_rows = [(ref_id, items[ref_id - 1]) for ref_id in budget["themes"]["fundamentals"]["source_refs"]]
    prompt = synth._build_prompt("中际旭创", "fundamentals", source_rows, budget["themes"]["fundamentals"], stock_config=stock_config)

    assert "半导体行业周报" not in prompt
    assert "光模块行业研究报告" in prompt


def test_build_prompt_uses_previous_topic_ledger_instead_of_raw_previous_prose():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="业绩路径",
            content="营收增长需要看订单兑现。",
            author="券商",
            source_platform="研报",
            url="http://report",
            publish_time="2026-06-01",
        )
    ]
    previous = {
        "industry_logic": (
            "AI算力、800G、1.6T、硅光和CPO是产业技术路线。"
            "这一整句原文不应该被完整塞进后续 prompt。"
        )
    }

    prompt = synth._build_prompt("中际旭创", "fundamentals", items, previous_narratives=previous)

    assert "已展开主题" in prompt
    assert "4.1 产业逻辑与竞争格局" in prompt
    assert "高速光互连技术路线" in prompt
    assert "800G / 1.6T / 硅光 / CPO" in prompt
    assert "只能用一句话说明与本节变量的关系" in prompt
    assert "这一整句原文不应该被完整塞进后续 prompt" not in prompt


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


def test_build_prompt_includes_fundflow_pack_only_for_funding_sentiment():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="一季报", content="公司披露一季报", author="复旦微电",
            source_platform="公告", url="", publish_time="2026-04-30",
        ),
    ]
    pack = {
        "schema": "fundflow_material_pack.v1",
        "rows": [{"date": "2026-07-02", "main_net": 1200.0, "super_large_net": 800.0, "small_net": -900.0, "change_pct": 2.5}],
        "summary": {
            "days": 1,
            "main_net_total": 1200.0,
            "super_large_net_total": 800.0,
            "small_net_total": -900.0,
            "price_change_total_pct": 2.5,
            "signal": "inflow_with_price_up",
        },
    }

    funding = synth._build_prompt(
        "复旦微电",
        "funding_sentiment",
        items,
        fundflow_material_pack=pack,
    )
    industry = synth._build_prompt(
        "复旦微电",
        "industry_logic",
        items,
        fundflow_material_pack=pack,
    )

    assert "资金流向确定性汇总（仅供4.3使用，非新增引用）" in funding
    assert "近1日主力净流入合计 1200万" in funding
    assert "不要自行求和" in funding
    assert "资金流向确定性汇总" not in industry


def test_funding_sentiment_prompt_excludes_financial_announcement_without_fundflow_pack():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="2026年第一季度报告",
            content="2026年Q1营收7.82亿元，归母净利润1.23亿元，环比下降。",
            author="复旦微电",
            source_platform="公告",
            url="",
            publish_time="2026-04-30",
        ),
    ]

    budget = synth._build_theme_material_budget("复旦微电", items, {})
    source_rows = [(ref_id, items[ref_id - 1]) for ref_id in budget["themes"]["funding_sentiment"]["source_refs"]]
    prompt = synth._build_prompt("复旦微电", "funding_sentiment", source_rows, budget["themes"]["funding_sentiment"])

    assert "2026年Q1营收7.82亿元" not in prompt
    assert "归母净利润1.23亿元" not in prompt
    assert "不得用营收、利润、毛利率等财务数据推测主力资金、买盘、卖盘或资金流入流出" in prompt


def test_build_prompt_includes_financial_explanation_pack_only_for_fundamentals():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="年报", content="公司披露年度报告", author="复旦微电",
            source_platform="公告", url="", publish_time="2026-04-30",
        ),
    ]
    pack = {
        "schema": "formal_financial_explanation_pack.v1",
        "rows": [
            {
                "topic": "revenue_change",
                "metric": "营业收入",
                "excerpt": "营业收入变动原因说明：主要系FPGA与MCU产品销售额增加所致。",
                "normalized_summary": "收入变化原因：主要系FPGA与MCU产品销售额增加所致。",
                "source_doc": "688385_2025_annual_jina.txt",
                "confidence": 0.85,
            },
            {
                "topic": "orders_customers_guidance",
                "metric": "订单客户与经营计划",
                "excerpt": "公司将继续拓展工业控制和智能电表客户应用。",
                "normalized_summary": "订单客户或经营计划说明：公司将继续拓展工业控制和智能电表客户应用。",
                "source_doc": "688385_2025_annual_jina.txt",
                "confidence": 0.72,
            },
        ],
    }

    fundamentals = synth._build_prompt(
        "复旦微电",
        "fundamentals",
        items,
        formal_financial_explanation_pack=pack,
    )
    industry = synth._build_prompt(
        "复旦微电",
        "industry_logic",
        items,
        formal_financial_explanation_pack=pack,
    )

    assert "正式经营解释材料包（仅供4.2使用，非新增引用）" in fundamentals
    assert "营业收入变动原因说明" in fundamentals
    assert "不得重复核心事实基座数字成表" in fundamentals
    assert "若本附录已有订单客户/经营计划片段，不得写“未提供订单/客户/指引”" in fundamentals
    assert "正式经营解释材料包" not in industry


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


# ---------------------------------------------------------------------------
# Phase 3c: Peer comparison material in KnowledgeSynthesizer prompts
# ---------------------------------------------------------------------------


def _sample_peer_material():
    """Build a standard peer material dict for Phase 3c tests."""
    return {
        "schema": "peer_comparison_material.v1",
        "target": "复旦微电",
        "peers": ["紫光国微", "安路科技"],
        "rows": [
            {
                "dimension": "盈利能力",
                "target": "复旦微电",
                "peer": "紫光国微",
                "metric": "gross_margin",
                "target_value": "55.3%",
                "peer_value": "52.6%",
                "comparison": "毛利率高于紫光国微(52.6%)约2.7%",
                "period": "FY2025",
                "unit": "%",
                "confidence": 0.85,
                "usage": "claim_eligible",
                "source_refs": ["指标:competitor_metrics"],
            },
            {
                "dimension": "估值水平",
                "target": "复旦微电",
                "peer": "紫光国微",
                "metric": "pe_ttm",
                "target_value": "220.36",
                "peer_value": "42.97",
                "comparison": "复旦微电PE(TTM)远高于紫光国微",
                "period": "2026-07-01",
                "unit": "倍",
                "confidence": 0.85,
                "usage": "claim_eligible",
                "source_refs": ["指标:competitor_metrics"],
            },
            {
                "dimension": "估值水平",
                "target": "复旦微电",
                "peer": "安路科技",
                "metric": "mcap",
                "target_value": "352.76",
                "peer_value": "120.50",
                "comparison": "总市值高于安路科技",
                "period": "2026-07-01",
                "unit": "亿",
                "confidence": 0.85,
                "usage": "claim_eligible",
                "source_refs": ["指标:competitor_metrics"],
            },
        ],
        "warnings": [],
    }


def test_peer_appendix_included_for_industry_logic():
    """Build prompt for industry_logic with peer material; verify heading, comparisons, source refs."""
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="Q1业绩分析", content="营收增长40%", author="张三",
            source_platform="雪球", url="http://x", publish_time="2026-05-20",
            interaction_score=100,
        ),
    ] * 3  # ensure >= min_items
    peer_material = _sample_peer_material()

    prompt = synth._build_prompt("复旦微电", "industry_logic", items, peer_comparison_material=peer_material)

    assert "同行对比材料（正式/指标来源，非新增引用）" in prompt
    assert "非新增引用" in prompt
    assert "毛利率高于紫光国微" in prompt
    assert "指标:competitor_metrics" in prompt
    assert "使用规则：" in prompt
    assert "claim_eligible" in prompt
    assert "confidence=0.85" in prompt
    assert "不得生成新的 [^n] 引用编号" in prompt


def test_peer_appendix_included_for_fundamentals_and_valuation_only():
    """Peer appendix appears in fundamentals and valuation_debate, NOT in funding_sentiment or events_catalysts."""
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="测试内容", content="测试内容", author="A",
            source_platform="雪球", url="", publish_time="2026-01-01",
        ),
    ] * 3
    peer_material = _sample_peer_material()

    fundamentals_prompt = synth._build_prompt("复旦微电", "fundamentals", items, peer_comparison_material=peer_material)
    valuation_prompt = synth._build_prompt("复旦微电", "valuation_debate", items, peer_comparison_material=peer_material)
    funding_prompt = synth._build_prompt("复旦微电", "funding_sentiment", items, peer_comparison_material=peer_material)
    events_prompt = synth._build_prompt("复旦微电", "events_catalysts", items, peer_comparison_material=peer_material)

    assert "同行对比材料" in fundamentals_prompt
    assert "同行对比材料" in valuation_prompt
    assert "同行对比材料" not in funding_prompt
    assert "同行对比材料" not in events_prompt


def test_peer_appendix_hard_filters_low_confidence_rows():
    """Peer row with confidence 0.40 must not appear in prompt."""
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="测试", content="测试", author="A",
            source_platform="雪球", url="", publish_time="2026-01-01",
        ),
    ] * 3
    material = _sample_peer_material()
    material["rows"].append({
        "dimension": "盈利能力",
        "target": "复旦微电",
        "peer": "聚辰股份",
        "metric": "gross_margin",
        "target_value": "55.3%",
        "peer_value": "48.0%",
        "comparison": "毛利率高于聚辰股份7.3%",
        "period": "FY2025",
        "unit": "%",
        "confidence": 0.40,
        "usage": "audit_only",
        "source_refs": ["来源:old_system"],
    })

    prompt = synth._build_prompt("复旦微电", "industry_logic", items, peer_comparison_material=material)

    assert "同行对比材料" in prompt  # heading still present
    assert "聚辰股份" not in prompt  # low-confidence peer dropped
    assert "毛利率高于聚辰股份" not in prompt


def test_peer_appendix_strips_context_only_comparisons():
    """Context-only row (confidence 0.60) keeps dimension/peer/source but strips comparison/values."""
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="测试", content="测试", author="A",
            source_platform="雪球", url="", publish_time="2026-01-01",
        ),
    ] * 3
    material = _sample_peer_material()
    # Add a context_only row with unique values that won't collide with claim_eligible rows.
    material["rows"].append({
        "dimension": "盈利能力",
        "target": "复旦微电",
        "peer": "兆易创新",
        "metric": "gross_margin",
        "target_value": "12345.67%",  # unique value unlikely to appear elsewhere
        "peer_value": "98765.43%",
        "comparison": "毛利率高于兆易创新99999.24%",
        "period": "FY2025",
        "unit": "%",
        "confidence": 0.60,
        "usage": "context_only",
        "source_refs": ["指标:competitor_metrics"],
    })

    prompt = synth._build_prompt("复旦微电", "industry_logic", items, peer_comparison_material=material)

    assert "同行对比材料" in prompt
    assert "兆易创新" in prompt  # peer name remains
    assert "context_only" in prompt  # context_only label present
    assert "盈利能力" in prompt  # dimension remains
    # stripped fields must not appear for the context_only row
    assert "毛利率高于兆易创新99999.24%" not in prompt
    assert "12345.67%" not in prompt
    assert "98765.43%" not in prompt


def test_synthesize_passes_peer_material_to_build_prompt(monkeypatch):
    """Verify peer_material flows from synthesize → _build_prompt."""
    synth = KnowledgeSynthesizer(client=None)
    synth.client = object()
    items = [
        SynthesisItem(
            title="Q1业绩分析", content="营收增长40%", author="张三",
            source_platform="雪球", url="http://x", publish_time="2026-05-20",
            interaction_score=100,
        ),
    ] * 3
    peer_material = _sample_peer_material()
    calls = []

    def spy(stock_name, theme_key, source_rows, theme_budget=None, previous_narratives=None, claim_verification_context=None, peer_comparison_material=None, stock_config=None, formal_financial_fact_pack=None, formal_financial_explanation_pack=None, fundflow_material_pack=None):
        calls.append(peer_comparison_material)
        return ""

    monkeypatch.setattr(synth, "_build_prompt", spy)
    monkeypatch.setattr(synth, "_call_llm", lambda prompt: "")

    result = synth.synthesize("复旦微电", {"items": items, "peer_comparison_material": peer_material})
    # At least one call received the peer_material reference
    assert any(call is peer_material for call in calls), "peer_material object not passed to _build_prompt"


def test_core_fact_extraction_prompt_does_not_include_peer_appendix():
    """core fact extraction prompt must not contain peer appendix heading."""
    synth = KnowledgeSynthesizer(client=object())
    narratives = {"industry_logic": "营收增长[^1]。毛利率改善[^2]。"}
    prompts_sent = []

    def spy_call_llm(prompt):
        prompts_sent.append(prompt)
        return '[{"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "source_refs": [1]}]'

    synth._call_llm = spy_call_llm
    result = synth.extract_core_facts("复旦微电", narratives)

    assert len(prompts_sent) == 1
    assert "同行对比材料" not in prompts_sent[0]
    assert "非新增引用" not in prompts_sent[0]
    assert "营收增长" in prompts_sent[0]


def test_peer_appendix_order_before_claim_verification_and_previous_ledger():
    """Peer appendix is placed after numbered sources, before verification context and previous ledger."""
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="测试", content="测试", author="A",
            source_platform="雪球", url="", publish_time="2026-01-01",
        ),
    ] * 3
    context = {
        "enabled": True,
        "stock": "复旦微电",
        "counts": {
            "verified": 1,
            "supported": 0,
            "unverified": 0,
            "needs_review": 0,
            "high_credit_claims": 1,
            "low_credit_claims": 0,
            "skipped_files": 0,
        },
        "verified_claims": [
            {
                "claim_text": "公告确认营收增长",
                "action": "verified",
                "verified_by_titles": ["公司业绩公告"],
                "confidence": 85,
            }
        ],
        "supported_claims": [],
        "unverified_claims": [],
    }
    previous = {
        "industry_logic": (
            "AI算力、800G、1.6T、硅光和CPO是产业技术路线。"
            "这些主题已在4.1展开。"
        )
    }

    prompt = synth._build_prompt(
        "复旦微电",
        "fundamentals",
        items,
        previous_narratives=previous,
        claim_verification_context=context,
        peer_comparison_material=_sample_peer_material(),
    )

    source_pos = prompt.find("信息来源：")
    peer_pos = prompt.find("同行对比材料（正式/指标来源，非新增引用）")
    context_pos = prompt.find("Claim Verification Context")
    ledger_pos = prompt.find("已展开主题")
    assert -1 not in {source_pos, peer_pos, context_pos, ledger_pos}
    assert source_pos < peer_pos < context_pos < ledger_pos


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
    previous = {"industry_logic": "AI算力、800G 和 CPO 是行业技术路线。"}
    prompt = synth._build_prompt("圣邦股份", "fundamentals", items, previous_narratives=previous, claim_verification_context=context)
    sources_pos = prompt.find("信息来源：")
    context_pos = prompt.find("Claim Verification Context")
    narratives_pos = prompt.find("已展开主题")
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

    def spy(stock_name, theme_key, source_rows, theme_budget=None, previous_narratives=None, claim_verification_context=None, peer_comparison_material=None, stock_config=None, formal_financial_fact_pack=None, formal_financial_explanation_pack=None, fundflow_material_pack=None):
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


# ---------------------------------------------------------------------------
# Theme Material Budget with Global Source IDs
# ---------------------------------------------------------------------------


def test_theme_budget_uses_global_source_refs():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="行业资讯",
            content="半导体板块动态。",
            author="媒体",
            source_platform="行业资讯",
            url="",
            publish_time="2026-07-01",
        ),
        SynthesisItem(
            title="公司业绩公告",
            content="2026年Q1营收增长。",
            author="公司",
            source_platform="公告",
            url="",
            publish_time="2026-04-30",
        ),
        SynthesisItem(
            title="资金流向",
            content="主力净流入1200万。",
            author="东方财富",
            source_platform="资金流向",
            url="",
            publish_time="2026-07-02",
        ),
    ]

    budget = synth._build_theme_material_budget("测试股", items, {})
    # events_catalysts should include the announcement at global ref 2, not renumber to [1].
    event_refs = budget["themes"]["events_catalysts"]["source_refs"]
    assert 2 in event_refs
    assert 1 not in event_refs  # industry news excluded
    source_rows = [(ref_id, items[ref_id - 1]) for ref_id in event_refs]
    prompt = synth._build_prompt("测试股", "events_catalysts", source_rows, budget["themes"]["events_catalysts"])
    assert "[2]" in prompt
    assert "[1]" not in prompt or "[1]" not in prompt.split("信息来源：")[1]


def test_build_prompt_uses_precomputed_source_rows_without_refiltering():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="公告",
            content="公司公告内容。",
            author="公司",
            source_platform="公告",
            url="",
            publish_time="2026-04-30",
        ),
    ] * 3

    calls = []
    original_filter = KnowledgeSynthesizer._filter_items_for_theme

    def spy_filter(theme_key, items, stock_name="", stock_config=None):
        calls.append((theme_key, len(items)))
        return original_filter(theme_key, items, stock_name, stock_config)

    import scripts.utils.knowledge_synthesizer as ks_module
    ks_module.KnowledgeSynthesizer._filter_items_for_theme = staticmethod(spy_filter)
    try:
        budget = synth._build_theme_material_budget("测试股", items, {})
        event_refs = budget["themes"]["events_catalysts"]["source_refs"]
        source_rows = [(ref_id, items[ref_id - 1]) for ref_id in event_refs]
        calls.clear()
        synth._build_prompt("测试股", "events_catalysts", source_rows, budget["themes"]["events_catalysts"])
        # _build_prompt should not call _filter_items_for_theme again.
        assert len(calls) == 0
    finally:
        ks_module.KnowledgeSynthesizer._filter_items_for_theme = original_filter


def test_budget_routes_fundflow_items_only_to_funding_sentiment():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="公告",
            content="公司公告内容。",
            author="公司",
            source_platform="公告",
            url="",
            publish_time="2026-04-30",
        ),
        SynthesisItem(
            title="资金流向",
            content="主力净流入1200万。",
            author="东方财富",
            source_platform="资金流向",
            url="",
            publish_time="2026-07-02",
        ),
    ]

    budget = synth._build_theme_material_budget("测试股", items, {})
    assert budget["themes"]["funding_sentiment"]["source_refs"] == [2]
    assert 2 not in budget["themes"]["events_catalysts"]["source_refs"]
    assert 2 not in budget["themes"]["industry_logic"]["source_refs"]
    assert 2 not in budget["themes"]["fundamentals"]["source_refs"]
    assert 2 not in budget["themes"]["valuation_debate"]["source_refs"]


def test_no_fundflow_no_funding_sentiment_even_with_financial_announcements():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="2026年第一季度报告",
            content="2026年Q1营收7.82亿元，归母净利润1.23亿元，环比下降。",
            author="复旦微电",
            source_platform="公告",
            url="",
            publish_time="2026-04-30",
        ),
    ]

    budget = synth._build_theme_material_budget("复旦微电", items, {})
    assert budget["themes"]["funding_sentiment"]["source_refs"] == []
    assert budget["themes"]["funding_sentiment"]["skip_reason"] != ""


def test_events_catalysts_can_render_when_funding_missing():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="公司发布业绩预告",
            content="公司公告披露净利润变化。",
            author="公司",
            source_platform="公告",
            url="",
            publish_time="2026-04-30",
        ),
    ]

    budget = synth._build_theme_material_budget("测试股", items, {})
    assert budget["themes"]["events_catalysts"]["source_refs"] == [1]
    assert budget["themes"]["funding_sentiment"]["source_refs"] == []


def test_fundamentals_prompt_orders_explanation_before_fact_pack():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="年报",
            content="公司披露年度报告",
            author="复旦微电",
            source_platform="公告",
            url="",
            publish_time="2026-04-30",
        ),
    ]
    fact_pack = {
        "facts": [
            {"metric": "营业收入", "value": "39.82亿元", "period": "2025年annual", "source": "年报"},
        ]
    }
    explanation_pack = {
        "schema": "formal_financial_explanation_pack.v1",
        "rows": [
            {
                "topic": "revenue_change",
                "metric": "营业收入",
                "excerpt": "营业收入变动原因说明：主要系FPGA产品销售额增加所致。",
                "source_doc": "688385_2025_annual_jina.txt",
                "confidence": 0.85,
            }
        ],
    }

    budget = synth._build_theme_material_budget("复旦微电", items, {})
    source_rows = [(ref_id, items[ref_id - 1]) for ref_id in budget["themes"]["fundamentals"]["source_refs"]]
    prompt = synth._build_prompt(
        "复旦微电",
        "fundamentals",
        source_rows,
        budget["themes"]["fundamentals"],
        formal_financial_fact_pack=fact_pack,
        formal_financial_explanation_pack=explanation_pack,
    )

    explanation_pos = prompt.find("正式经营解释材料包")
    fact_pos = prompt.find("正式财务事实包")
    assert explanation_pos != -1
    assert fact_pos != -1
    assert explanation_pos < fact_pos


def test_supply_chain_state_blocks_generic_position_without_operating_variables():
    synth = KnowledgeSynthesizer(client=None)
    items = [
        SynthesisItem(
            title="行业研报",
            content="公司竞争格局稳定。",
            author="券商",
            source_platform="行业研报",
            url="",
            publish_time="2026-07-01",
        ),
    ]

    budget = synth._build_theme_material_budget("测试股", items, {})
    supply_chain_state = budget["themes"]["industry_logic"]["supply_chain_state"]
    assert supply_chain_state["has_operating_variable"] is False
    assert supply_chain_state["matched_terms"] == []
    source_rows = [(ref_id, items[ref_id - 1]) for ref_id in budget["themes"]["industry_logic"]["source_refs"]]
    prompt = synth._build_prompt("测试股", "industry_logic", source_rows, budget["themes"]["industry_logic"])
    assert "披露不足" in prompt
    assert "不要写出具体供应链位置判断" in prompt
