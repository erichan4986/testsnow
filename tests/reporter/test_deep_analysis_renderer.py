"""Tests for DeepAnalysisRenderer."""

import re

import pytest
from scripts.utils.deep_analysis_material_snapshot import (
    MaterialRow,
    build_chapter4_view_model,
    build_deep_analysis_material_snapshot,
    select_annual_display_rows,
)
from scripts.utils.reporter.sections import DeepAnalysisRenderer, ExecutiveSummaryRenderer


def _test_external_family(text: str, title: str = "") -> str:
    value = f"{title} {text}"
    if re.search(r"供给|供应|交付|预付款|订单", value):
        return "capacity_delivery"
    if re.search(r"技术|产品|FPGA|NPO|XPO|芯片", value, re.I):
        return "technology_product"
    if re.search(r"客户|需求|市场", value):
        return "demand_customer"
    if re.search(r"收入|利润|毛利率|财务", value):
        return "financial_quality"
    return "other"


def _external_argument_row(claim, evidence, *, ref=None, refs=None, key, title="外部待验证变量"):
    citation_refs = list(refs if refs is not None else [ref])
    family = _test_external_family(claim, title)
    return {
        "schema_version": "curated_external_argument_card.v3",
        "argument_key": key,
        "entity_scope": "target",
        "coverage_families": [family],
        "primary_family": family,
        "evidence_units": [{
            "source_unit_id": f"unit:{key}",
            "text": evidence,
            "evidence_status": "source_unit_verified",
            "citation_refs": citation_refs,
        }],
        "citation_refs": citation_refs,
    }




def _render(renderer, ctx):
    return renderer.render(ctx)


def test_required_keys():
    renderer = DeepAnalysisRenderer()
    assert renderer.required_keys() == ["stock_name", "synthesis"]


def test_render_missing_keys():
    renderer = DeepAnalysisRenderer()
    assert renderer.render({}) == ""
    assert renderer.render({"stock_name": "Test"}) == ""


def test_visible_citations_keep_reserved_executive_summary_refs():
    citations = {
        1: {"source": "年报"},
        2: {"source": "外部观察"},
        3: {"source": "未使用"},
    }
    visible = DeepAnalysisRenderer._visible_citations_only(
        citations, "正文[^1]", reserved_refs=(2,)
    )
    assert set(visible) == {1, 2}


def test_alias_offset_citation_by_identity_only():
    renderer = DeepAnalysisRenderer()
    text = "外部变量[^12]；其他材料[^13]"
    aliases = {
        12: {"source": "外部观察", "url": "https://example.com/a"},
        13: {"source": "其他", "url": "https://example.com/b"},
    }
    reserved = {
        4: {"source": "外部观察", "url": "https://example.com/a"},
    }
    assert renderer._alias_reserved_citations(text, aliases, reserved) == "外部变量[^4]；其他材料[^13]"


def test_external_variable_preface_is_only_added_when_freshness_gate_allows_it():
    renderer = DeepAnalysisRenderer()
    row = MaterialRow(
        "external:1", "外部材料称订单节奏需跟踪。", "external", "external_observation",
        (1,), (), title="订单变量", body="外部材料称订单节奏需跟踪。", render_role="external_variable",
    )
    with_preface = renderer._formal_medium_external_variable_map(
        (row,), {1: {"source": "微信公众号精选观察"}}, preface=True,
    )
    without_preface = renderer._formal_medium_external_variable_map(
        (row,), {1: {"source": "微信公众号精选观察"}}, preface=False,
    )
    assert any("正式材料的时间点较早" in line for line in with_preface)
    assert not any("正式材料的时间点较早" in line for line in without_preface)


