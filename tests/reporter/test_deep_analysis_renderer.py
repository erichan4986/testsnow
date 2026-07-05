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


def test_deep_analysis_renders_controlled_fallbacks_for_empty_sections():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "",
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "citations": {},
        },
    }

    result = renderer.render(ctx)

    assert "### 4.1 产业逻辑与竞争格局" in result
    assert "当前正式材料不足以形成可验证的产业逻辑与竞争格局判断" in result
    assert "### 4.2 业绩路径与多空分歧" in result
    assert "当前正式材料不足以形成可验证的业绩路径或估值分歧判断" in result
    assert "### 4.3 资金面与催化剂时间线" in result
    assert "当前正式材料未形成可验证的资金面或催化剂时间线" in result


def test_deep_analysis_funding_only_renders_events_fallback():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "产业逻辑。",
            "fundamentals": "基本面。",
            "valuation_debate": "",
            "funding_sentiment": "资金面内容。",
            "events_catalysts": "",
            "citations": {},
        },
    }

    result = renderer.render(ctx)

    assert "### 4.3 资金面与催化剂时间线" in result
    assert "资金面内容。" in result
    assert "当前正式材料未形成可验证的催化剂时间线。" in result


def test_deep_analysis_events_only_renders_funding_fallback():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "产业逻辑。",
            "fundamentals": "基本面。",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "催化剂内容。",
            "citations": {},
        },
    }

    result = renderer.render(ctx)

    assert "### 4.3 资金面与催化剂时间线" in result
    assert "催化剂内容。" in result
    assert "当前正式材料未提供足够资金面数据。" in result


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
    assert "### 4.4 外部观点与待验证变量（Preview）" in result
    assert "800G需求增长[^2]" in result
    assert result.index("baseline 产业逻辑") < result.index("### 4.4 外部观点与待验证变量（Preview）")
    assert "不直接形成估值结论" not in result
    assert "- [^1] 雪球" in result


def test_curated_external_narrative_reasoning_cards_not_rendered_visible():
    renderer = DeepAnalysisRenderer()
    excerpt = "外部原文片段" * 20
    ctx = {
        "stock_name": "复旦微电",
        "synthesis": {
            "industry_logic": "baseline 产业逻辑[^1]",
            "fundamentals": "baseline 业绩路径",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "citations": {1: {"source": "公告", "title": "年报"}},
        },
        "deep_analysis_display": {
            "industry_logic": "外部材料提示估值分歧[^1]",
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "citations": {
                1: {
                    "source": "雪球专栏观察",
                    "title": "复旦微电估值分析",
                    "source_type": "curated_external_analysis_evidence",
                    "verification_status": "professional_observation",
                    "claim_id": "fudan-xq-val-001",
                }
            },
            "_curated_external_narrative": True,
            "_curated_external_narrative_paragraphs": [
                {
                    "heading": "估值分歧",
                    "text": "外部材料提示估值分歧。",
                    "citation_refs": [1],
                }
            ],
            "_curated_external_reasoning_cards": [
                {
                    "claim_id": "fudan-xq-val-001",
                    "display_topic": "valuation_debate",
                    "claim": "外部观点认为A股估值处于乐观情景上沿",
                    "source_excerpt": excerpt,
                    "reasoning_steps": ["用紫光国微作盈利参照", "用2026净利和PE交叉验证"],
                    "numbers_used": ["375-420亿", "46-52元"],
                    "assumptions": ["2026净利修复到7.5亿"],
                    "counterpoints": ["军工订单恢复不及预期"],
                    "verification_need": "跟踪半年报和订单恢复",
                    "citation_refs": [1],
                }
            ],
        },
    }

    result = renderer.render(ctx)

    assert "**观点卡片：**" not in result
    assert "**观点**：外部观点认为A股估值处于乐观情景上沿" not in result
    assert "**推理步骤**：" not in result
    assert "**关键数字**：" not in result
    assert "外部材料提示估值分歧[^2]" in result
    assert "- [^2] 雪球专栏观察" in result


