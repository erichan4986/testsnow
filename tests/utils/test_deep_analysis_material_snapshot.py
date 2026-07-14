"""Tests for the deep-analysis MaterialSnapshot read-model."""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from deep_analysis_material_snapshot import (  # noqa: E402
    _CitationAllocator,
    _adapt_material_row,
    Chapter4ViewModel,
    MaterialRow,
    build_chapter4_view_model,
    build_deep_analysis_material_snapshot,
    citation_identity,
    select_annual_display_rows,
)


def _ctx():
    return {
        "synthesis": {"industry_logic": "baseline"},
        "synthesis_display": {"industry_logic": "display"},
        "core_facts": [{"fact": "营业收入", "data": "10亿元"}],
        "pillar": {"valuation": 5},
        "recommendation_decision": object(),
        "structured_risk_signals": {"risk": 1},
        "price_target": {"target": 10},
        "deep_analysis_evidence_profile": {"profile": "formal_thin_external_rich"},
        "annual_report_memo": {
            "schema": "annual_report_memo.v1",
            "status": "ready",
            "sections": {
                "confirmed": [
                    {
                        "title": "营业收入",
                        "body": "营业收入 10 亿元",
                        "internal_refs": ["annual:fact:revenue"],
                        "citation_refs": [1],
                        "source_ref_ids": ["annual-source:revenue"],
                        "argument_family": "financial_quality_explanation",
                        "argument_complete": False,
                    }
                ],
                "annual_report_explanation": [
                    {
                        "title": "管理层讨论",
                        "body": "公司解释增长来自 FPGA。",
                        "internal_refs": ["annual:card:management"],
                        "citation_refs": [2],
                        "source_ref_ids": ["annual-source:management"],
                        "argument_family": "business_structure",
                        "argument_complete": True,
                    }
                ],
                "not_disclosed": [
                    {
                        "title": "未披露",
                        "body": "客户名称未充分披露。",
                        "internal_refs": [],
                        "citation_refs": [],
                        "source_ref_ids": [],
                    }
                ],
                "inconclusive": [],
            },
            "citations": {
                1: {"source": "公司年报", "title": "财务数据"},
                2: {"source": "公司年报", "title": "管理层讨论"},
            },
        },
        "broker_research_memo": {
            "schema": "broker_research_memo.v1",
            "status": "single_institution",
            "sections": [
                {
                    "title": "产业与产品判断",
                    "body": "测试证券认为 800G 放量支撑增长。",
                    "internal_refs": ["broker:card:core"],
                    "citation_refs": [1],
                    "source_ref_ids": ["broker-source:core"],
                }
            ],
            "forecast_ranges": [
                {
                    "metric": "归母净利润",
                    "period": "2026E",
                    "range": "券商预测区间 10-12 亿元",
                    "internal_refs": ["broker:card:forecast"],
                    "citation_refs": [2],
                    "source_ref_ids": ["broker-source:forecast"],
                }
            ],
            "risks": [
                {
                    "body": "研报提示：若需求低于假设，盈利预测需下修。",
                    "internal_refs": ["broker:card:risk"],
                    "citation_refs": [3],
                    "source_ref_ids": ["broker-source:risk"],
                }
            ],
            "citations": {
                1: {"source": "券商研报", "title": "核心观点"},
                2: {"source": "券商研报", "title": "盈利预测"},
                3: {"source": "券商研报", "title": "风险提示"},
            },
        },
        "deep_analysis_display": {
            "_curated_external_reasoning_cards": [
                {
                    "claim": "外部材料称技术路线存在分歧。",
                    "citation_refs": [1],
                    "verification_need": "需要公告验证。",
                }
            ],
            "_curated_external_topic_groups": {
                "technology_route": [
                    {
                        "heading": "技术路线",
                        "text": "外部观点称 CPO 路线仍需验证。",
                        "citation_refs": [2],
                    }
                ]
            },
            "citations": {
                1: {"source": "微信公众号精选观察", "title": "外部深度"},
                2: {"source": "雪球精选观察", "title": "外部讨论"},
            },
        },
        "fundflow_material_pack": {
            "schema": "fundflow_material_pack.v1",
            "rows": [{"date": "2026-07-01", "main_net": 100.0}],
            "summary": {"signal": "inflow_with_price_up"},
        },
        "peer_comparison_material": {
            "schema": "peer_comparison_material.v1",
            "rows": [
                {"metric": "pe_ttm", "confidence": 0.85, "source_refs": ["指标:competitor_metrics"]},
                {"metric": "gross_margin", "confidence": 0.4, "source_refs": ["雪球精选观察"]},
            ],
        },
    }