def test_external_argument_v2_renders_delta_and_full_evidence_without_truncation():
    renderer = DeepAnalysisRenderer()
    evidence = "外部文章记录上游物料供应偏紧，并列出客户认证、交付安排和公司回应的完整上下文。"
    rows = (
        MaterialRow(
            "external:argument_cards_v2:0", "交付变量", "external", "external_observation", (1,), (),
            title="供应链交付", body="中际旭创800G交付节奏仍需验证。", render_role="external_variable",
            external_claim="中际旭创800G交付节奏仍需验证。", external_evidence=evidence,
            evidence_status="source_quote_verified", owner_relation="owner_delta", argument_key="delivery",
        ),
        MaterialRow(
            "external:argument_cards_v2:1", "行业变量", "external", "external_observation", (2,), (),
            title="同业路线", body="同业NPO路线进入验证窗口。", render_role="external_variable",
            external_claim="同业NPO路线进入验证窗口。", external_evidence="缓存文章讨论同业验证节奏。",
            evidence_status="cached_excerpt", owner_relation="outside_owner", argument_key="peer-route",
        ),
    )

    rendered = "\n".join(renderer._formal_medium_external_variable_map(
        rows, {1: {"source": "微信公众号精选观察"}, 2: {"source": "知乎精选观察"}},
        disclaimer="仅作观察。",
    ))

    assert "相对正式材料/机构假设，外部材料新增的待验证点：中际旭创800G交付节奏仍需验证[^1]。" in rendered
    assert "外部新增待验证变量：同业NPO路线进入验证窗口[^2]。" in rendered
    assert f"> **外部原文依据**：{evidence}" in rendered
    assert "> **缓存材料摘录**：缓存文章讨论同业验证节奏。" in rendered
    assert "..." not in rendered


def test_external_variable_map_separates_and_orders_peer_industry_background():
    renderer = DeepAnalysisRenderer()
    rows = (
        MaterialRow(
            "external:peer", "行业竞争格局加速分化。", "external", "external_observation", (2,), (),
            title="竞争格局", body="行业竞争格局加速分化。", render_role="external_variable",
            external_claim="行业竞争格局加速分化。", evidence_status="source_unit_verified",
            entity_scope="peer_or_industry", argument_key="peer",
        ),
        MaterialRow(
            "external:target", "测试股产品完成客户导入。", "external", "external_observation", (1,), (),
            title="客户导入", body="测试股产品完成客户导入。", render_role="external_variable",
            external_claim="测试股产品完成客户导入。", evidence_status="source_unit_verified",
            entity_scope="target", argument_key="target",
        ),
    )

    rendered = "\n".join(renderer._formal_medium_external_variable_map(
        rows, {1: {"source": "外部A"}, 2: {"source": "外部B"}}, disclaimer="仅作观察。",
    ))

    assert rendered.index("测试股产品完成客户导入") < rendered.index("同业/行业背景（Preview）")
    assert rendered.index("同业/行业背景（Preview）") < rendered.index("行业竞争格局加速分化")
    assert "同业/行业背景观察：行业竞争格局加速分化" in rendered
    assert "#### 同业/行业背景（Preview）" not in rendered
    assert "> **同业/行业背景（Preview）**：" in rendered


def test_external_variable_map_groups_topics_within_each_entity_scope():
    renderer = DeepAnalysisRenderer()
    rows = (
        MaterialRow(
            "external:tech-1", "目标技术一。", "external", "external_observation", (11,), (),
            title="技术与产品", body="目标技术一。", render_role="external_variable",
            evidence_status="source_unit_verified", entity_scope="target", argument_key="tech-1",
        ),
        MaterialRow(
            "external:financial", "目标财务。", "external", "external_observation", (12,), (),
            title="财务质量", body="目标财务。", render_role="external_variable",
            evidence_status="source_unit_verified", entity_scope="target", argument_key="financial",
        ),
        MaterialRow(
            "external:tech-2", "目标技术二。", "external", "external_observation", (13,), (),
            title="技术与产品", body="目标技术二。", render_role="external_variable",
            evidence_status="source_unit_verified", entity_scope="target", argument_key="tech-2",
        ),
        MaterialRow(
            "external:peer-tech", "同业技术。", "external", "external_observation", (14,), (),
            title="技术与产品", body="同业技术。", render_role="external_variable",
            evidence_status="source_unit_verified", entity_scope="peer_or_industry", argument_key="peer-tech",
        ),
    )

    rendered = "\n".join(renderer._formal_medium_external_variable_map(
        rows,
        {ref: {"source": "外部观察"} for ref in range(11, 15)},
        citation_offset=20,
        disclaimer="仅作观察。",
    ))
    target, peer = rendered.split("> **同业/行业背景（Preview）**", 1)

    assert target.count("**技术与产品**") == 1
    assert target.count("**财务质量**") == 1
    assert target.index("目标技术一[^31]") < target.index("目标技术二[^33]")
    assert target.index("目标技术二[^33]") < target.index("**财务质量**")
    assert peer.count("**技术与产品**") == 1
    assert "同业/行业背景观察：同业技术[^34]" in peer