def test_curated_external_narrative_renders_flat_planned_paragraphs():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "synthesis": {
            "industry_logic": "baseline 产业逻辑[^1]",
            "fundamentals": "",
            "citations": {1: {"source": "研报", "title": "baseline title"}},
        },
        "deep_analysis_display": {
            "_curated_external_narrative": True,
            "_curated_external_narrative_paragraphs": [
                {
                    "topic": "supply_delivery_capacity",
                    "heading": "预付款与物料瓶颈",
                    "text": "外部材料提示上游材料预付款激增，可能反映磷化铟衬底与光芯片供应紧张。",
                    "citation_refs": [1],
                },
                {
                    "topic": "technology_route",
                    "heading": "NPO/XPO 技术路线",
                    "text": "外部材料提示 NPO/XPO 在 Scale-up 场景可能成为下一代互连增量。",
                    "citation_refs": [2],
                },
            ],
            "citations": {
                1: {
                    "source": "微信公众号精选观察",
                    "title": "上游材料预付款观察",
                    "source_type": "curated_external_analysis_evidence",
                },
                2: {
                    "source": "微信公众号精选观察",
                    "title": "NPO/XPO 外部分析",
                    "source_type": "curated_external_analysis_evidence",
                },
            },
        },
    }

    result = renderer.render(ctx)

    assert "### 4.4 精选外部观察（Preview）" in result
    assert "#### 4.4.1" not in result
    assert "#### 4.4.2" not in result
    assert "**预付款与物料瓶颈**" in result
    assert "磷化铟衬底与光芯片供应紧张[^2]" in result
    assert "**NPO/XPO 技术路线**" in result
    assert "下一代互连增量[^3]" in result
    assert result.index("预付款与物料瓶颈") < result.index("NPO/XPO 技术路线")
    assert "- [^2] 微信公众号精选观察" in result
    assert "- [^3] 微信公众号精选观察" in result


def test_curated_external_narrative_merges_duplicate_display_citations():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "synthesis": {
            "industry_logic": "baseline 产业逻辑[^1]",
            "citations": {1: {"source": "研报", "title": "baseline title"}},
        },
        "deep_analysis_display": {
            "_curated_external_narrative": True,
            "_curated_external_narrative_paragraphs": [
                {
                    "heading": "交付变量",
                    "text": "第一段引用同一篇外部文章。",
                    "citation_refs": [1],
                },
                {
                    "heading": "供应链变量",
                    "text": "第二段也引用同一篇外部文章。",
                    "citation_refs": [2],
                },
            ],
            "citations": {
                1: {
                    "source": "微信公众号精选观察",
                    "author": "作者A",
                    "title": "同一篇文章",
                    "url": "https://example.com/same",
                    "source_type": "curated_external_analysis_evidence",
                },
                2: {
                    "source": "微信公众号精选观察",
                    "author": "作者A",
                    "title": "同一篇文章",
                    "url": "https://example.com/same",
                    "source_type": "curated_external_analysis_evidence",
                },
            },
        },
    }

    result = renderer.render(ctx)
    local_sources = result.split("**本节引用来源：**", 1)[1].split("## 引用来源", 1)[0]

    assert "第一段引用同一篇外部文章[^2]" in result
    assert "第二段也引用同一篇外部文章[^2]" in result
    assert "第二段也引用同一篇外部文章[^3]" not in result
    assert local_sources.count("https://example.com/same") == 1
    assert "- [^2] 微信公众号精选观察" in local_sources
    assert "- [^3] 微信公众号精选观察" not in local_sources


