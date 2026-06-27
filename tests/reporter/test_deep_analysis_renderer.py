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


def test_curated_external_display_is_addendum_not_replacement():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "synthesis": {
            "industry_logic": "baseline 产业逻辑[^1]",
            "fundamentals": "baseline 业绩路径",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "citations": {1: {"source": "雪球", "title": "baseline title"}},
        },
        "deep_analysis_display": {
            "industry_logic": "精选外部材料仅作为专业观察，提示中际旭创产业线索：800G需求增长[^1]",
            "fundamentals": "",
            "valuation_debate": "精选外部材料仅作为专业观察，不直接形成估值结论；估值仍应回到官方财务、市场价格和评分模型。",
            "funding_sentiment": "精选外部材料不直接生成资金面判断，资金面仍以交易数据、资金流和市场指标为准。",
            "events_catalysts": "",
            "citations": {
                1: {
                    "source": "微信公众号精选观察",
                    "title": "中际旭创外部观察标题",
                    "source_type": "curated_external_analysis_evidence",
                }
            },
        },
    }

    result = renderer.render(ctx)

    assert "### 4.1 产业逻辑与竞争格局" in result
    assert "baseline 产业逻辑[^1]" in result
    assert "### 4.4 精选外部观察（Preview）" in result
    assert "800G需求增长[^2]" in result
    assert result.index("baseline 产业逻辑") < result.index("### 4.4 精选外部观察（Preview）")
    assert "不直接形成估值结论" not in result
    assert "- [^1] 雪球" in result
    assert "- [^2] 微信公众号精选观察" in result


def test_render_with_core_facts():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "行业逻辑。",
            "citations": {1: {"source": "雪球", "author": "张三", "title": "测试"}},
        },
        "core_facts": [
            {"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "provenance_status": "supported", "source_labels": ["公告"], "evidence_type": "official"},
        ],
    }
    result = renderer.render(ctx)
    assert "## 三、核心事实基座" in result
    assert "营收增长" in result


def test_render_core_facts_evidence_column():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "行业逻辑。",
            "citations": {1: {"source": "雪球"}, 2: {"source": "研报"}},
        },
        "core_facts": [
            {
                "fact_id": 1,
                "fact": "营收增长",
                "data": "10%",
                "confidence": "高",
                "source_labels": ["雪球", "研报"],
                "evidence_type": "mixed",
                "provenance_status": "supported",
            },
        ],
    }
    result = renderer.render(ctx)
    assert "| # | 事实 | 数据/来源 | 证据 | 置信度 |" in result
    assert "雪球、研报 (mixed)" in result


def test_render_old_style_fact_renders_missing_ref():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "行业逻辑。",
            "citations": {},
        },
        "core_facts": [
            {"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "provenance_status": "supported", "source_labels": ["公告"], "evidence_type": "official"},
            {"fact_id": 2, "fact": "毛利提升", "data": "51%", "confidence": "高"},
        ],
    }
    result = renderer.render(ctx)
    assert "未绑定引用 (unknown)" in result


def test_render_evidence_cell_no_numbered_citations():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "行业逻辑。",
            "citations": {1: {"source": "雪球"}},
        },
        "core_facts": [
            {
                "fact_id": 1,
                "fact": "营收增长",
                "data": "10%",
                "confidence": "高",
                "source_labels": ["雪球"],
                "evidence_type": "community",
                "provenance_status": "supported",
            },
        ],
    }
    result = renderer.render(ctx)
    evidence_section = result.split("| # | 事实 | 数据/来源 | 证据 | 置信度 |")[1].split("## 四、深度分析")[0]
    assert "[^" not in evidence_section


def test_render_partially_supported_evidence_cell():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "行业逻辑。",
            "citations": {1: {"source": "雪球"}},
        },
        "core_facts": [
            {
                "fact_id": 1,
                "fact": "营收增长",
                "data": "10%",
                "confidence": "高",
                "source_labels": ["雪球"],
                "evidence_type": "community",
                "provenance_status": "partially_supported",
            },
        ],
    }
    result = renderer.render(ctx)
    assert "雪球 (community, 部分引用无效)" in result


