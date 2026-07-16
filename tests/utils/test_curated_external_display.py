"""Tests for curated external display normalization."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from curated_external_display import (
    build_curated_external_narrative_display,
    classify_external_source_title,
    hydrate_viewpoint_narrative_citation_refs,
    normalize_viewpoint_narrative_reasoning_cards,
)


def test_template_reasoning_card_is_enriched_from_claim_and_numbers():
    cards = [
        {
            "claim_id": "c1",
            "display_topic": "valuation_debate",
            "claim": "A股估值处于乐观情景上沿，港股折价约50%",
            "source_excerpt": "A股现价偏贵25-40%，港股折价约50%。",
            "reasoning_steps": ["外部材料提出该增量变量，需与公司交付能力、上游供给和下游需求交叉验证。"],
            "numbers_used": ["25-40%", "50%"],
            "assumptions": ["该变量仍属外部观察，未获官方确认。"],
            "counterpoints": ["若下游需求或公司交付节奏不及预期，该变量可能失效。"],
            "verification_need": "跟踪后续公告、订单或行业数据以验证该论断。",
            "citation_refs": [1],
        }
    ]
    citations = {
        1: {
            "claim_id": "c1",
            "source_type": "curated_external_analysis_evidence",
            "verification_status": "professional_observation",
        }
    }

    normalized = normalize_viewpoint_narrative_reasoning_cards(cards, citations)

    card = normalized[0]
    assert card["reasoning_steps"] != ["外部材料提出该增量变量，需与公司交付能力、上游供给和下游需求交叉验证。"]
    assert "25-40%" in "；".join(card["reasoning_steps"])
    assert card["assumptions"] != ["该变量仍属外部观察，未获官方确认。"]
    assert card["counterpoints"] != ["若下游需求或公司交付节奏不及预期，该变量可能失效。"]
    assert card["verification_need"] != "跟踪后续公告、订单或行业数据以验证该论断。"


def test_build_narrative_display_preserves_reasoning_card_metadata(tmp_path):
    import json

    narrative = {
        "schema_version": "curated_external_viewpoint_narrative.v1",
        "status": "ok",
        "stock_name": "测试股",
        "paragraphs": [
            {"heading": "测试主题", "text": "外部材料提示变量。[^1]", "citation_refs": [1]}
        ],
        "reasoning_cards": [
            {
                "claim_id": "c1",
                "claim": "外部观点",
                "source_excerpt": "原文",
                "reasoning_steps": ["步骤1"],
                "numbers_used": ["10%"],
                "assumptions": ["假设"],
                "counterpoints": ["反方"],
                "verification_need": "验证",
            }
        ],
        "citations": {
            "1": {
                "source_type": "curated_external_analysis_evidence",
                "verification_status": "professional_observation",
                "claim_id": "c1",
            }
        },
        "stats": {"lint": {"ok": True, "violations": []}},
    }
    path = tmp_path / "narrative.json"
    path.write_text(json.dumps(narrative, ensure_ascii=False), encoding="utf-8")

    result = build_curated_external_narrative_display(
        str(path), expected_stock_name="测试股",
    )
    display = result["display"]
    assert display["_curated_external_reasoning_cards"]
    card = display["_curated_external_reasoning_cards"][0]
    assert card["claim_id"] == "c1"
    assert card["claim"] == "外部观点"
    assert card["reasoning_steps"]
    assert card["citation_refs"] == [1]


def test_build_narrative_display_dedupes_exact_url_and_remaps_cached_claim_refs(tmp_path):
    import json

    citation = {
        "source_type": "curated_external_analysis_evidence",
        "verification_status": "professional_observation",
        "source": "微信公众号精选观察",
        "url": "https://example.com/shared",
    }
    narrative = {
        "schema_version": "curated_external_viewpoint_narrative.v1",
        "status": "ok",
        "stock_name": "测试股",
        "paragraphs": [
            {"heading": "变量一", "text": "外部材料称：第一条观察。", "citation_refs": [1]},
            {"heading": "变量二", "text": "外部材料称：第二条观察。", "citation_refs": [2]},
            {"heading": "变量三", "text": "外部材料称：第三条观察。", "claim_refs": ["c2"]},
        ],
        "reasoning_cards": [{"claim_id": "c2", "claim": "第二条观察", "citation_refs": [2]}],
        "citations": {
            "1": {**citation, "claim_id": "c1"},
            "2": {**citation, "claim_id": "c2"},
        },
        "stats": {"lint": {"ok": True, "violations": []}},
    }
    path = tmp_path / "narrative.json"
    path.write_text(json.dumps(narrative, ensure_ascii=False), encoding="utf-8")

    display = build_curated_external_narrative_display(
        str(path), expected_stock_name="测试股",
    )["display"]

    assert set(display["citations"]) == {1}
    assert [row["citation_refs"] for row in display["_curated_external_narrative_paragraphs"]] == [[1], [1], [1]]
    assert display["_curated_external_reasoning_cards"][0]["citation_refs"] == [1]
    assert display["citations"][1]["claim_ids"] == ["c1", "c2"]


def test_hydrate_cached_paragraph_rebuilds_refs_when_existing_refs_are_stale():
    paragraphs = [
        {
            "heading": "订单节奏",
            "text": "外部材料称订单节奏仍需验证。",
            "claim_refs": ["claim:c1"],
            "citation_refs": [99],
        }
    ]
    citations = {1: {"claim_id": "claim:c1"}}

    hydrated = hydrate_viewpoint_narrative_citation_refs(
        paragraphs,
        citations,
        citation_ref_map={2: 1},
    )

    assert hydrated[0]["citation_refs"] == [1]


def test_cached_display_drops_foreign_target_claim_and_keeps_safe_card_only(tmp_path):
    import json

    narrative = {
        "schema_version": "curated_external_viewpoint_narrative.v1",
        "status": "ok",
        "stock_name": "复旦微电",
        "paragraphs": [{
            "heading": "混合观察",
            "text": "复旦微电子EEPROM业务存在外部变量。",
            "claim_refs": ["fudan-foreign", "fudan-safe"],
        }],
        "reasoning_cards": [
            {
                "claim_id": "fudan-foreign",
                "claim": "复旦微电子EEPROM业务已经进入客户供应链。",
                "source_excerpt": "复旦微电子EEPROM业务已经进入客户供应链。",
            },
            {
                "claim_id": "fudan-safe",
                "claim": "复旦微电子新产品认证节奏仍需验证。",
                "source_excerpt": "复旦微电子新产品认证节奏仍需验证。",
            },
        ],
        "citations": {
            "1": {
                "source_type": "curated_external_analysis_evidence",
                "verification_status": "professional_observation",
                "claim_id": "fudan-foreign",
                "title": "聚辰股份: EEPROM产品导入进展",
            },
            "2": {
                "source_type": "curated_external_analysis_evidence",
                "verification_status": "professional_observation",
                "claim_id": "fudan-safe",
                "title": "复旦微电: 新产品认证观察",
            },
        },
    }
    path = tmp_path / "narrative.json"
    path.write_text(json.dumps(narrative, ensure_ascii=False), encoding="utf-8")

    result = build_curated_external_narrative_display(
        str(path), expected_stock_name="复旦微电",
    )

    assert result["status"] == "ok"
    display = result["display"]
    assert display["_curated_external_narrative_paragraphs"] == []
    assert [card["claim_id"] for card in display["_curated_external_reasoning_cards"]] == ["fudan-safe"]
    assert set(display["citations"]) == {2}


def test_cached_display_rejects_mismatched_stock_identity_before_loading(tmp_path):
    import json

    path = tmp_path / "narrative.json"
    path.write_text(json.dumps({"status": "ok", "stock_name": "聚辰股份"}), encoding="utf-8")

    result = build_curated_external_narrative_display(
        str(path), expected_stock_name="复旦微电",
    )

    assert result["status"] == "stock_identity_mismatch"
    assert result["display"] is None


def test_cached_hydration_does_not_bind_ambiguous_claim_suffix():
    hydrated = hydrate_viewpoint_narrative_citation_refs(
        [{"text": "外部材料称变量仍需验证。", "claim_refs": ["same"]}],
        {1: {"claim_id": "left:same"}, 2: {"claim_id": "right:same"}},
    )

    assert "citation_refs" not in hydrated[0]


def test_cached_display_keeps_peer_context_under_preview_heading(tmp_path):
    import json

    narrative = {
        "schema_version": "curated_external_viewpoint_narrative.v1",
        "status": "ok",
        "stock_name": "复旦微电",
        "reasoning_cards": [{
            "claim_id": "peer",
            "claim": "聚辰股份EEPROM产品竞争格局仍可能影响行业定价。",
            "source_excerpt": "聚辰股份EEPROM产品竞争格局仍可能影响行业定价。",
        }],
        "citations": {"1": {
            "source_type": "curated_external_analysis_evidence",
            "verification_status": "professional_observation",
            "claim_id": "peer",
            "title": "聚辰股份: EEPROM竞争格局观察",
        }},
    }
    path = tmp_path / "narrative.json"
    path.write_text(json.dumps(narrative, ensure_ascii=False), encoding="utf-8")

    display = build_curated_external_narrative_display(
        str(path), expected_stock_name="复旦微电",
    )["display"]

    card = display["_curated_external_reasoning_cards"][0]
    assert card["entity_context"] == "peer_or_industry_context"
    assert card["heading"] == "同业/行业背景（Preview）"
    assert card["citation_refs"] == [1]


def test_unknown_source_title_stays_ambiguous():
    assert classify_external_source_title("行业观察：EEPROM供需变化", "复旦微电") == "ambiguous"