def test_verified_external_multiline_unit_keeps_inline_refs_on_each_paragraph():
    renderer = DeepAnalysisRenderer()
    row = MaterialRow(
        "external:multiline", "业绩原因", "external", "external_observation", (7,), (),
        title="财务质量", body="收入与毛利均实现增长。\n同时，公司持续推进产品迭代并形成贡献。",
        render_role="external_variable", evidence_status="source_unit_verified",
        entity_scope="target", argument_key="financial-quality",
    )

    rendered = "\n".join(renderer._formal_medium_external_variable_map(
        (row,), {7: {"source": "外部观察"}}, disclaimer="仅作观察。",
    ))

    assert "外部新增待验证变量：收入与毛利均实现增长[^7]。" in rendered
    assert "同时，公司持续推进产品迭代并形成贡献[^7]。" in rendered


def test_annual_portrait_prefers_a_complete_sentence():
    renderer = DeepAnalysisRenderer()
    rows = [
        {"body": "公司主营业务为高端光通信收发模块，为客户提供低成"},
        {"body": "公司主营业务为高端光通信收发模块，服务云计算数据中心客户"},
    ]

    assert renderer._select_annual_portrait_row(rows) == rows[1]


def test_annual_portrait_requires_company_scope():
    renderer = DeepAnalysisRenderer()
    narrow = {"body": "公司NFC产品广泛应用于金融POS、智能门锁和门禁等市场。"}
    company = {"body": "公司主营业务为芯片设计，并为多个行业客户提供产品与系统解决方案。"}

    assert renderer._select_annual_portrait_row([narrow]) is None
    assert renderer._select_annual_portrait_row([narrow, company]) == company


def test_annual_portrait_accepts_company_product_matrix_without_terminal_punctuation():
    renderer = DeepAnalysisRenderer()
    matrix = {
        "body": "在子系列产品基础上，公司开发了FPGA、RF-FPGA、PSoC、RFSoC、FPAI等多个系列产品类型，逻辑资源从50K至4000K，算力从4TOPS至128TOPS，广泛应用于工业控制、测试测量、电力能源、消费电子、音视频、人工智能、卫星通信以及高可靠等领域，为客户提供低成本、低功耗、高性能、高可靠性的多元产品矩阵，全面匹配多样化应用需求。安全与识别产品线拥有多个芯片方向，是国内领先供应商",
    }

    assert renderer._select_annual_portrait_row([matrix]) == matrix


def test_annual_portrait_falls_back_after_an_ineligible_business_pool():
    renderer = DeepAnalysisRenderer()
    rows = (
        MaterialRow("annual:narrow", "公司NFC产品广泛应用于门禁市场。", "annual", "formal_explanation", (1,), ("annual:narrow",), body="公司NFC产品广泛应用于门禁市场。", render_role="business_structure"),
        MaterialRow("annual:operating", "报告期内，公司主营业务覆盖芯片设计、测试及系统解决方案。", "annual", "formal_explanation", (2,), ("annual:operating",), body="报告期内，公司主营业务覆盖芯片设计、测试及系统解决方案。", render_role="operating_progress"),
    )

    rendered = "\n".join(renderer._annual_material_profile_section(
        rows,
        {1: {"source": "公司年报"}, 2: {"source": "公司年报"}},
        fallback="无材料",
    ))
    portrait = rendered.split("**一句话画像**", 1)[1].split("**业务结构**", 1)[0]

    assert "主营业务覆盖芯片设计、测试及系统解决方案" in portrait


def test_compact_annual_text_never_cuts_an_over_limit_sentence():
    sentence = "公司主营业务为高端光通信收发模块的研发、生产及销售，" + "产品服务于云计算数据中心、数据通信和电信传输客户，" * 5 + "形成稳定合作关系。"

    assert len(sentence) > 140
    assert DeepAnalysisRenderer._compact_annual_text(sentence, 140) == sentence.rstrip("。")