def test_curated_external_narrative_dedupes_repeated_body_footnotes_after_merge():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "synthesis": {
            "industry_logic": "baseline 产业逻辑[^1]",
            "citations": {1: {"source": "研报", "title": "baseline title"}},
        },
        "deep_analysis_display": {
            "_curated_external_narrative": True,
            "_curated_external_narrative_paragraphs": [
                {
                    "heading": "供应链变量",
                    "text": "外部材料提示同一来源不应重复刷脚注。",
                    "citation_refs": [1, 1, 3, 1],
                },
            ],
            "citations": {
                1: {
                    "source": "微信公众号精选观察",
                    "author": "作者A",
                    "title": "同一篇文章",
                    "url": "https://example.com/same",
                    "source_type": "curated_external_analysis_evidence",
                },
                3: {
                    "source": "微信公众号精选观察",
                    "author": "作者A",
                    "title": "同一篇文章",
                    "url": "https://example.com/same",
                    "source_type": "curated_external_analysis_evidence",
                },
            },
        },
    }

    result = renderer.render(ctx)
    local_sources = result.split("**本节引用来源：**", 1)[1].split("## 引用来源", 1)[0]

    assert "外部材料提示同一来源不应重复刷脚注[^2]。" in result
    assert "[^2][^2]" not in result
    assert local_sources.count("https://example.com/same") == 1


def test_curated_external_topic_groups_keep_taxonomy_fallback():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "测试股",
        "synthesis": {
            "industry_logic": "baseline 产业逻辑[^1]",
            "citations": {1: {"source": "研报", "title": "baseline title"}},
        },
        "deep_analysis_display": {
            "_curated_external_topic_groups": {
                "order_capacity_delivery": [
                    {
                        "heading": "交付变量",
                        "text": "外部材料提示交付节奏仍需跟踪。",
                        "citation_refs": [1],
                    }
                ],
                "technology_route": [
                    {
                        "heading": "技术路线",
                        "text": "外部材料提示技术路线仍有分歧。",
                        "citation_refs": [2],
                    }
                ],
            },
            "citations": {
                1: {
                    "source": "微信公众号精选观察",
                    "title": "交付观察",
                    "source_type": "curated_external_analysis_evidence",
                },
                2: {
                    "source": "微信公众号精选观察",
                    "title": "技术观察",
                    "source_type": "curated_external_analysis_evidence",
                },
            },
        },
    }

    result = renderer.render(ctx)

    assert "### 4.4 外部观点与待验证变量（Preview）" in result
    assert "#### 4.4.1 订单、产能与交付节奏" in result
    assert "#### 4.4.2 产业链与技术路线分歧" in result
    assert "交付变量" in result
    assert "技术路线" in result


def test_curated_external_grouped_addendum_merges_duplicate_display_citations():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "测试股",
        "synthesis": {
            "industry_logic": "baseline 产业逻辑[^1]",
            "citations": {1: {"source": "研报", "title": "baseline title"}},
        },
        "deep_analysis_display": {
            "_curated_external_topic_groups": {
                "order_capacity_delivery": [
                    {
                        "heading": "交付变量",
                        "text": "第一条引用同一来源。",
                        "citation_refs": [1],
                    },
                    {
                        "heading": "供应链变量",
                        "text": "第二条也引用同一来源。",
                        "citation_refs": [2],
                    },
                ],
            },
            "citations": {
                1: {
                    "source": "微信公众号精选观察",
                    "author": "作者A",
                    "title": "同一篇文章",
                    "url": "https://example.com/same",
                    "source_type": "curated_external_analysis_evidence",
                },
                2: {
                    "source": "微信公众号精选观察",
                    "author": "作者A",
                    "title": "同一篇文章",
                    "url": "https://example.com/same",
                    "source_type": "curated_external_analysis_evidence",
                },
            },
        },
    }

    result = renderer.render(ctx)
    local_sources = result.split("**本节引用来源：**", 1)[1].split("## 引用来源", 1)[0]

    assert "第一条引用同一来源[^2]" in result
    assert "第二条也引用同一来源[^2]" in result
    assert "第二条也引用同一来源[^3]" not in result
    assert local_sources.count("https://example.com/same") == 1