def _annual_display_row(body, role="business_structure", ref=1, row_id=None, complete=False, status="formal_explanation", title="测试标题"):
    row_id = row_id or f"annual:test:{ref}"
    return MaterialRow(
        row_id=row_id,
        text=f"{title}：{body}",
        source_layer="annual",
        claim_status=status,
        citation_refs=(ref,),
        source_ref_ids=(row_id,),
        title=title,
        body=body,
        render_role=role,
        argument_complete=complete,
        source_credit="official",
    )


def test_select_annual_display_rows_projects_mixed_rows_and_rejects_display_noise():
    rows = [
        _annual_display_row(
            "公司推出新一代高速产品并采用硅光方案，满足更远距离传输需求。"
            "该系列符合 IEEE 802.3ck 和 OSFP MSA 标准。",
            role="technology_product_progress",
            ref=1,
            row_id="annual:mixed",
        ),
        _annual_display_row(
            "报告期内，公司车规级产品已实现批量出货并进入客户供应体系。",
            role="operating_progress",
            ref=2,
            row_id="annual:operating",
        ),
        _annual_display_row(
            "营业收入增长主要系高端产品销售增长及产品结构升级所致。",
            role="financial_quality_explanation",
            ref=3,
            row_id="annual:financial",
        ),
        _annual_display_row(
            "我们认为，后附的公司财务报表在所有重大方面公允反映了公司财务状况。",
            role="market_competition_outlook",
            ref=4,
            row_id="annual:audit",
        ),
        _annual_display_row(
            "在生产模式上，公司主要采取以销定产的生产模式，并按订单编制生产计划。",
            role="business_structure",
            ref=5,
            row_id="annual:routine",
        ),
        _annual_display_row(
            "根据第三方预测，2026年全球市场规模将达到228亿美元。",
            role="market_competition_outlook",
            ref=6,
            row_id="annual:industry",
        ),
    ]

    selected, diagnostics = select_annual_display_rows(rows)

    selected_ids = {row.row_id for row in selected}
    assert {"annual:mixed", "annual:operating", "annual:financial"} <= selected_ids
    assert {"annual:audit", "annual:routine", "annual:industry"}.isdisjoint(selected_ids)
    mixed = next(row for row in selected if row.row_id == "annual:mixed")
    assert mixed.body == "公司推出新一代高速产品并采用硅光方案，满足更远距离传输需求。"
    assert mixed.citation_refs == (1,)
    assert diagnostics["annual_candidates_count"] == 6
    assert diagnostics["annual_selected_count"] == 3
    assert diagnostics["annual_rejected_by_reason"]
    assert sum(diagnostics["annual_rejected_by_reason"].values()) == 3


def test_select_annual_display_rows_filters_formal_fact_noise_before_admission():
    rows = [
        _annual_display_row(
            "我们认为，后附的公司财务报表在所有重大方面公允反映了公司财务状况。",
            status="formal_fact",
            role="financial_quality_explanation",
            ref=1,
            row_id="annual:confirmed-audit",
        ),
        _annual_display_row(
            "营业收入增长主要系高端产品销售增长及产品结构升级所致。",
            status="formal_fact",
            role="financial_quality_explanation",
            ref=2,
            row_id="annual:confirmed-financial",
        ),
    ]

    selected, diagnostics = select_annual_display_rows(rows)

    assert [row.row_id for row in selected] == ["annual:confirmed-financial"]
    assert diagnostics["annual_rejected_by_reason"] == {"audit_boilerplate": 1}