def test_annual_profile_dedupes_rows_that_compact_to_the_same_visible_sentence():
    renderer = DeepAnalysisRenderer()
    sentence = "公司主营业务为高端光通信收发模块研发、生产及销售，产品服务于云计算数据中心客户。"
    long_tail = "同时，公司持续布局下一代高速产品并扩大研发投入，" + "推进产品验证、客户导入、产能建设、供应链协同和海外交付能力提升，" * 4 + "形成长期竞争力。"
    rows = (
        MaterialRow("annual:business", sentence, "annual", "formal_explanation", (1,), ("annual:business",), title="业务结构", body=sentence, render_role="business_structure", source_credit="official"),
        MaterialRow("annual:market", sentence + long_tail, "annual", "formal_explanation", (2,), ("annual:market",), title="经营变化", body=sentence + long_tail, render_role="market_competition_outlook", source_credit="official"),
    )

    rendered = "\n".join(renderer._annual_material_profile_section(
        rows,
        {1: {"source": "公司年报", "title": "业务"}, 2: {"source": "公司年报", "title": "经营"}},
        fallback="无材料",
    ))

    assert rendered.count(sentence.rstrip("。")) == 1


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
    result = _render(renderer, ctx)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "## 四、深度分析" in result
    assert "4.1 产业逻辑与竞争格局" in result


def test_render_embeds_material_coverage_diagnostics_comment():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "TestStock",
        "synthesis": {
            "industry_logic": "行业逻辑内容。",
            "fundamentals": "基本面内容。",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "citations": {},
        },
        "deep_analysis_material_coverage": {
            "annual": {"narrative_cards_seen": 10, "narrative_cards_selected": 4},
            "broker": {"raw_report_count": 3, "memo_usable_card_count": 2},
            "external": {"citation_source_count": 2},
        },
    }

    result = _render(renderer, ctx)

    assert "<!-- deep_analysis_material_coverage:" in result
    assert '"raw_report_count": 3' in result
    assert "narrative_cards_seen" not in result.split("<!-- deep_analysis_material_coverage:", 1)[0]


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

    result = _render(renderer, ctx)

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

    result = _render(renderer, ctx)

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

    result = _render(renderer, ctx)

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
            "_curated_external_argument_cards": [
                _external_argument_row(
                    "外部材料提示 800G 需求增长。",
                    "800G需求增长。",
                    ref=1,
                    key="demand:800g",
                )
            ],
            "citations": {
                1: {
                    "source": "微信公众号精选观察",
                    "title": "中际旭创外部观察标题",
                    "source_type": "curated_external_analysis_evidence",
                }
            },
        },
    }

    result = _render(renderer, ctx)

    assert "### 4.1 产业逻辑与竞争格局" in result
    assert "baseline 产业逻辑[^1]" in result
    assert "### 4.4 外部观点与待验证变量（Preview）" in result
    assert "800G需求增长[^2]" in result
    assert result.index("baseline 产业逻辑") < result.index("### 4.4 外部观点与待验证变量（Preview）")
    assert "不直接形成估值结论" not in result
    assert "- [^1] 雪球" in result
















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
    result = _render(renderer, ctx)
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
    result = _render(renderer, ctx)
    assert "| # | 事实 | 数据/来源 | 证据 | 置信度 |" in result
    assert "雪球、研报 (mixed)" in result


def test_render_old_style_fact_omits_missing_ref_from_core_base():
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
    result = _render(renderer, ctx)
    assert "营收增长" in result
    assert "毛利提升" not in result
    assert "未绑定引用 (unknown)" not in result


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
    result = _render(renderer, ctx)
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
    result = _render(renderer, ctx)
    assert "雪球 (community, 部分引用无效)" in result


def test_render_invalid_ref_omitted_from_core_base():
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
    result = _render(renderer, ctx)
    assert "营收增长" in result
    assert "毛利提升" not in result
    assert "引用无效 (unknown)" not in result


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

    result = _render(renderer, ctx)

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

    result = _render(renderer, ctx)

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

    result = _render(renderer, ctx)

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

    result = _render(renderer, ctx)
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

    result = _render(renderer, ctx)

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

    result = _render(renderer, ctx)

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

    result = _render(renderer, ctx)

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

    result = _render(renderer, ctx)

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

    result = _render(renderer, ctx)
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
    result = _render(renderer, ctx)
    assert "## 三、核心事实基座" in result
    assert "当前未形成可由高信用来源支撑的核心事实基座" in result
    assert "| # | 事实 | 数据/来源 | 证据 | 置信度 |" not in result
    assert "引用无效 (unknown)" not in result