def test_curated_external_unknown_topic_does_not_fall_into_market_expectation():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "测试股",
        "synthesis": {"industry_logic": "baseline", "citations": {}},
        "deep_analysis_display": {
            "_curated_external_narrative": True,
            "_curated_external_narrative_paragraphs": [
                {
                    "topic": "misc",
                    "heading": "泛泛观察",
                    "text": "外部材料只是描述行业背景，没有估值、股价、资金或情绪线索。",
                    "citation_refs": [1],
                }
            ],
            "citations": {
                1: {
                    "source": "微信公众号精选观察",
                    "title": "泛泛观察",
                    "source_type": "curated_external_analysis_evidence",
                }
            },
        },
    }

    result = renderer.render(ctx)

    assert "### 4.4 精选外部观察（Preview）" in result
    assert "#### 4.4.1 其他待验证观察" not in result
    assert "#### 4.4.1" not in result
    assert "资本市场预期与情绪温度" not in result
    assert "泛泛观察" in result


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
            "industry_logic": "enhanced 年报全文 行业逻辑[^1]。",
            "citations": {
                1: {
                    "source": "定期报告叙事卡片",
                    "title": "2025年年度报告",
                    "source_type": "periodic_report_narrative_card",
                }
            },
        },
        "core_facts": [],
    }
    result = renderer.render(ctx)
    assert "enhanced 年报全文 行业逻辑" in result
    assert "baseline 行业逻辑" not in result
    assert "定期报告叙事卡片" in result


def test_render_does_not_use_social_synthesis_display_for_main_analysis():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "baseline 正式源行业逻辑。",
            "citations": {
                1: {
                    "source": "研报",
                    "title": "正式研报",
                    "source_type": "broker_research",
                }
            },
        },
        "synthesis_display": {
            "industry_logic": "雪球/知乎 display 行业逻辑[^1]。",
            "citations": {
                1: {
                    "source": "知乎精选观察",
                    "title": "知乎观点",
                    "source_type": "social_viewpoint_analysis_evidence",
                }
            },
        },
        "core_facts": [],
    }

    result = renderer.render(ctx)

    assert "baseline 正式源行业逻辑" in result
    assert "雪球/知乎 display 行业逻辑" not in result
    assert "知乎精选观察" not in result


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
    assert "### 4.4 外部观点与待验证变量（Preview）" in result
    assert result.index("### 4.1 产业逻辑与竞争格局") < result.index("### 4.4 外部观点与待验证变量（Preview）")


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


def test_curated_external_addendum_includes_citation_url():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "synthesis": {
            "industry_logic": "baseline 产业逻辑。",
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "citations": {},
        },
        "deep_analysis_display": {
            "industry_logic": "精选外部材料仅作为专业观察，提示中际旭创产业线索：《外部标题》观察到内容[^1]",
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "citations": {
                1: {
                    "source": "微信公众号精选观察",
                    "author": "测试账号",
                    "title": "外部标题",
                    "url": "https://mp.weixin.qq.com/s/example",
                    "source_type": "curated_external_analysis_evidence",
                }
            },
        },
    }

    result = renderer.render(ctx)

    assert "### 4.4 外部观点与待验证变量（Preview）" in result
    assert "https://mp.weixin.qq.com/s/example" in result
    assert "[^1]" in result