def test_select_annual_display_rows_uses_body_not_title_for_noise_and_role_admission():
    rows = [
        _annual_display_row(
            "根据第三方预测，2026年全球市场规模将达到228亿美元。",
            role="market_competition_outlook",
            row_id="annual:industry-title",
            title="主营业务与产品",
        ),
        _annual_display_row(
            "> 产品类型 | 产品介绍 | 应用领域",
            row_id="annual:blockquote-title",
            title="主营业务与产品",
        ),
        _annual_display_row(
            "| 产品类型 | 产品介绍 | 应用领域 | 典型产品 |",
            row_id="annual:table-title",
            title="主营业务与产品",
        ),
        _annual_display_row(
            "上游供应链整体保持稳定，相关安排仍需后续观察。",
            row_id="annual:role-title",
            title="主营业务与产品",
        ),
    ]

    selected, diagnostics = select_annual_display_rows(rows)

    assert not selected
    assert diagnostics["annual_rejected_by_reason"] == {
        "generic_industry_context": 1,
        "document_or_heading_noise": 2,
        "role_mismatch": 1,
    }


def test_select_annual_display_rows_keeps_sentence_boundary_after_mode_projection():
    selected, _ = select_annual_display_rows((
        _annual_display_row(
            "公司提供工业控制设备并服务客户，经营模式包括直销和经销。"
            "报告期内，公司新增客户并实现批量交付。",
            title="主营业务与产品",
            row_id="annual:mode-with-progress",
        ),
    ))

    assert [row.body for row in selected] == [
        "公司提供工业控制设备并服务客户。报告期内，公司新增客户并实现批量交付。"
    ]


def test_select_annual_display_rows_keeps_retained_source_text_verbatim():
    body = "报告期内公司从事的主要业务为高端设备研发，并服务于工业客户。"
    selected, _ = select_annual_display_rows((
        _annual_display_row(body, role="business_structure", row_id="annual:source-text"),
    ))

    assert [row.body for row in selected] == [body]


def test_select_annual_display_rows_has_no_family_or_global_cap():
    rows = [
        _annual_display_row(
            f"报告期内，公司产品{i}完成客户导入并实现批量出货。",
            role="operating_progress",
            ref=i + 1,
            row_id=f"annual:operating:{i}",
        )
        for i in range(16)
    ]

    selected, diagnostics = select_annual_display_rows(rows)

    assert len(selected) == 16
    assert diagnostics["annual_selected_count"] == 16


def test_select_annual_display_rows_dedupes_exact_and_containment_only():
    rows = [
        _annual_display_row("公司主营业务为芯片设计", ref=1, row_id="annual:short"),
        _annual_display_row("公司主营业务为芯片设计", ref=2, row_id="annual:exact"),
        _annual_display_row("公司主营业务为芯片设计，产品服务于汽车电子客户", ref=3, row_id="annual:long"),
        _annual_display_row("公司通过客户认证进入汽车电子供应链", ref=4, row_id="annual:independent"),
    ]

    selected, diagnostics = select_annual_display_rows(rows)

    selected_ids = {row.row_id for row in selected}
    assert "annual:long" in selected_ids
    assert "annual:short" not in selected_ids
    assert "annual:exact" not in selected_ids
    assert "annual:independent" in selected_ids
    assert diagnostics["annual_deduped_count"] == 2


def test_select_annual_display_rows_dedupes_exact_text_across_roles():
    body = "公司主营业务为芯片设计，产品服务于汽车电子客户。"
    selected, diagnostics = select_annual_display_rows((
        _annual_display_row(body, role="business_structure", ref=1, row_id="annual:business"),
        _annual_display_row(body, role="technology_product_progress", ref=2, row_id="annual:technology"),
    ))

    assert [row.row_id for row in selected] == ["annual:business"]
    assert diagnostics["annual_rejected_by_reason"] == {"duplicate_exact": 1}


def test_select_annual_display_rows_rejects_structural_noise_and_fragments():
    selected, diagnostics = select_annual_display_rows((
        _annual_display_row("公司具备成熟的供应商遴选机制，并严格遵守相关规则。", row_id="annual:supplier"),
        _annual_display_row("因此无从事与本公司相同或相近的业务。", row_id="annual:competition"),
        _annual_display_row("（2）占公司营业收入或营业利润10%以上的行业、产品、地区、", row_id="annual:table"),
        _annual_display_row("方面，随着 Scale-up 网络规模提升，市场需求持续扩大。", role="market_competition_outlook", row_id="annual:fragment"),
        _annual_display_row("公司主营业务为高端光通信收发模块的研发、生产及销售，产品服务于云计算数据中心。", row_id="annual:business"),
    ))

    assert [row.row_id for row in selected] == ["annual:business"]
    assert diagnostics["annual_rejected_by_reason"] == {
        "disclosure_or_governance": 2,
        "document_or_heading_noise": 2,
    }