def test_render_invalid_ref_evidence_cell():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "行业逻辑。",
            "citations": {},
        },
        "core_facts": [
            {
                "fact_id": 1,
                "fact": "营收增长",
                "data": "10%",
                "confidence": "高",
                "source_labels": ["公告"],
                "evidence_type": "official",
                "provenance_status": "supported",
            },
            {
                "fact_id": 2,
                "fact": "毛利提升",
                "data": "51%",
                "confidence": "高",
                "source_labels": [],
                "evidence_type": "unknown",
                "provenance_status": "invalid_ref",
            },
        ],
    }
    result = renderer.render(ctx)
    assert "引用无效 (unknown)" in result


def test_render_verified_claim_summary_section():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中简科技",
        "synthesis": {
            "industry_logic": "基本面 LLM 合成未启用或未产生有效输出。",
            "citations": {},
        },
        "claim_verification_summary": {
            "verified": [
                {
                    "claim_text": "2026年第一季度营业收入下降约50%-60%",
                    "status": "verified",
                    "verified_by_titles": ["中简科技2026年第一季度报告"],
                    "confidence": 84,
                }
            ],
            "supported": [
                {
                    "claim_text": "研发费用同比增长约175%-185%",
                    "status": "supported",
                    "verified_by_titles": ["中简科技2026年第一季度报告"],
                    "confidence": 76,
                }
            ],
        },
    }

    result = renderer.render(ctx)

    assert "### 事实核验摘要" in result
    assert "2026年第一季度营业收入下降约50%-60%" in result
    assert "| 研发费用同比增长约175%-185% | 部分支持，非官方确认 | 中简科技2026年第一季度报告 | 76 |" in result
    assert result.index("### 事实核验摘要") < result.index("### 4.1 产业逻辑与竞争格局")


def test_render_verified_claim_summary_accepts_real_summary_bucket_names():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中简科技",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "claim_verification_summary": {
            "verified_claims": [
                {
                    "claim_text": "客户需求量阶段性减少导致收入下降约50%-60%",
                    "action": "verified",
                    "verified_by_titles": ["中简科技2026年第一季度报告"],
                    "confidence": 84,
                }
            ],
            "supported_claims": [
                {
                    "claim_text": "研发费用同比增长约175%-185%",
                    "action": "supported",
                    "verified_by_titles": ["中简科技2026年第一季度报告"],
                    "confidence": 76,
                }
            ],
        },
    }

    result = renderer.render(ctx)

    assert "### 事实核验摘要" in result
    assert "| 客户需求量阶段性减少导致收入下降约50%-60% | 已验证 | 中简科技2026年第一季度报告 | 84 |" in result
    assert "| 研发费用同比增长约175%-185% | 部分支持，非官方确认 | 中简科技2026年第一季度报告 | 76 |" in result


def test_verified_claim_summary_excludes_unverified_and_malformed_rows():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中简科技",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "claim_verification_summary": {
            "verified": [
                {"claim_text": "", "status": "verified", "verified_by_titles": ["公告"]},
                {"claim_text": "有效事实", "status": "malformed", "verified_by_titles": ["公告"]},
                {"claim_text": "有效核验事实", "status": "verified", "verified_by_titles": ["公告"]},
            ],
            "unverified": [
                {"claim_text": "社区未核验观点", "status": "unverified", "verified_by_titles": ["社区"]},
            ],
            "needs_review": [
                {"claim_text": "待人工复核观点", "status": "needs_review", "verified_by_titles": ["公告"]},
            ],
            "contradicted": [
                {"claim_text": "被反驳观点", "status": "contradicted", "verified_by_titles": ["公告"]},
            ],
        },
    }

    result = renderer.render(ctx)

    assert "### 事实核验摘要" in result
    assert "有效核验事实" in result
    assert "社区未核验观点" not in result
    assert "待人工复核观点" not in result
    assert "被反驳观点" not in result
    assert "有效事实" not in result


def test_verified_claim_summary_sanitizes_citations_urls_and_agent_reach_labels():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中简科技",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "claim_verification_summary": {
            "verified": [
                {
                    "claim_text": "收入下降[^1] | 研发费用增加[2]",
                    "status": "verified",
                    "verified_by_titles": [
                        "AgentReach(web) https://example.com/report | 中简科技公告[^3]"
                    ],
                    "confidence": "84",
                }
            ]
        },
    }

    result = renderer.render(ctx)
    section = result.split("### 事实核验摘要")[1].split("### 4.1")[0]

    assert "[^" not in section
    assert "[2]" not in section
    assert "http" not in section
    assert "AgentReach" not in section
    assert "收入下降 \\| 研发费用增加" in section
    assert "中简科技公告" in section