def test_curated_external_narrative_addendum_renders_paragraphs_not_bullets():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "synthesis": {
            "industry_logic": "baseline 产业逻辑。",
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "citations": {},
        },
        "deep_analysis_display": {
            "_curated_external_narrative": True,
            "_curated_external_narrative_paragraphs": [
                {
                    "heading": "供应链瓶颈与交付疑虑并存",
                    "text": "外部材料提示供应链约束会影响交付弹性，需要和订单转化一起跟踪。",
                    "citation_refs": [1],
                }
            ],
            "citations": {
                1: {
                    "source": "微信公众号精选观察",
                    "author": "测试账号",
                    "title": "外部深度文章",
                    "url": "https://mp.weixin.qq.com/s/viewpoint",
                    "source_type": "curated_external_analysis_evidence",
                    "source_credit": 55,
                }
            },
        },
    }

    result = renderer.render(ctx)

    assert "### 4.4 精选外部观察（Preview）" in result
    assert "#### 4.4.1" not in result
    assert "**供应链瓶颈与交付疑虑并存**" in result
    assert "外部材料提示供应链约束会影响交付弹性" in result
    assert "- **供应链瓶颈与交付疑虑并存**" not in result
    assert "[^1]" in result
    assert "https://mp.weixin.qq.com/s/viewpoint" in result


def test_formal_rich_profile_renders_legacy_headings_and_badge():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "deep_analysis_evidence_profile": {
            "profile": "formal_rich",
            "formal_section_support": {"industry": 2, "fundamentals": 2, "funding_support": 1, "catalyst_support": 1},
        },
        "synthesis": {
            "industry_logic": "产业逻辑[^1]",
            "fundamentals": "基本面",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "citations": {1: {"source": "研报", "title": "测试"}},
        },
        "core_facts": [],
    }
    result = renderer.render(ctx)
    assert "<!-- deep_analysis_profile:" in result
    assert "深度分析形态：正式材料丰富" in result
    assert "### 4.1 产业逻辑与竞争格局" in result
    assert "### 4.2 业绩路径与多空分歧" in result
    assert "### 4.3 资金面与催化剂时间线" in result


def test_formal_thin_external_rich_profile_renders_new_layout():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "复旦微电",
        "deep_analysis_evidence_profile": {"profile": "formal_thin_external_rich"},
        "synthesis": {"industry_logic": "", "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": "", "citations": {}},
        "formal_financial_fact_pack": {
            "facts": [
                {"metric": "营业收入", "value": "39.82亿元"},
                {"metric": "归母净利润", "value": "2.32亿元，同比下降59.42%"},
            ],
        },
        "deep_analysis_display": {
            "industry_logic": "",
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "citations": {
                1: {"source": "微信公众号精选观察", "title": "测试外部", "source_type": "curated_external_analysis_evidence"},
            },
            "_curated_external_topic_groups": {
                "technology_route": [{"heading": "路线", "text": "外部观点A[^1]", "citation_refs": [1]}],
                "order_capacity_delivery": [{"heading": "交付", "text": "外部观点B[^1]", "citation_refs": [1]}],
                "financial_quality": [{"heading": "业绩", "text": "外部观点C[^1]", "citation_refs": [1]}],
            },
            "_curated_external_reasoning_cards": [
                {
                    "claim_id": "c1",
                    "claim": "外部观点A",
                    "assumptions": ["假设A"],
                    "counterpoints": ["反方A"],
                    "verification_need": "验证A",
                    "citation_refs": [1],
                },
            ],
        },
        "core_facts": [],
    }
    result = renderer.render(ctx)
    assert "深度分析形态：正式材料薄但外部观点丰富" in result
    assert "<!-- deep_analysis_profile:" in result
    assert "### 4.1 正式材料要点" in result
    assert "### 4.2 外部观点地图（Preview，不参与评分）" in result
    assert "### 4.3 待验证清单" in result
    assert "### 4.1 产业逻辑与竞争格局" not in result
    assert "### 4.2 业绩路径与多空分歧" not in result
    assert "### 4.3 资金面与催化剂时间线" not in result
    assert "外部材料称：外部观点A[^1]；该说法需以公告、财报拆分或行业第三方数据验证。" in result
    assert "| 变量 | 为什么重要 | 需要什么证据 | 来源层级 |" in result