def test_select_annual_display_rows_rejects_remaining_report_noise_shapes():
    rows = (
        _annual_display_row("2、自本承诺函签署后，本方和关联企业将不会控制任何从事相同业务的企业。", row_id="annual:promise"),
        _annual_display_row("在客户开拓上，供应商通常需要通过客户的供应商认证和产品代码。", row_id="annual:certification"),
        _annual_display_row("综上所述，公司不存在不能保证独立性、不能保持自主经营能力的情况。", row_id="annual:independence"),
        _annual_display_row("报告期内，公司经营模式没有发生变化。", row_id="annual:mode"),
        _annual_display_row("因香港联交所有关规则并不要求港股客户申报股份质押情况，因此无法统计相关数量。", row_id="annual:hkex"),
        _annual_display_row("到2029年，数据产业规模年均复合增长率超过15%，催生一批数智应用新产品新服务新业态。", role="market_competition_outlook", row_id="annual:policy"),
        _annual_display_row("更多与研发成果相关内容可查阅相关章节，知识产权列表本年新增累计数量申请数（个）获得数（个）。", role="technology_product_progress", row_id="annual:ip-table"),
        _annual_display_row("公司主营业务为高端光通信收发模块研发、生产及销售，产品服务于云计算数据中心。", row_id="annual:business"),
    )

    selected, diagnostics = select_annual_display_rows(rows)

    assert [row.row_id for row in selected] == ["annual:business"]
    assert sum(diagnostics["annual_rejected_by_reason"].values()) == 7


def test_select_annual_display_rows_removes_normalized_duplicate_segments_within_a_row():
    sentence = "主要应用于400G以太网、数据中心和云网络。"
    selected, _ = select_annual_display_rows((
        _annual_display_row(
            sentence + "主要应用于 400G 以 太网、数据中心和云 网络。",
            role="business_structure",
            row_id="annual:repeated",
        ),
    ))

    assert [row.body for row in selected] == [sentence]


def test_formal_medium_view_model_selects_annual_display_rows_and_reports_diagnostics():
    ctx = _ctx()
    ctx["annual_report_memo"]["sections"]["annual_report_explanation"] = [
        {
            "title": "主营业务",
            "body": "公司主营业务为芯片设计并服务于汽车电子客户。",
            "citation_refs": [1],
            "source_ref_ids": ["annual:business"],
            "argument_family": "business_structure",
        },
        {
            "title": "审计意见",
            "body": "我们认为，后附的公司财务报表在所有重大方面公允反映了公司财务状况。",
            "citation_refs": [2],
            "source_ref_ids": ["annual:audit"],
            "argument_family": "business_structure",
        },
        {
            "title": "行业预测",
            "body": "根据第三方预测，2026年全球市场规模将达到228亿美元。",
            "citation_refs": [3],
            "source_ref_ids": ["annual:industry"],
            "argument_family": "market_competition_outlook",
        },
    ]

    view_model = build_chapter4_view_model(
        build_deep_analysis_material_snapshot(ctx),
        {"profile": "formal_medium"},
    )

    annual_ids = {row.row_id for row in view_model.section("4.1").rows}
    assert "annual:annual_report_explanation:0" in annual_ids
    assert "annual:annual_report_explanation:1" not in annual_ids
    assert "annual:annual_report_explanation:2" not in annual_ids
    assert view_model.diagnostics["annual_candidates_count"] == 4
    assert view_model.diagnostics["annual_selected_count"] == 2


def test_formal_medium_price_path_uses_strict_selected_role_priority():
    ctx = _ctx()
    ctx["annual_report_memo"]["sections"]["annual_report_explanation"] = [
        {
            "title": "审计意见",
            "body": "我们认为，后附的公司财务报表在所有重大方面公允反映了公司财务状况。",
            "citation_refs": [1],
            "source_ref_ids": ["annual:audit"],
            "argument_family": "business_structure",
            "argument_complete": True,
        },
        {
            "title": "技术进展",
            "body": "公司推出新一代产品并完成客户验证。",
            "citation_refs": [2],
            "source_ref_ids": ["annual:technology"],
            "argument_family": "technology_product_progress",
            "argument_complete": True,
        },
    ]

    view_model = build_chapter4_view_model(
        build_deep_analysis_material_snapshot(ctx),
        {"profile": "formal_medium"},
    )

    price_path_annual = [row for row in view_model.section("4.4").rows if row.source_layer == "annual"]
    assert price_path_annual
    assert price_path_annual[0].row_id == "annual:annual_report_explanation:1"