def test_render_core_facts_mixed_invalid_omits_unsupported_rows():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "圣邦股份",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "core_facts": [
            {"fact_id": 1, "fact": "营收增长", "data": "10%", "confidence": "高", "provenance_status": "supported", "source_labels": ["公告"], "evidence_type": "official"},
            {"fact_id": 2, "fact": "毛利提升", "data": "51%", "confidence": "高", "provenance_status": "invalid_ref"},
        ],
    }
    result = _render(renderer, ctx)
    assert "| # | 事实 | 数据/来源 | 证据 | 置信度 |" in result
    assert "营收增长" in result
    assert "毛利提升" not in result
    assert "引用无效 (unknown)" not in result


def test_render_claim_summary_uses_neutral_title():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中简科技",
        "synthesis": {"industry_logic": "行业逻辑。", "citations": {}},
        "claim_verification_summary": {
            "verified": [{"claim_text": "营收下降", "status": "verified", "verified_by_titles": ["公告"], "confidence": 84}],
        },
    }
    result = _render(renderer, ctx)
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
    result = _render(renderer, ctx)
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
    result = _render(renderer, ctx)
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

    result = _render(renderer, ctx)

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
    result = _render(renderer, ctx)
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
    result = _render(renderer, ctx)
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
            "_curated_external_argument_cards": [
                _external_argument_row(
                    "外部材料提示需求仍待验证。",
                    "微信观察内容。",
                    ref=1,
                    key="demand:wechat",
                )
            ],
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

    result = _render(renderer, ctx)

    assert "精选外部材料仅作为专业观察" in result
    assert "不参与评分、风险评分或最终建议" in result
    assert "baseline 行业逻辑" in result
    assert "### 4.4 外部观点与待验证变量（Preview）" in result
    assert result.index("### 4.1 产业逻辑与竞争格局") < result.index("### 4.4 外部观点与待验证变量（Preview）")


def test_formal_rich_v3_addendum_renders_exact_evidence_and_deduped_source():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "测试股",
        "deep_analysis_evidence_profile": {"profile": "formal_rich"},
        "synthesis": {
            "industry_logic": "正式材料基线。",
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "citations": {},
        },
        "deep_analysis_display": {
            "_curated_external_argument_cards": [
                _external_argument_row(
                    "外部材料称交付节奏仍需验证。",
                    "外部文章记录上游供给偏紧。",
                    ref=1,
                    key="delivery:one",
                ),
                _external_argument_row(
                    "外部材料称客户验证节奏仍需观察。",
                    "同一文章记录客户验证进展。",
                    ref=2,
                    key="delivery:two",
                ),
            ],
            "citations": {
                1: {"source": "微信公众号精选观察", "title": "同一文章", "url": "https://example.com/shared", "source_type": "curated_external_analysis_evidence"},
                2: {"source": "微信公众号精选观察", "title": "同一文章", "url": "https://example.com/shared", "source_type": "curated_external_analysis_evidence"},
            },
        },
        "core_facts": [],
    }

    result = _render(renderer, ctx)

    assert "### 4.4 外部观点与待验证变量（Preview）" in result
    assert "**供应链与交付**" in result
    assert "上游供给偏紧" in result
    assert "外部原文依据" not in result
    local_sources = result.split("**本节引用来源：**", 1)[1].split("## 引用来源", 1)[0]
    assert local_sources.count("https://example.com/shared") == 1


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
    result = _render(renderer, ctx)
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
            "_curated_external_argument_cards": [
                _external_argument_row(
                    "外部材料提示供应链交付仍待验证。",
                    "《外部标题》观察到内容。",
                    ref=1,
                    key="delivery:url",
                )
            ],
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

    result = _render(renderer, ctx)

    assert "### 4.4 外部观点与待验证变量（Preview）" in result
    assert "https://mp.weixin.qq.com/s/example" in result
    assert "[^1]" in result