def test_formal_thin_external_map_frames_claims_and_keeps_numbers():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "复旦微电",
        "deep_analysis_evidence_profile": {"profile": "formal_thin_external_rich"},
        "synthesis": {"industry_logic": "", "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": "", "citations": {}},
        "formal_financial_fact_pack": {"facts": [{"metric": "营业收入", "value": "39.82亿元"}]},
        "deep_analysis_display": {
            "citations": {
                1: {"source": "雪球专栏观察", "title": "测试外部", "source_type": "curated_external_analysis_evidence"},
            },
            "_curated_external_reasoning_cards": [
                {
                    "claim_id": "c1",
                    "claim": "国内高可靠卫星FPGA市占率95%以上；单星价值300-500万元",
                    "reasoning_steps": ["需核对95%口径"],
                    "counterpoints": ["官方未披露市占率"],
                    "verification_need": "需等待公告或第三方行业数据验证",
                    "citation_refs": [1],
                },
            ],
        },
        "core_facts": [],
    }

    result = renderer.render(ctx)

    assert "外部材料称：国内高可靠卫星FPGA市占率95%以上；单星价值300-500万元[^1]" in result
    assert "该说法需以公告、财报拆分或行业第三方数据验证" in result
    assert "95%" in result
    assert "300-500万元" in result


def test_thin_all_profile_renders_material_insufficient_layout():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "测试股",
        "deep_analysis_evidence_profile": {"profile": "thin_all"},
        "synthesis": {"industry_logic": "", "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": "", "citations": {}},
        "formal_financial_fact_pack": {"facts": [{"metric": "营业收入", "value": "10亿元"}]},
        "core_facts": [],
    }
    result = renderer.render(ctx)
    assert "深度分析形态：材料不足" in result
    assert "### 4.1 正式材料要点" in result
    assert "当前可用于深度基本面分析的正式材料不足" in result
    assert "### 4.2" not in result


def _annual_memo_fixture(status: str = "ready", forbidden_card: bool = False) -> dict:
    cards = [
        {
            "title": "主营业务与产品",
            "body": "公司增长主线来自 FPGA 与智能电表 MCU。",
            "internal_refs": ["annual:card:business_model:0"],
            "citation_refs": [1],
            "source_ref_ids": ["periodic_report_narrative_evidence:business_model:0"],
        },
        {
            "title": "研发与产品进展",
            "body": "新一代 FPGA 进入客户验证阶段。",
            "internal_refs": ["annual:card:rd_product_progress:0"],
            "citation_refs": [2],
            "source_ref_ids": ["periodic_report_narrative_evidence:rd_product_progress:0"],
        },
        {
            "title": "管理层市场判断",
            "body": "管理层认为工业与汽车电子需求保持韧性。",
            "internal_refs": ["annual:card:management_market_view:0"],
            "citation_refs": [3],
            "source_ref_ids": ["periodic_report_narrative_evidence:management_market_view:0"],
        },
        {
            "title": "营业收入",
            "body": "营业收入 39.82 亿元。",
            "internal_refs": ["fact:营业收入"],
            "citation_refs": [4],
            "source_ref_ids": ["periodic_report_filing_fact:revenue"],
        },
    ]
    if forbidden_card:
        cards.append({
            "title": "雪球观点",
            "body": "雪球上有人认为公司订单饱满。[^5]",
            "internal_refs": ["annual:card:forbidden:0"],
            "citation_refs": [5],
            "source_ref_ids": ["periodic_report_narrative_evidence:forbidden:0"],
        })
    return {
        "schema": "annual_report_memo.v1",
        "status": status,
        "source_layer": "annual_report",
        "sections": {
            "confirmed": [cards[3]],
            "annual_report_explanation": cards[:3],
            "not_disclosed": [{"title": "未充分披露项", "body": "重要客户、订单、产能、供应链、管理层指引或细分拆分未在正式材料中充分披露。", "internal_refs": [], "citation_refs": [], "source_ref_ids": []}],
            "inconclusive": [{"title": "不能下结论", "body": "不得用营收/利润推断主力资金或市场行为。", "internal_refs": [], "citation_refs": [], "source_ref_ids": []}],
        },
        "validation": {"warnings": [], "numeric_terms_checked": True, "unsupported_numbers": [], "strong_claims": []},
        "citations": {
            1: {"source": "公司年报", "title": "2025年度报告", "source_type": "periodic_report_narrative_evidence"},
            2: {"source": "公司年报", "title": "2025年度报告", "source_type": "periodic_report_narrative_evidence"},
            3: {"source": "公司年报", "title": "2025年度报告", "source_type": "periodic_report_narrative_evidence"},
            4: {"source": "公司年报", "title": "2025年度报告", "source_type": "periodic_report_filing_fact"},
            5: {"source": "雪球", "title": "雪球评论", "source_type": "social_media"},
        },
    }