def test_snapshot_projects_annual_broker_and_external_rows_with_global_citations():
    snapshot = build_deep_analysis_material_snapshot(_ctx())

    assert snapshot.schema == "deep_analysis_material_snapshot.v1"
    assert all(isinstance(row, MaterialRow) for row in snapshot.rows)
    assert all(row.display_scope == ("deep_analysis",) for row in snapshot.rows)
    assert all(row.scoring_eligible is False for row in snapshot.rows)
    assert all(row.risk_score_eligible is False for row in snapshot.rows)

    rows_by_id = {row.row_id: row for row in snapshot.rows}
    assert rows_by_id["annual:confirmed:0"].text == "营业收入：营业收入 10 亿元"
    assert rows_by_id["annual:annual_report_explanation:0"].claim_status == "formal_explanation"
    assert rows_by_id["broker:forecast_ranges:0"].source_layer == "broker"
    assert rows_by_id["broker:risks:0"].claim_status == "professional_analysis"
    assert rows_by_id["external:reasoning_cards:0"].source_layer == "external"
    assert rows_by_id["external:topic_groups:technology_route:0"].section_hint == "external_map"

    all_refs = {ref for row in snapshot.rows for ref in row.citation_refs}
    assert all_refs
    assert all(ref in snapshot.citations for ref in all_refs)
    assert rows_by_id["annual:confirmed:0"].citation_refs == (1,)
    assert rows_by_id["broker:sections:0"].citation_refs == (3,)
    assert rows_by_id["external:reasoning_cards:0"].citation_refs == (6,)


def test_snapshot_keeps_fundflow_and_peer_material_in_diagnostics_only():
    snapshot = build_deep_analysis_material_snapshot(_ctx())

    assert not any(row.source_layer in {"fundflow", "peer"} for row in snapshot.rows)
    assert snapshot.diagnostics["fundflow_rows_count"] == 1
    assert snapshot.diagnostics["fundflow_summary_signal"] == "inflow_with_price_up"
    assert snapshot.diagnostics["peer_rows_count"] == 2
    assert snapshot.diagnostics["peer_high_confidence_rows"] == 1
    assert snapshot.diagnostics["peer_has_social_leak"] is True


def test_snapshot_builder_does_not_mutate_ctx_or_forbidden_fields():
    ctx = _ctx()
    before = copy.deepcopy({k: v for k, v in ctx.items() if k != "recommendation_decision"})
    recommendation_decision = ctx["recommendation_decision"]

    snapshot = build_deep_analysis_material_snapshot(ctx)

    assert snapshot.rows
    assert {k: v for k, v in ctx.items() if k != "recommendation_decision"} == before
    assert ctx["recommendation_decision"] is recommendation_decision
    for forbidden in (
        "synthesis",
        "synthesis_display",
        "core_facts",
        "pillar",
        "recommendation_decision",
        "structured_risk_signals",
        "price_target",
    ):
        assert forbidden in ctx
    assert "deep_analysis_material_snapshot" not in ctx


def test_evidence_rows_are_immutable():
    snapshot = build_deep_analysis_material_snapshot(_ctx())

    with pytest.raises(Exception):
        snapshot.rows[0].text = "changed"


def test_formal_medium_view_model_unifies_source_layers_and_visible_citations():
    snapshot = build_deep_analysis_material_snapshot(_ctx())

    view_model = build_chapter4_view_model(snapshot, {"profile": "formal_medium"})

    assert isinstance(view_model, Chapter4ViewModel)
    assert all(isinstance(row, MaterialRow) for row in snapshot.rows)
    assert [section.section_id for section in view_model.sections] == ["4.1", "4.2", "4.3", "4.4"]
    assert {row.source_layer for row in view_model.section("4.1").rows} == {"annual"}
    assert {row.source_layer for row in view_model.section("4.2").rows} == {"broker"}
    assert {row.source_layer for row in view_model.section("4.3").rows} == {"external"}
    assert {row.source_layer for row in view_model.section("4.4").rows} == {"annual", "broker", "external"}
    assert all(row.attribution for row in view_model.section("4.2").rows)
    assert all(row.source_credit == "official" for row in view_model.section("4.1").rows)
    assert all(row.source_credit == "professional" for row in view_model.section("4.2").rows)
    assert all(row.source_credit == "external_low_credit" for row in view_model.section("4.3").rows)
    assert all(
        not row.scoring_eligible and not row.risk_score_eligible
        for row in view_model.section("4.3").rows
    )

    visible_refs = {
        ref
        for section in view_model.sections
        for row in section.rows
        for ref in row.citation_refs
    }
    assert visible_refs == set(view_model.citations)
    assert not any(row.row_id == "annual:not_disclosed:0" for row in view_model.section("4.1").rows)