def test_verified_claim_summary_defaults_missing_source_and_handles_bad_confidence():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中简科技",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "claim_verification_summary": {
            "verified": [
                {
                    "claim_text": "官方核验事实",
                    "status": "verified",
                    "confidence": {"unexpected": "shape"},
                }
            ]
        },
    }

    result = renderer.render(ctx)

    assert "| 官方核验事实 | 已验证 | 高信用来源 | — |" in result


def test_supported_claim_summary_defaults_missing_source_to_partial_support_source():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "圣邦股份",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "claim_verification_summary": {
            "supported_claims": [
                {
                    "claim_text": "一季报净利润同比增长106.96%",
                    "action": "supported",
                    "confidence": 54,
                }
            ]
        },
    }

    result = renderer.render(ctx)

    assert "| 一季报净利润同比增长106.96% | 部分支持，非官方确认 | 部分支持来源 | 54 |" in result
    assert "| 一季报净利润同比增长106.96% | 部分支持，非官方确认 | 高信用来源 | 54 |" not in result


def test_verified_claim_summary_strips_title_prefix_from_source():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中简科技",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "claim_verification_summary": {
            "verified_claims": [
                {
                    "claim_text": "官方核验事实",
                    "action": "verified",
                    "verified_by_titles": ["Title: 99999999.PDF"],
                    "confidence": 84,
                }
            ]
        },
    }

    result = renderer.render(ctx)

    assert "Title:" not in result
    assert "| 官方核验事实 | 已验证 | 99999999.PDF | 84 |" in result


def test_verified_claim_summary_maps_known_cninfo_pdf_titles():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中简科技",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "claim_verification_summary": {
            "verified_claims": [
                {
                    "claim_text": "客户需求量阶段性减少导致收入下降约50%-60%",
                    "action": "verified",
                    "verified_by_titles": ["Title: 1225106812.PDF"],
                    "confidence": 84,
                }
            ]
        },
    }

    result = renderer.render(ctx)

    assert "1225106812.PDF" not in result
    assert "| 客户需求量阶段性减少导致收入下降约50%-60% | 已验证 | 2026年第一季度业绩预告 | 84 |" in result


def test_verified_claim_summary_caps_rows_and_does_not_mutate_inputs():
    renderer = DeepAnalysisRenderer()
    synthesis = {"industry_logic": "行业逻辑。", "citations": {}}
    core_facts = [{"fact_id": 1, "fact": "营收", "data": "10%", "confidence": "高"}]
    summary = {
        "verified": [
            {
                "claim_text": f"核验事实{i}",
                "status": "verified",
                "verified_by_titles": [f"公告{i}"],
                "confidence": i,
            }
            for i in range(8)
        ]
    }
    ctx = {
        "stock_name": "中简科技",
        "synthesis": synthesis,
        "core_facts": core_facts,
        "claim_verification_summary": summary,
    }
    original_synthesis = dict(synthesis)
    original_core_facts = [dict(row) for row in core_facts]

    result = renderer.render(ctx)
    section = result.split("### 事实核验摘要")[1].split("### 4.1")[0]

    assert section.count("| 核验事实") == 6
    assert "核验事实5" in section
    assert "核验事实6" not in section
    assert synthesis == original_synthesis
    assert core_facts == original_core_facts


def test_verified_claim_summary_not_rendered_for_missing_or_empty_summary():
    renderer = DeepAnalysisRenderer()
    base_ctx = {
        "stock_name": "中简科技",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
    }

    assert "官方事实核验摘要" not in renderer.render(base_ctx)
    assert "官方事实核验摘要" not in renderer.render(
        {**base_ctx, "claim_verification_summary": {"verified": [], "supported": []}}
    )
    assert "官方事实核验摘要" not in renderer.render(
        {**base_ctx, "claim_verification_summary": "bad-shape"}
    )