def test_formal_thin_annual_memo_renders_sections():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "复旦微电",
        "deep_analysis_evidence_profile": {
            "profile": "formal_thin_external_rich",
            "formal_thin_layout_variant": "annual_broker_external_checklist",
        },
        "synthesis": {"industry_logic": "", "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": "", "citations": {}},
        "annual_report_memo": _annual_memo_fixture(),
        "deep_analysis_display": {
            "citations": {
                1: {"source": "微信公众号精选观察", "title": "测试外部", "source_type": "curated_external_analysis_evidence"},
            },
            "_curated_external_reasoning_cards": [
                {
                    "claim_id": "c1",
                    "claim": "外部观点A",
                    "assumptions": ["假设A"],
                    "counterpoints": ["反方A"],
                    "verification_need": "验证A",
                    "citation_refs": [1],
                },
            ],
        },
        "core_facts": [],
    }
    result = renderer.render(ctx)
    assert "### 4.1 年报经营摘要" in result
    assert "**已确认**" in result
    assert "**年报解释**" in result
    assert "**未披露 / 不能下结论**" in result
    assert "营业收入 39.82 亿元" in result
    assert "公司增长主线来自 FPGA" in result


def test_formal_thin_broker_absence_keeps_heading():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "复旦微电",
        "deep_analysis_evidence_profile": {
            "profile": "formal_thin_external_rich",
            "formal_thin_layout_variant": "annual_broker_external_checklist",
            "broker_memo_status": "absent",
        },
        "synthesis": {"industry_logic": "", "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": "", "citations": {}},
        "annual_report_memo": _annual_memo_fixture(),
        "deep_analysis_display": {
            "citations": {},
            "_curated_external_reasoning_cards": [],
        },
        "core_facts": [],
    }
    result = renderer.render(ctx)
    assert "### 4.2 研报观点与假设" in result
    assert "当前未取得足够可用研报 digest，不展开研报观点与假设" in result
    assert "### 4.3 外部观点地图（Preview，不参与评分）" in result
    assert "### 4.4 待验证清单" in result


def test_annual_memo_rows_render_citation_refs():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "复旦微电",
        "deep_analysis_evidence_profile": {
            "profile": "formal_thin_external_rich",
            "formal_thin_layout_variant": "annual_broker_external_checklist",
        },
        "synthesis": {"industry_logic": "", "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": "", "citations": {}},
        "annual_report_memo": _annual_memo_fixture(),
        "deep_analysis_display": {
            "citations": {},
            "_curated_external_reasoning_cards": [],
        },
        "core_facts": [],
    }
    result = renderer.render(ctx)
    assert "[^1]" in result
    assert "[^4]" in result
    assert "- [^1] 公司年报" in result or "- [^4] 公司年报" in result