def test_curated_external_addendum_separates_peer_background_after_target_cards():
    renderer = DeepAnalysisRenderer()
    target = _external_argument_row(
        "测试股产品完成客户导入。", "测试股产品完成客户导入。", ref=1, key="target",
    )
    peer = _external_argument_row(
        "行业竞争格局加速分化。", "行业竞争格局加速分化。", ref=2, key="peer",
    )
    peer["entity_scope"] = "peer_or_industry"
    display = {
        "_curated_external_argument_cards": [peer, target],
        "citations": {
            1: {"source": "微信公众号精选观察", "title": "目标观察", "source_type": "curated_external_analysis_evidence"},
            2: {"source": "微信公众号精选观察", "title": "行业观察", "source_type": "curated_external_analysis_evidence"},
        },
    }

    rendered = renderer._curated_external_addendum(display)

    assert rendered.index("测试股产品完成客户导入") < rendered.index("同业/行业背景（Preview）")
    assert rendered.index("同业/行业背景（Preview）") < rendered.index("行业竞争格局加速分化")




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
    result = _render(renderer, ctx)
    assert "<!-- deep_analysis_profile:" in result
    assert "深度分析形态：正式材料丰富" in result
    assert "### 4.1 产业逻辑与竞争格局" in result
    assert "### 4.2 业绩路径与多空分歧" in result
    assert "### 4.3 资金面与催化剂时间线" in result






















def test_thin_all_profile_renders_material_insufficient_layout():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "测试股",
        "deep_analysis_evidence_profile": {"profile": "thin_all"},
        "synthesis": {"industry_logic": "", "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": "", "citations": {}},
        "formal_financial_fact_pack": {"facts": [{"metric": "营业收入", "value": "10亿元"}]},
        "core_facts": [],
    }
    result = _render(renderer, ctx)
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
            "argument_family": "business_structure",
            "argument_complete": True,
        },
        {
            "title": "研发与产品进展",
            "body": "新一代 FPGA 进入客户验证阶段。",
            "internal_refs": ["annual:card:rd_product_progress:0"],
            "citation_refs": [2],
            "source_ref_ids": ["periodic_report_narrative_evidence:rd_product_progress:0"],
            "argument_family": "technology_product_progress",
            "argument_complete": True,
        },
        {
            "title": "管理层市场判断",
            "body": "管理层认为工业与汽车电子需求保持韧性。",
            "internal_refs": ["annual:card:management_market_view:0"],
            "citation_refs": [3],
            "source_ref_ids": ["periodic_report_narrative_evidence:management_market_view:0"],
            "argument_family": "market_competition_outlook",
            "argument_complete": True,
        },
        {
            "title": "营业收入",
            "body": "营业收入 39.82 亿元。",
            "internal_refs": ["fact:营业收入"],
            "citation_refs": [4],
            "source_ref_ids": ["periodic_report_filing_fact:revenue"],
            "argument_family": "financial_quality_explanation",
            "argument_complete": False,
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


def test_formal_thin_v3_external_evidence_keeps_full_snapshot_citation_offset():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "复旦微电",
        "deep_analysis_evidence_profile": {"profile": "formal_thin_external_rich"},
        "synthesis": {"industry_logic": "", "fundamentals": "", "citations": {}},
        "annual_report_memo": _annual_memo_fixture(),
        "broker_research_memo": {"status": "absent", "citations": {}},
        "deep_analysis_display": {
            "_curated_external_argument_cards": [
                _external_argument_row(
                    "外部材料提示 FPGA 2026Q3 客户验证仍需观察。",
                    "外部文章记录 FPGA 2026Q3 客户验证节奏仍待确认。",
                    ref=1,
                    key="technology:validation",
                )
            ],
            "citations": {
                1: {
                    "source": "微信公众号精选观察",
                    "title": "FPGA 客户验证观察",
                    "source_type": "curated_external_analysis_evidence",
                }
            },
        },
        "core_facts": [],
    }

    result = _render(renderer, ctx)

    assert "### 4.3 外部观点与待验证变量（Preview，不参与评分）" in result
    assert "FPGA 2026Q3 客户验证节奏仍待确认[^5]" in result
    assert "[^5] | **微信公众号精选观察** | 《FPGA 客户验证观察》" in result
























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
    result = _render(renderer, ctx)
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
    result = _render(renderer, ctx)

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
    result = _render(renderer, ctx)

    assert "高于新易盛约15倍" not in result
    assert "新易盛为 68.29 倍" in result
    assert "个 PE 倍数点" in result


