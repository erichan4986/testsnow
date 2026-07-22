"""Tests for the deep-analysis MaterialSnapshot read-model."""

import copy
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from deep_analysis_material_snapshot import (  # noqa: E402
    _CitationAllocator,
    _adapt_material_row,
    Chapter4ViewModel,
    MaterialSnapshot,
    MaterialRow,
    ExternalNarrativePart,
    ExternalTopicNarrative,
    build_chapter4_view_model,
    build_deep_analysis_material_snapshot,
    citation_identity,
    select_annual_display_rows,
    select_incremental_external_display_rows,
    select_external_topic_narratives,
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
            "_curated_external_argument_cards": [
                _external_argument_card(
                    argument_key="technology:route",
                    evidence="外部文章讨论 CPO 路线分歧。",
                )
            ],
            "citations": {
                1: {"source": "微信公众号精选观察", "title": "外部深度"},
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


def _external_argument_card(
    evidence, *, argument_key, ref=1, topic="capacity_delivery", entity_scope="target",
):
    origin = "peer_or_industry" if entity_scope == "peer_or_industry" else "explicit_target"
    return {
        "schema_version": "curated_external_argument_card.v4",
        "card_id": f"external-argument:{argument_key}",
        "entity_scope": entity_scope,
        "coverage_families": [topic],
        "primary_family": topic,
        "evidence_units": [{
            "schema_version": "curated_external_evidence_unit.v2", "text": evidence,
            "evidence_status": "source_unit_verified",
            "unit_id": f"unit:{argument_key}",
            "unit_hash": "test",
            "source_id": "source:test",
            "document_hash": "test", "block_id": "block:test", "block_ordinal": 0,
            "unit_ordinal": 0, "block_hash": "test", "start": 0, "end": len(evidence),
            "citation_refs": [ref],
            "scope_provenance": {
                "schema_version": "curated_external_scope_provenance.v2", "origin": origin,
                "anchor_unit_id": f"unit:{argument_key}" if origin == "explicit_target" else "",
                "proof_kind": "explicit_stock_name" if origin == "explicit_target" else "none",
                "proof_value": "测试股" if origin == "explicit_target" else "",
            },
        }],
        "argument_key": argument_key,
        "citation_refs": [ref],
        "quality_action": "preview_only",
        "synthesis_display_only": True,
        "scoring_eligible": False,
        "risk_score_eligible": False,
    }


def test_snapshot_projects_external_argument_v4_and_keeps_full_snapshot_offsets():
    ctx = _ctx()
    ctx["deep_analysis_display"].update({
        "_curated_external_argument_cards": [
            _external_argument_card(
                argument_key="capacity:delivery",
                evidence="外部文章称上游物料供应偏紧，交付节奏仍需验证。",
            )
        ],
        "citations": {1: {"source": "微信公众号精选观察", "title": "供应链观察"}},
    })

    snapshot = build_deep_analysis_material_snapshot(ctx)
    external = [row for row in snapshot.rows if row.source_layer == "external"]

    assert [row.row_id for row in external] == ["external:argument_cards:0"]
    assert external[0].external_claim == "外部文章称上游物料供应偏紧，交付节奏仍需验证。"
    assert external[0].external_evidence.startswith("外部文章称")
    assert external[0].evidence_status == "source_unit_verified"
    assert external[0].argument_key == "capacity:delivery"
    assert external[0].citation_refs == (6,)
    assert snapshot.citations[6]["title"] == "供应链观察"


def test_snapshot_uses_v4_exact_unit_text_without_display_projection():
    ctx = _ctx()
    ctx["deep_analysis_display"].update({
        "_curated_external_argument_cards": [_external_argument_card(
            argument_key="target:product",
            evidence="测试股产品完成客户导入。",
        )],
        "citations": {1: {"source": "微信公众号精选观察", "title": "产品观察"}},
    })

    snapshot = build_deep_analysis_material_snapshot(ctx)
    row = next(row for row in snapshot.rows if row.source_layer == "external")

    assert row.body == "测试股产品完成客户导入。"
    assert row.citation_refs == (6,)


def test_snapshot_orders_target_external_rows_before_peer_background():
    ctx = _ctx()
    ctx["deep_analysis_display"].update({
        "_curated_external_argument_cards": [
            _external_argument_card(
                argument_key="peer:competition", evidence="行业竞争格局加速分化。", ref=2,
                topic="competitive_landscape", entity_scope="peer_or_industry",
            ),
            _external_argument_card(
                argument_key="target:delivery", evidence="测试股产品完成客户导入。", ref=1,
                topic="commercialization", entity_scope="target",
            ),
        ],
        "citations": {
            1: {"source": "微信公众号精选观察", "title": "目标观察"},
            2: {"source": "微信公众号精选观察", "title": "行业观察"},
        },
    })

    snapshot = build_deep_analysis_material_snapshot(ctx)
    external = [row for row in snapshot.rows if row.source_layer == "external"]

    assert [row.entity_scope for row in external] == ["target", "peer_or_industry"]


def test_snapshot_projects_topic_narratives_with_unit_derived_global_refs():
    ctx = _ctx()
    card = _external_argument_card(
        argument_key="target:delivery", evidence="测试股产品完成客户导入。",
        topic="commercialization", entity_scope="target",
    )
    unit = card["evidence_units"][0]
    ctx["deep_analysis_display"] = {
        "_curated_external_argument_cards": [card],
        "_curated_external_topic_narratives": [{
            "scope_bucket": "target", "primary_family": "commercialization", "parts": [{
                "argument_key": card["argument_key"], "unit_id": unit["unit_id"],
                "quote": unit["text"], "relation": "first", "citation_refs": [1],
            }],
        }],
        "citations": {1: {"source": "微信公众号精选观察", "title": "目标观察"}},
    }

    snapshot = build_deep_analysis_material_snapshot(ctx)

    narrative = snapshot.external_topic_narratives[0]
    assert isinstance(narrative, ExternalTopicNarrative)
    assert isinstance(narrative.parts[0], ExternalNarrativePart)
    assert narrative.parts[0].citation_refs == (6,)
    assert snapshot.rows[-1].external_unit_ids == (unit["unit_id"],)


def test_view_model_filters_hidden_narrative_arguments_and_keeps_price_path_rows_unchanged():
    visible = MaterialRow(
        "external:visible", "客户验证", "external", "external_observation", (2,), ("external:visible",),
        title="商业化进展", body="测试股产品完成客户导入。", external_claim="测试股产品完成客户导入。",
        external_evidence="测试股产品完成客户导入。", evidence_status="source_unit_verified",
        entity_scope="target", argument_key="visible", external_family="commercialization",
        external_unit_ids=("u-visible",),
    )
    hidden = MaterialRow(
        "external:hidden", "重复观察", "external", "external_observation", (), ("external:hidden",),
        title="商业化进展", body="测试股产品完成客户导入。", external_claim="测试股产品完成客户导入。",
        external_evidence="测试股产品完成客户导入。", evidence_status="source_unit_verified",
        entity_scope="target", argument_key="hidden", external_family="commercialization",
        external_unit_ids=("u-hidden",),
    )
    narrative = ExternalTopicNarrative("target", "commercialization", (
        ExternalNarrativePart("visible", "u-visible", "测试股产品完成客户导入。", "first", (2,)),
        ExternalNarrativePart("hidden", "u-hidden", "重复观察。", "continuation", (3,)),
    ))
    snapshot = MaterialSnapshot(
        "deep_analysis_material_snapshot.v1", (visible, hidden),
        {2: {"source": "外部观察"}, 3: {"source": "外部观察"}}, {}, (narrative,),
    )

    without_memo = build_chapter4_view_model(
        MaterialSnapshot(snapshot.schema, snapshot.rows, snapshot.citations, snapshot.diagnostics),
        "formal_medium",
    )
    with_memo = build_chapter4_view_model(snapshot, "formal_medium")

    projected = with_memo.section("4.3").narratives[0]
    assert [part.argument_key for part in projected.parts] == ["visible"]
    assert projected.parts[0].relation == "first"
    assert with_memo.section("4.4").rows == without_memo.section("4.4").rows
    assert set(with_memo.citations) == {2}


def _external_narrative_row(key, unit_id, body, ref):
    return MaterialRow(
        f"external:{key}", body, "external", "external_observation", (ref,), (f"source:{ref}",),
        title="财务质量", body=body, evidence_status="source_unit_verified",
        entity_scope="target", argument_key=key, external_family="financial_quality",
        external_unit_ids=(unit_id,),
    )


def test_external_narrative_accepts_plan_order_when_unit_coverage_matches():
    rows = (
        _external_narrative_row("second", "u2", "归母净利润预计增长。", 2),
        _external_narrative_row("first", "u1", "营业收入预计增长。", 1),
    )
    narrative = ExternalTopicNarrative("target", "financial_quality", (
        ExternalNarrativePart("first", "u1", "营业收入预计增长。", "first", (1,)),
        ExternalNarrativePart("second", "u2", "归母净利润预计增长。", "continuation", (2,)),
    ))

    selected = select_external_topic_narratives((narrative,), rows)

    assert [(part.argument_key, part.unit_id) for part in selected[0].parts] == [
        ("first", "u1"), ("second", "u2"),
    ]


def test_external_narrative_rejects_incomplete_plan_before_owner_filtering():
    duplicate = "公司2025年营业收入为10亿元。"
    update = "公司2026年上半年营业收入预计为22至24亿元。"
    owner = _annual_display_row(
        duplicate, role="financial_quality_explanation", row_id="annual:revenue",
    )
    rows = (
        _external_narrative_row("financial", "u1", duplicate, 2),
        _external_narrative_row("financial", "u2", update, 2),
    )
    incomplete = ExternalTopicNarrative("target", "financial_quality", (
        ExternalNarrativePart("financial", "u1", duplicate, "first", (2,)),
    ))

    assert select_external_topic_narratives((incomplete,), rows, (owner,)) == ()


def test_external_narrative_merges_equivalent_metric_facts_and_citations():
    quotes = (
        "营业收入预计22至24亿元，同比增长19.64%至30.52%。",
        "复旦微电于7月7日晚间公告，预计2026年上半年实现营业收入约22至24亿元，同比增长19.64%至30.52%。",
        "营业收入预计18至20亿元，同比增长5%至10%。",
    )
    rows = tuple(
        _external_narrative_row(f"fact-{index}", f"u{index}", quote, index)
        for index, quote in enumerate(quotes, 1)
    )
    narrative = ExternalTopicNarrative("target", "financial_quality", tuple(
        ExternalNarrativePart(f"fact-{index}", f"u{index}", quote, "first" if index == 1 else "continuation", (index,))
        for index, quote in enumerate(quotes, 1)
    ))

    parts = select_external_topic_narratives((narrative,), rows)[0].parts

    assert len(parts) == 2
    assert parts[0].quote == quotes[1]
    assert parts[0].citation_refs == (1, 2)
    assert parts[1].quote == quotes[2]
    assert parts[1].citation_refs == (3,)


def test_external_narrative_does_not_merge_different_metrics_with_same_values():
    quotes = (
        "营业收入预计22至24亿元，同比增长19.64%至30.52%。",
        "归母净利润预计22至24亿元，同比增长19.64%至30.52%。",
    )
    rows = tuple(
        _external_narrative_row(f"metric-{index}", f"u{index}", quote, index)
        for index, quote in enumerate(quotes, 1)
    )
    narrative = ExternalTopicNarrative("target", "financial_quality", tuple(
        ExternalNarrativePart(f"metric-{index}", f"u{index}", quote, "first" if index == 1 else "continuation", (index,))
        for index, quote in enumerate(quotes, 1)
    ))

    parts = select_external_topic_narratives((narrative,), rows)[0].parts

    assert [part.quote for part in parts] == list(quotes)


def test_external_narrative_does_not_merge_materially_different_small_values():
    quotes = ("毛利率预计为0.3%。", "毛利率预计为0.5%。")
    rows = tuple(
        _external_narrative_row(f"margin-{index}", f"u{index}", quote, index)
        for index, quote in enumerate(quotes, 1)
    )
    narrative = ExternalTopicNarrative("target", "financial_quality", tuple(
        ExternalNarrativePart(f"margin-{index}", f"u{index}", quote, "first" if index == 1 else "continuation", (index,))
        for index, quote in enumerate(quotes, 1)
    ))

    parts = select_external_topic_narratives((narrative,), rows)[0].parts

    assert [part.quote for part in parts] == list(quotes)


def test_external_narrative_hides_owner_equivalent_part_and_keeps_new_period():
    owner = _annual_display_row(
        "公司2025年营业收入为10亿元。", role="financial_quality_explanation",
        row_id="annual:revenue",
    )
    quotes = (
        "公司2025年营业收入为10亿元。",
        "公司2026年上半年营业收入预计为22至24亿元。",
    )
    rows = tuple(
        _external_narrative_row(f"period-{index}", f"u{index}", quote, index + 1)
        for index, quote in enumerate(quotes)
    )
    narrative = ExternalTopicNarrative("target", "financial_quality", tuple(
        ExternalNarrativePart(
            f"period-{index}", f"u{index}", quote,
            "first" if index == 0 else "continuation", (index + 1,),
        )
        for index, quote in enumerate(quotes)
    ))

    parts = select_external_topic_narratives((narrative,), rows, (owner,))[0].parts

    assert [part.quote for part in parts] == [quotes[1]]
    assert parts[0].relation == "first"


def test_external_narrative_keeps_same_year_different_reporting_period():
    owner = _annual_display_row(
        "公司预计2026年上半年营业收入为10亿元，同比增长20%，主要受产品增长推动。",
        role="financial_quality_explanation",
        row_id="annual:first-half",
    )
    quote = "公司预计2026年下半年营业收入为10亿元，同比增长20%，主要受产品增长推动。"
    row = _external_narrative_row("second-half", "u1", quote, 2)
    narrative = ExternalTopicNarrative("target", "financial_quality", (
        ExternalNarrativePart("second-half", "u1", quote, "first", (2,)),
    ))

    parts = select_external_topic_narratives((narrative,), (row,), (owner,))[0].parts

    assert [part.quote for part in parts] == [quote]


def test_external_narrative_normalizes_full_and_half_width_punctuation_for_owner_match():
    owner = _annual_display_row(
        "公司FPGA产品，已认证：可量产。", role="technology_product_progress",
        row_id="annual:punctuation",
    )
    quote = "公司FPGA产品,已认证:可量产。"
    row = replace(
        _external_narrative_row("punctuation", "u1", quote, 2),
        external_family="technology_product",
    )
    narrative = ExternalTopicNarrative("target", "technology_product", (
        ExternalNarrativePart("punctuation", "u1", quote, "first", (2,)),
    ))

    selected = select_external_topic_narratives((narrative,), (row,), (owner,))

    assert selected[0].parts == ()


def test_external_narrative_keeps_protected_owner_deltas():
    owners = tuple(
        _annual_display_row(body, role=role, ref=index + 1, row_id=f"annual:owner:{index}")
        for index, (body, role) in enumerate((
            ("公司2025年营业收入为10亿元。", "financial_quality_explanation"),
            ("公司800G产品处于样品阶段。", "technology_product_progress"),
            ("公司上游设备采购存在明显瓶颈。", "operating_progress"),
            ("公司推出NPO产品。", "technology_product_progress"),
            ("公司FPAI产品覆盖4TOPS至128TOPS。", "technology_product_progress"),
        ))
    )
    quotes = (
        "公司2025年归母净利润为10亿元。",
        "公司800G产品进入量产阶段。",
        "公司上游设备采购没有明显瓶颈。",
        "公司与头部客户合作推出NPO产品。",
        "公司FPAI产品集成CPU、FPGA、NPU，覆盖4TOPS至128TOPS。",
    )
    rows = tuple(
        _external_narrative_row(f"protected-{index}", f"u{index}", quote, index + 10)
        for index, quote in enumerate(quotes)
    )
    narrative = ExternalTopicNarrative("target", "financial_quality", tuple(
        ExternalNarrativePart(
            f"protected-{index}", f"u{index}", quote,
            "first" if index == 0 else "continuation", (index + 10,),
        )
        for index, quote in enumerate(quotes)
    ))

    parts = select_external_topic_narratives((narrative,), rows, owners)[0].parts

    assert [part.quote for part in parts] == list(quotes)


def test_external_narrative_returns_empty_sentinel_when_all_parts_match_owner():
    quote = "公司2025年营业收入为10亿元。"
    owner = _annual_display_row(
        quote, role="financial_quality_explanation", row_id="annual:revenue",
    )
    row = _external_narrative_row("duplicate", "u1", quote, 2)
    narrative = ExternalTopicNarrative("target", "financial_quality", (
        ExternalNarrativePart("duplicate", "u1", quote, "first", (2,)),
    ))

    selected = select_external_topic_narratives((narrative,), (row,), (owner,))

    assert len(selected) == 1
    assert selected[0].parts == ()


def test_external_peer_narrative_bypasses_target_owner_comparison():
    quote = "同业公司800G产品已进入量产阶段。"
    owner = _annual_display_row(
        quote, role="technology_product_progress", row_id="annual:technology",
    )
    row = replace(
        _external_narrative_row("peer", "u1", quote, 2),
        entity_scope="peer_or_industry", external_family="technology_product",
    )
    narrative = ExternalTopicNarrative("peer_or_industry", "technology_product", (
        ExternalNarrativePart("peer", "u1", quote, "first", (2,)),
    ))

    selected = select_external_topic_narratives((narrative,), (row,), (owner,))

    assert [part.quote for part in selected[0].parts] == [quote]


def test_view_model_projects_owner_equivalent_parts_without_changing_price_path_rows():
    owner = _annual_display_row(
        "公司2025年营业收入为10亿元。", role="financial_quality_explanation",
        ref=1, row_id="annual:revenue",
    )
    duplicate = "公司2025年营业收入为10亿元。"
    update = "公司2026年上半年营业收入预计为22至24亿元。"
    external = MaterialRow(
        "external:financial", "财务更新", "external", "external_observation", (2,), ("external:2",),
        title="2026年业绩更新", body=duplicate + update, render_role="external_variable",
        external_claim=duplicate + update, external_evidence=duplicate + update,
        evidence_status="source_unit_verified", entity_scope="target",
        argument_key="financial", external_family="financial_quality",
        external_unit_ids=("u1", "u2"),
    )
    narrative = ExternalTopicNarrative("target", "financial_quality", (
        ExternalNarrativePart("financial", "u1", duplicate, "first", (2,)),
        ExternalNarrativePart("financial", "u2", update, "continuation", (2,)),
    ))
    snapshot = MaterialSnapshot(
        "deep_analysis_material_snapshot.v1", (owner, external),
        {1: {"source": "公司年报"}, 2: {"source": "外部观察"}}, {}, (narrative,),
    )

    view_model = build_chapter4_view_model(snapshot, "formal_medium")

    assert [part.quote for part in view_model.section("4.3").narratives[0].parts] == [update]
    assert view_model.section("4.1").rows[0].citation_refs == (1,)
    price_row = next(row for row in view_model.section("4.4").rows if row.source_layer == "external")
    assert price_row.body == duplicate + update


def test_external_selector_keeps_all_distinct_arguments_and_marks_owner_relation():
    owner = MaterialRow(
        "annual:owner", "供应链", "annual", "formal_explanation", (1,), ("annual:owner",),
        body="公司800G产品保持稳定交付。", render_role="operating_progress",
    )
    rows = tuple(
        MaterialRow(
            f"external:argument_cards:{index}", claim, "external", "external_observation", (index + 2,), (f"external:{index}",),
            title="供应链交付", body=claim, render_role="external_variable",
            external_claim=claim, external_evidence=evidence,
            evidence_status="source_quote_verified", entity_scope="target",
            argument_key=f"argument:{index}",
        )
        for index, (claim, evidence) in enumerate((
            ("外部材料称800G供应链短缺可能导致交付延期。", "外部文章记录800G供应链短缺与延期风险。"),
            ("外部材料称客户认证节奏仍需观察。", "外部文章讨论客户认证进度。"),
            ("外部材料称海外政策变化带来新增变量。", "外部文章讨论海外政策变化。"),
        ))
    )

    selected, diagnostics = select_incremental_external_display_rows(
        rows, {2: {"source": "外部A"}, 3: {"source": "外部B"}, 4: {"source": "外部C"}}, (owner,),
    )

    assert len(selected) == 3
    assert {row.argument_key for row in selected} == {"argument:0", "argument:1", "argument:2"}
    relations = {row.argument_key: row.owner_relation for row in selected}
    assert relations["argument:0"] == "owner_delta"
    assert relations["argument:2"] == "outside_owner"
    assert diagnostics["external_incremental_selected_count"] == 3


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


def test_select_annual_display_rows_applies_role_budget_without_rewriting_admission_count():
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

    assert len(selected) == 2
    assert diagnostics["annual_selected_count"] == 16
    assert diagnostics["annual_hidden_count"] == 14
    assert diagnostics["annual_hidden_by_role"] == {"operating_progress": 14}


def test_formal_medium_view_model_assigns_portrait_slot_and_keeps_distinct_external_projections():
    annual_rows = (
        _annual_display_row(
            "公司主营业务为高速互连产品研发，产品服务于云计算客户。",
            role="business_structure",
            ref=1,
            row_id="annual:portrait",
        ),
        _annual_display_row(
            "报告期内，公司完成下一代产品验证并导入重点客户。",
            role="operating_progress",
            ref=2,
            row_id="annual:operating",
        ),
    )
    external_rows = (
        MaterialRow(
            "external:argument_cards:reasoning:0", "供应链变量", "external", "external_observation", (3,), ("external:reasoning",),
            title="供应链观察", body="外部材料称上游供给节奏仍需验证。", render_role="external_variable",
        ),
        MaterialRow(
            "external:argument_cards:narrative:0", "客户变量", "external", "external_observation", (4,), ("external:narrative",),
            title="客户验证", body="外部材料称重点客户验证节奏仍需观察。", render_role="external_variable",
        ),
    )
    snapshot = MaterialSnapshot(
        "deep_analysis_material_snapshot.v1",
        annual_rows + external_rows,
        {
            1: {"source": "公司年报"}, 2: {"source": "公司年报"},
            3: {"source": "微信公众号精选观察"}, 4: {"source": "微信公众号精选观察"},
        },
        {},
    )

    view_model = build_chapter4_view_model(snapshot, {"profile": "formal_medium"})

    annual = view_model.section("4.1").rows
    external = view_model.section("4.3").rows
    assert next(row for row in annual if row.row_id == "annual:portrait").editorial_slot == "portrait"
    assert [row.row_id for row in external] == [
        "external:argument_cards:reasoning:0",
        "external:argument_cards:narrative:0",
    ]


def test_incremental_external_selector_keeps_owner_superset_with_new_event_delta():
    owner = MaterialRow(
        "annual:owner", "官方材料", "annual", "formal_explanation", (1,), ("annual:owner",),
        body="公司800G产品已进入批量交付阶段。", render_role="operating_progress",
    )
    external = MaterialRow(
        "external:argument_cards:narrative:0", "外部观察", "external", "external_observation", (2,), ("external:0",),
        title="交付变化", body="外部材料称公司800G产品已进入批量交付阶段，光芯片短缺可能导致后续交付延期。",
        render_role="external_variable",
    )

    selected, diagnostics = select_incremental_external_display_rows(
        (external,), {2: {"source": "外部观察"}}, (owner,),
    )

    assert [row.row_id for row in selected] == [external.row_id]
    assert dict(selected[0].diagnostics)["external_incremental_reason"] == "new_event_variable"
    assert diagnostics["external_incremental_selected_count"] == 1


def test_incremental_external_selector_rejects_owner_theme_without_delta():
    owner = MaterialRow(
        "broker:owner", "机构观点", "broker", "professional_analysis", (1,), ("broker:owner",),
        body="800G产品主要面向数据中心客户。", render_role="broker_assumption", attribution="测试证券",
    )
    external = MaterialRow(
        "external:argument_cards:narrative:0", "外部观察", "external", "external_observation", (2,), ("external:0",),
        title="产品观察", body="外部文章认为数据中心客户正在使用800G产品。", render_role="external_variable",
    )

    selected, diagnostics = select_incremental_external_display_rows(
        (external,), {2: {"source": "外部观察"}}, (owner,),
    )

    assert selected == ()
    assert diagnostics["external_incremental_rejected_by_reason"] == {"owner_theme_without_delta": 1}


def test_incremental_external_selector_rejects_rephrased_existing_event():
    owner = MaterialRow(
        "annual:owner", "官方材料", "annual", "formal_explanation", (1,), ("annual:owner",),
        body="公司800G产品交付节奏保持稳定。", render_role="operating_progress",
    )
    external = MaterialRow(
        "external:argument_cards:narrative:0", "外部观察", "external", "external_observation", (2,), ("external:0",),
        body="外部文章指出800G产品维持稳定交付节奏。", render_role="external_variable",
    )

    selected, diagnostics = select_incremental_external_display_rows(
        (external,), {2: {"source": "外部观察"}}, (owner,),
    )

    assert selected == ()
    assert diagnostics["external_incremental_rejected_by_reason"] == {"owner_theme_without_delta": 1}


def test_incremental_external_selector_keeps_new_event_without_numeric_anchor():
    owner = MaterialRow(
        "annual:owner", "官方材料", "annual", "formal_explanation", (1,), ("annual:owner",),
        body="公司订单已覆盖核心客户。", render_role="operating_progress",
    )
    external = MaterialRow(
        "external:argument_cards:narrative:0", "外部观察", "external", "external_observation", (2,), ("external:0",),
        body="外部材料称订单仍需通过客户认证。", render_role="external_variable",
    )

    selected, _ = select_incremental_external_display_rows(
        (external,), {2: {"source": "外部观察"}}, (owner,),
    )

    assert dict(selected[0].diagnostics)["external_incremental_reason"] == "new_event_variable"


def test_incremental_external_selector_falls_through_rejected_narrative_bucket():
    owner = MaterialRow(
        "annual:owner", "官方材料", "annual", "formal_explanation", (1,), ("annual:owner",),
        body="公司800G产品已进入客户验证阶段。", render_role="technology_product_progress",
    )
    rows = (
        MaterialRow(
            "external:argument_cards:narrative:0", "重复观察", "external", "external_observation", (2,), ("external:0",),
            title="客户验证", body="外部材料称公司800G产品已进入客户验证阶段。", render_role="external_variable",
        ),
        MaterialRow(
            "external:argument_cards:reasoning:0", "增量观察", "external", "external_observation", (3,), ("external:1",),
            title="量产节奏", body="外部材料称800G产品量产时间由2026Q4延期至2027Q1。", render_role="external_variable",
        ),
    )

    selected, diagnostics = select_incremental_external_display_rows(
        rows, {2: {"source": "外部观察"}, 3: {"source": "外部观察"}}, (owner,),
    )

    assert [row.row_id for row in selected] == ["external:argument_cards:reasoning:0"]
    assert diagnostics["external_incremental_rejected_by_reason"] == {"owner_text_duplicate": 1}


def test_incremental_external_selector_keeps_uncovered_context_without_anchor():
    owner = MaterialRow(
        "annual:owner", "官方材料", "annual", "formal_explanation", (1,), ("annual:owner",),
        body="公司主营业务为芯片设计。", render_role="business_structure",
    )
    external = MaterialRow(
        "external:argument_cards:topic:market:0", "外部观察", "external", "external_observation", (2,), ("external:0",),
        title="渠道库存", body="渠道库存变化仍值得持续观察。", render_role="external_variable",
    )

    selected, _ = select_incremental_external_display_rows(
        (external,), {2: {"source": "外部观察"}}, (owner,),
    )

    assert dict(selected[0].diagnostics)["external_incremental_reason"] == "new_topic_context"


def test_incremental_external_selector_recognizes_new_units_and_acronym_anchors():
    owner = MaterialRow(
        "annual:owner", "官方材料", "annual", "formal_explanation", (1,), ("annual:owner",),
        body="公司CPO与800G产品处于客户导入阶段。", render_role="technology_product_progress",
    )
    rows = (
        MaterialRow(
            "external:argument_cards:narrative:0", "交付观察", "external", "external_observation", (2,), ("external:0",),
            body="外部材料称800G交付计划由1500万下调至1200万。", render_role="external_variable",
        ),
        MaterialRow(
            "external:argument_cards:narrative:1", "路线观察", "external", "external_observation", (3,), ("external:1",),
            body="外部材料称NPO与XPO路线可能在2027Q1进入验证。", render_role="external_variable",
        ),
    )

    selected, _ = select_incremental_external_display_rows(
        rows, {2: {"source": "外部观察"}, 3: {"source": "外部观察"}}, (owner,),
    )

    assert [dict(row.diagnostics)["external_incremental_reason"] for row in selected] == [
        "new_concrete_anchor", "new_concrete_anchor",
    ]


def test_formal_medium_rejected_external_row_stays_out_of_4_3_and_4_4():
    rows = (
        _annual_display_row(
            "公司CPO产品已进入客户验证阶段。", role="technology_product_progress",
            ref=1, row_id="annual:technology",
        ),
        MaterialRow(
            "external:argument_cards:narrative:0", "重复观察", "external", "external_observation", (2,), ("external:0",),
            title="客户验证", body="外部材料称公司CPO产品已进入客户验证阶段。", render_role="external_variable",
        ),
    )
    snapshot = MaterialSnapshot(
        "deep_analysis_material_snapshot.v1", rows,
        {1: {"source": "公司年报"}, 2: {"source": "外部观察"}}, {},
    )

    view_model = build_chapter4_view_model(snapshot, {"profile": "formal_medium"})

    assert not view_model.section("4.3").rows
    assert all(row.source_layer != "external" for row in view_model.section("4.4").rows)
    assert view_model.diagnostics["external_incremental_rejected_by_reason"] == {"owner_text_duplicate": 1}


def test_formal_medium_price_path_falls_back_to_cited_generic_broker_assumption():
    rows = (
        MaterialRow("annual:generic", "业务", "annual", "formal_explanation", (1,), ("annual:generic",), title="财务质量与变化原因", body="公司主营业务为芯片设计并服务工业客户。", render_role="business_structure", argument_complete=True),
        MaterialRow("broker:generic", "观点", "broker", "professional_analysis", (2,), ("broker:generic",), title="券商核心观点", body="研报认为产品放量支撑增长。", render_role="broker_assumption", attribution="测试证券"),
        MaterialRow("external:generic", "观察", "external", "external_observation", (3,), ("external:generic",), title="反方风险", body="外部材料称供应链需要验证。", render_role="external_variable"),
    )
    snapshot = MaterialSnapshot(
        "deep_analysis_material_snapshot.v1", rows,
        {1: {"source": "公司年报"}, 2: {"source": "券商研报"}, 3: {"source": "微信公众号精选观察"}}, {},
    )

    view_model = build_chapter4_view_model(snapshot, {"profile": "formal_medium"})

    price_path_rows = view_model.section("4.4").rows
    broker = next(row for row in price_path_rows if row.source_layer == "broker")
    assert broker.row_id == "broker:generic"
    assert broker.title == "测试证券研报核心假设"
    assert broker.body == "研报认为产品放量支撑增长。"


def test_formal_medium_price_path_generic_broker_fallback_never_uses_risk_row():
    rows = (
        MaterialRow("annual:generic", "业务", "annual", "formal_explanation", (1,), ("annual:generic",), title="财务质量与变化原因", body="公司主营业务为芯片设计并服务工业客户。", render_role="business_structure", argument_complete=True),
        MaterialRow("broker:risk", "风险", "broker", "professional_analysis", (2,), ("broker:risk",), title="风险提示", body="研报提示需求不及预期。", render_role="broker_risk", attribution="测试证券"),
    )
    snapshot = MaterialSnapshot(
        "deep_analysis_material_snapshot.v1", rows,
        {1: {"source": "公司年报"}, 2: {"source": "券商研报"}}, {},
    )

    view_model = build_chapter4_view_model(snapshot, {"profile": "formal_medium"})

    assert all(row.source_layer != "broker" for row in view_model.section("4.4").rows)


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
    assert price_path_annual[0].row_id == "annual:confirmed:0"


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
    assert rows_by_id["external:argument_cards:0"].source_layer == "external"
    assert rows_by_id["external:argument_cards:0"].section_hint == "external_map"

    all_refs = {ref for row in snapshot.rows for ref in row.citation_refs}
    assert all_refs
    assert all(ref in snapshot.citations for ref in all_refs)
    assert rows_by_id["annual:confirmed:0"].citation_refs == (1,)
    assert rows_by_id["broker:sections:0"].citation_refs == (3,)
    assert rows_by_id["external:argument_cards:0"].citation_refs == (6,)


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
    external_row = next(row for row in view_model.section("4.3").rows if row.row_id == "external:argument_cards:0")
    assert annual_row.title == "营业收入"
    assert annual_row.body == "营业收入 10 亿元"
    assert annual_row.render_role == "financial_quality_explanation"
    assert annual_row.argument_complete is False
    assert broker_row.render_role == "broker_assumption"
    assert broker_row.attribution == "测试证券"
    assert external_row.render_role == "external_variable"
    assert external_row.title == "供应链与交付"
    assert external_row.external_claim == "外部文章讨论 CPO 路线分歧。"
    assert external_row.external_evidence == "外部文章讨论 CPO 路线分歧。"
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