def test_formal_medium_view_model_preserves_input_and_row_render_metadata():
    ctx = _ctx()
    before = copy.deepcopy({k: v for k, v in ctx.items() if k != "recommendation_decision"})
    snapshot = build_deep_analysis_material_snapshot(ctx)

    view_model = build_chapter4_view_model(snapshot, {"profile": "formal_medium"})

    annual_row = next(row for row in view_model.section("4.1").rows if row.row_id == "annual:confirmed:0")
    broker_row = next(row for row in view_model.section("4.2").rows if row.row_id == "broker:sections:0")
    external_row = next(row for row in view_model.section("4.3").rows if row.row_id == "external:reasoning_cards:0")
    assert annual_row.title == "营业收入"
    assert annual_row.body == "营业收入 10 亿元"
    assert annual_row.render_role == "financial_quality_explanation"
    assert annual_row.argument_complete is False
    assert broker_row.render_role == "broker_assumption"
    assert broker_row.attribution == "测试证券"
    assert external_row.render_role == "external_variable"
    assert external_row.title == "外部变量"
    assert {k: v for k, v in ctx.items() if k != "recommendation_decision"} == before


def test_incomplete_selected_annual_rows_enter_price_path_after_complete_rows_are_exhausted():
    ctx = _ctx()
    ctx["annual_report_memo"]["sections"]["annual_report_explanation"][0]["argument_complete"] = False

    view_model = build_chapter4_view_model(
        build_deep_analysis_material_snapshot(ctx),
        {"profile": "formal_medium"},
    )

    assert view_model.section("4.1").rows
    assert any(row.source_layer == "annual" for row in view_model.section("4.4").rows)


def test_snapshot_does_not_admit_stale_rows_from_absent_annual_or_broker_memo():
    ctx = _ctx()
    ctx["annual_report_memo"]["status"] = "absent"
    ctx["broker_research_memo"]["status"] = "absent"

    snapshot = build_deep_analysis_material_snapshot(ctx)
    view_model = build_chapter4_view_model(snapshot, {"profile": "formal_medium"})

    assert not view_model.section("4.1").rows
    assert not view_model.section("4.2").rows
    assert all(row.source_layer == "external" for row in snapshot.rows)


def test_shared_material_classification_and_citation_identity_helpers():
    assert citation_identity({"url": "https://example.com/a"}) == ("url", "https://example.com/a")
    assert citation_identity({"source": "研报", "author": "机构", "title": "正文"}) == (
        "meta",
        "研报",
        "机构",
        "正文",
    )
    assert citation_identity({}, fallback_ref=7) == ("ref", 7)


def test_material_row_adapter_owns_common_refs_source_ids_and_diagnostics():
    allocator = _CitationAllocator()
    source = {
        "title": "管理层讨论",
        "body": "增长来自产品升级。",
        "citation_refs": ["1"],
        "source_ref_ids": ["annual-source:management"],
        "selection_reason": "highest_score",
    }

    row = _adapt_material_row(
        source,
        allocator,
        {1: {"source": "公司年报", "title": "管理层讨论"}},
        "annual:annual_report_explanation:0",
        source_layer="annual",
        claim_status="formal_explanation",
        section_hint="annual_memo",
        render_role="management_view",
        source_credit="official",
    )

    assert row.title == "管理层讨论"
    assert row.body == "增长来自产品升级。"
    assert row.text == "管理层讨论：增长来自产品升级。"
    assert row.citation_refs == (1,)
    assert row.source_ref_ids == ("annual-source:management",)
    assert row.diagnostics == (("selection_reason", "highest_score"),)
    assert allocator.citations[1]["source"] == "公司年报"