def test_formal_rich_sanitizes_forward_pe_and_ps_spread_in_deep_analysis_table():
    renderer = DeepAnalysisRenderer()
    ctx = {
        "stock_name": "中际旭创",
        "deep_analysis_evidence_profile": {"profile": "formal_rich"},
        "peer_comparison_material": {
            "rows": [
                {
                    "metric": "forward_pe",
                    "peer": "新易盛",
                    "target_value": 43.1174,
                    "peer_value": 34.6546,
                },
                {
                    "metric": "ps",
                    "peer": "新易盛",
                    "target_value": 63.5344,
                    "peer_value": 79.1244,
                },
            ]
        },
        "synthesis": {
            "industry_logic": (
                "| 指标 | 中际旭创 | 对标 | 结论 |\n"
                "|---|---|---|---|\n"
                "| Forward PE | 43.1倍 | 新易盛34.7倍 | Forward PE高于新易盛约8.5倍 |\n"
                "| PS | 63.5倍 | 新易盛79.1倍 | PS(市销率)低于新易盛约15.6倍 |"
            ),
            "fundamentals": "",
            "valuation_debate": "",
            "funding_sentiment": "",
            "events_catalysts": "",
            "citations": {},
        },
        "core_facts": [],
    }

    result = _render(renderer, ctx)

    assert "Forward PE高于新易盛约8.5倍" not in result
    assert "PS(市销率)低于新易盛约15.6倍" not in result
    assert "中际旭创 Forward PE 为 43.12 倍，新易盛为 34.65 倍，高出约 8.5 个 Forward PE 倍数点" in result
    assert "中际旭创 PS(市销率) 为 63.53 倍，新易盛为 79.12 倍，低约 15.6 个 PS 倍数点" in result


























def test_annual_portrait_selection_uses_generic_company_scope_not_chip_keywords():
    renderer = DeepAnalysisRenderer()
    rows = [
        {"body": "光模块、FPGA、安全与识别、智能电表产品线介绍。"},
        {"body": "公司从事精密设备设计、开发、测试，并提供系统解决方案，面向多个行业客户。"},
    ]

    portrait = renderer._select_annual_portrait_row(rows)

    assert portrait["body"].startswith("公司从事精密设备")


def test_annual_selector_preserves_business_prefix_before_mode_noise():
    row = MaterialRow(
        row_id="annual:business-mode",
        text="主营业务与产品：公司提供工业控制设备并服务大型制造客户，经营模式包括直销和经销。",
        source_layer="annual",
        claim_status="formal_explanation",
        citation_refs=(1,),
        source_ref_ids=("annual:business-mode",),
        title="主营业务与产品",
        body="公司提供工业控制设备并服务大型制造客户，经营模式包括直销和经销。",
        render_role="business_structure",
        source_credit="official",
    )

    selected, _ = select_annual_display_rows((row,))

    assert len(selected) == 1
    assert selected[0].body == "公司提供工业控制设备并服务大型制造客户"
















def test_external_claim_blocks_keep_all_boundary_units_and_citations():
    lines = []
    claim = "外部材料称：第一句。第二句；第三句。第四句；第五句。[^4][^5]"

    DeepAnalysisRenderer._append_external_variable_paragraph(lines, "变量", claim)

    blocks = [line for line in lines if "[^4][^5]" in line]
    assert blocks == [
        "外部材料称：第一句。第二句；第三句。[^4][^5]",
        "外部材料称：第四句；第五句。[^4][^5]",
    ]
    assert all(block.startswith("外部材料称：") for block in blocks)
    assert "".join(block.replace("外部材料称：", "").replace("[^4][^5]", "") for block in blocks) == claim.replace("外部材料称：", "").replace("[^4][^5]", "")


def test_external_claim_blocks_drop_only_exact_duplicate_boundary_units():
    lines = []
    claim = "外部材料称：相同判断。独立证据；相同判断。进一步验证。[^9]"

    DeepAnalysisRenderer._append_external_variable_paragraph(lines, "变量", claim)

    blocks = [line for line in lines if "[^9]" in line]
    rendered = "".join(block.replace("外部材料称：", "").replace("[^9]", "") for block in blocks)
    assert blocks == [
        "外部材料称：相同判断。独立证据；进一步验证。[^9]",
    ]
    assert rendered.count("相同判断") == 1
    assert "独立证据；" in rendered
    assert "进一步验证。" in rendered


def test_external_claim_blocks_keep_no_boundary_claim_as_one_cited_paragraph():
    lines = []
    claim = "外部材料称：一段没有句读边界的完整观察[^3]"

    DeepAnalysisRenderer._append_external_variable_paragraph(lines, "变量", claim)

    assert [line for line in lines if "[^3]" in line] == [claim]