def test_annual_memo_unavailable_renders_fallback_no_legacy():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "复旦微电",
        "deep_analysis_evidence_profile": {
            "profile": "formal_thin_external_rich",
            "formal_thin_layout_variant": "annual_broker_external_checklist",
        },
        "synthesis": {"industry_logic": "", "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": "", "citations": {}},
        "annual_report_memo": {
            "schema": "annual_report_memo.v1",
            "status": "absent",
            "source_layer": "annual_report",
            "sections": {"confirmed": [], "annual_report_explanation": [], "not_disclosed": [], "inconclusive": []},
            "validation": {"warnings": [], "numeric_terms_checked": True, "unsupported_numbers": [], "strong_claims": []},
            "citations": {},
        },
        "deep_analysis_display": {
            "citations": {},
            "_curated_external_reasoning_cards": [],
        },
        "core_facts": [],
    }
    result = renderer.render(ctx)
    assert "### 4.1 年报经营摘要" in result
    assert "当前未取得足够年报材料" in result
    assert "### 4.1 产业逻辑与竞争格局" not in result
    assert "### 4.2 业绩路径与多空分歧" not in result
    assert "### 4.3 资金面与催化剂时间线" not in result


def test_formal_rich_keeps_legacy_headings():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "deep_analysis_evidence_profile": {"profile": "formal_rich"},
        "synthesis": {
            "industry_logic": "产业逻辑[^1]",
            "fundamentals": "基本面",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "citations": {1: {"source": "公告", "title": "年报"}},
        },
        "annual_report_memo": _annual_memo_fixture(),
        "core_facts": [],
    }
    result = renderer.render(ctx)
    assert "### 4.1 产业逻辑与竞争格局" in result
    assert "### 4.2 业绩路径与多空分歧" in result
    assert "### 4.3 资金面与催化剂时间线" in result
    assert "### 4.1 年报经营摘要" not in result


def test_formal_rich_does_not_emit_unused_annual_memo_citations():
    renderer = DeepAnalysisRenderer()
    memo = _annual_memo_fixture()
    memo["citations"][1]["title"] = "Annual Memo Only Source"
    ctx = {
        "stock_name": "中际旭创",
        "deep_analysis_evidence_profile": {"profile": "formal_rich"},
        "synthesis": {
            "industry_logic": "产业逻辑[^1]",
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "citations": {1: {"source": "公告", "title": "正式引用"}},
        },
        "annual_report_memo": memo,
        "core_facts": [],
    }
    result = renderer.render(ctx)

    assert "Annual Memo Only Source" not in result
    assert "公司增长主线来自 FPGA" not in result


def test_formal_rich_sanitizes_pe_spread_in_deep_analysis_table():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "deep_analysis_evidence_profile": {"profile": "formal_rich"},
        "peer_comparison_material": {
            "rows": [
                {
                    "metric": "pe_ttm",
                    "peer": "新易盛",
                    "target_value": 83.26,
                    "peer_value": 68.29,
                }
            ]
        },
        "synthesis": {
            "industry_logic": "| 指标 | 中际旭创 | 对标 | 结论 |\n|---|---|---|---|\n| PE(TTM) | 83.26倍 | 新易盛PE TTM 68.29倍 | PE(TTM)高于新易盛约15倍 |",
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "citations": {},
        },
        "core_facts": [],
    }
    result = renderer.render(ctx)

    assert "高于新易盛约15倍" not in result
    assert "新易盛为 68.29 倍" in result
    assert "个 PE 倍数点" in result


def test_annual_memo_rejects_forbidden_source():
    renderer = DeepAnalysisRenderer()
    memo = _annual_memo_fixture(forbidden_card=True)
    ctx = {
        "stock_name": "复旦微电",
        "deep_analysis_evidence_profile": {
            "profile": "formal_thin_external_rich",
            "formal_thin_layout_variant": "annual_broker_external_checklist",
        },
        "synthesis": {"industry_logic": "", "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": "", "citations": {}},
        "annual_report_memo": memo,
        "deep_analysis_display": {
            "citations": {},
            "_curated_external_reasoning_cards": [],
        },
        "core_facts": [],
    }
    result = renderer.render(ctx)
    assert "雪球上有人认为" not in result
    # The forbidden card should not be in annual_report_explanation rows.
    assert any("雪球" in str(r.get("body", "")) for r in memo["sections"]["annual_report_explanation"]) is False
