"""Tests for the deep-analysis MaterialSnapshot read-model."""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from deep_analysis_material_snapshot import (  # noqa: E402
    EvidenceRow,
    build_deep_analysis_material_snapshot,
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
                    }
                ],
                "annual_report_explanation": [
                    {
                        "title": "管理层讨论",
                        "body": "公司解释增长来自 FPGA。",
                        "internal_refs": ["annual:card:management"],
                        "citation_refs": [2],
                        "source_ref_ids": ["annual-source:management"],
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


def test_snapshot_projects_annual_broker_and_external_rows_with_global_citations():
    snapshot = build_deep_analysis_material_snapshot(_ctx())

    assert snapshot.schema == "deep_analysis_material_snapshot.v1"
    assert all(isinstance(row, EvidenceRow) for row in snapshot.rows)
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
