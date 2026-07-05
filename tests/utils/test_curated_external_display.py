"""Tests for curated external display normalization."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from curated_external_display import normalize_viewpoint_narrative_reasoning_cards


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
    from curated_external_display import build_curated_external_narrative_display
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

    result = build_curated_external_narrative_display(str(path))
    display = result["display"]
    assert display["_curated_external_reasoning_cards"]
    card = display["_curated_external_reasoning_cards"][0]
    assert card["claim_id"] == "c1"
    assert card["claim"] == "外部观点"
    assert card["reasoning_steps"]
    assert card["citation_refs"] == [1]