def test_render_core_facts_all_invalid_shows_empty_state():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "圣邦股份",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "core_facts": [
            {"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "provenance_status": "invalid_ref"},
            {"fact_id": 2, "fact": "毛利提升", "data": "51%", "confidence": "高", "provenance_status": "missing_ref"},
        ],
    }
    result = renderer.render(ctx)
    assert "## 三、核心事实基座" in result
    assert "当前未形成可由高信用来源支撑的核心事实基座" in result
    assert "| # | 事实 | 数据/来源 | 证据 | 置信度 |" not in result
    assert "引用无效 (unknown)" not in result


def test_render_core_facts_mixed_invalid_keeps_table():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "圣邦股份",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "core_facts": [
            {"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "provenance_status": "supported", "source_labels": ["公告"], "evidence_type": "official"},
            {"fact_id": 2, "fact": "毛利提升", "data": "51%", "confidence": "高", "provenance_status": "invalid_ref"},
        ],
    }
    result = renderer.render(ctx)
    assert "| # | 事实 | 数据/来源 | 证据 | 置信度 |" in result
    assert "营收增长" in result
    assert "毛利提升" in result
    assert "引用无效 (unknown)" in result


def test_render_claim_summary_uses_neutral_title():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中简科技",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "claim_verification_summary": {
            "verified": [{"claim_text": "营收下降", "status": "verified", "verified_by_titles": ["公告"], "confidence": 84}],
        },
    }
    result = renderer.render(ctx)
    assert "### 官方事实核验摘要" not in result
    assert "### 事实核验摘要" in result


def test_render_supported_claim_status_label():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中简科技",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "claim_verification_summary": {
            "supported": [{"claim_text": "研发费用增长", "status": "supported", "verified_by_titles": ["公告"], "confidence": 76}],
        },
    }
    result = renderer.render(ctx)
    assert "部分支持，非官方确认" in result
    assert "| 研发费用增长 | 部分支持，非官方确认 |" in result


def test_render_prefers_synthesis_display():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "baseline 行业逻辑。",
            "citations": {},
        },
        "synthesis_display": {
            "industry_logic": "enhanced 年报全文 行业逻辑。",
            "citations": {},
        },
        "core_facts": [],
    }
    result = renderer.render(ctx)
    assert "enhanced 年报全文 行业逻辑" in result
    assert "baseline 行业逻辑" not in result


def test_render_falls_back_to_synthesis_when_no_display():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "baseline 行业逻辑。",
            "citations": {},
        },
        "core_facts": [],
    }
    result = renderer.render(ctx)
    assert "baseline 行业逻辑" in result


def test_render_prefers_deep_analysis_display():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "baseline 行业逻辑。",
            "citations": {},
        },
        "synthesis_display": {
            "industry_logic": "synthesis_display 行业逻辑。",
            "citations": {},
        },
        "deep_analysis_display": {
            "industry_logic": "deep_analysis_display 行业逻辑。",
            "citations": {},
        },
        "core_facts": [],
    }
    result = renderer.render(ctx)
    assert "deep_analysis_display 行业逻辑" in result
    assert "synthesis_display 行业逻辑" not in result
    assert "baseline 行业逻辑" not in result


def test_render_deep_analysis_display_with_curated_external_sources_adds_preview_notice():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "baseline 行业逻辑。",
            "citations": {},
        },
        "deep_analysis_display": {
            "industry_logic": "微信观察内容[^1]。",
            "citations": {
                1: {
                    "source": "微信公众号精选观察",
                    "source_type": "curated_external_analysis_evidence",
                    "title": "测试微信文章",
                },
            },
        },
        "core_facts": [],
    }

    result = renderer.render(ctx)

    assert "精选外部材料仅作为专业观察" in result
    assert "不参与评分、风险评分或最终建议" in result
    assert "baseline 行业逻辑" in result
    assert "### 4.4 精选外部观察（Preview）" in result
    assert result.index("### 4.1 产业逻辑与竞争格局") < result.index("### 4.4 精选外部观察（Preview）")


def test_render_uses_synthesis_display_when_no_deep_analysis():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "baseline 行业逻辑。",
            "citations": {},
        },
        "synthesis_display": {
            "industry_logic": "synthesis_display 行业逻辑。",
            "citations": {},
        },
        "core_facts": [],
    }
    result = renderer.render(ctx)
    assert "synthesis_display 行业逻辑" in result
    assert "baseline 行业逻辑" not in result
