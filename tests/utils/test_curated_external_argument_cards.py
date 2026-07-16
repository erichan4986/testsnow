"""Tests for deterministic curated external argument cards."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from curated_external_argument_cards import (  # noqa: E402
    ARGUMENT_CARD_SCHEMA,
    build_external_argument_cards,
)


def _digest_claim(**overrides):
    quote = "市场传言中际旭创800G交付计划从1500万只下调至1200万只，公司已否认该传言。"
    claim = {
        "schema_version": "curated_external_viewpoint_claim.v1",
        "claim_id": "claim:delivery",
        "stock_name": "中际旭创",
        "claim_type": "watch_variable",
        "topic": "供应链交付",
        "claim": "中际旭创800G交付计划下调传言仍需验证。",
        "source_quote": quote,
        "source_quote_hash": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
        "why_incremental": "baseline未涉及该交付传言及回应。",
        "baseline_overlap": "none",
        "source_id": "source:wechat:1",
        "source_title": "中际旭创：交付计划传言与回应",
        "source_account": "测试作者",
        "source_kind": "wechat",
        "source_ref": "https://example.com/delivery",
        "source_url": "https://example.com/delivery",
        "verification_status": "professional_observation",
        "source_credit": 55,
        "quality_action": "preview_only",
        "knowledge_eligible": False,
        "synthesis_display_only": True,
        "scoring_eligible": False,
        "risk_score_eligible": False,
    }
    claim.update(overrides)
    if "source_quote" in overrides and "source_quote_hash" not in overrides:
        claim["source_quote_hash"] = hashlib.sha256(claim["source_quote"].encode("utf-8")).hexdigest()
    return claim


def _citation(claim_id="card:fpga", title="复旦微电：FPGA竞争格局"):
    return {
        "claim_id": claim_id,
        "source": "知乎精选观察",
        "title": title,
        "url": "https://example.com/fpga",
        "source_type": "curated_external_analysis_evidence",
        "verification_status": "professional_observation",
        "source_credit": 55,
    }


def test_digest_claim_builds_verified_source_argument_card():
    result = build_external_argument_cards(
        stock_name="中际旭创",
        digest_claims=[_digest_claim()],
    )

    assert result["stats"]["accepted_count"] == 1
    card = result["cards"][0]
    assert card["schema_version"] == ARGUMENT_CARD_SCHEMA
    assert card["entity_scope"] == "target"
    assert card["topic_family"] == "capacity_delivery"
    assert card["evidence_units"][0]["evidence_status"] == "source_quote_verified"
    assert card["evidence_units"][0]["text"].startswith("市场传言")
    assert card["citation_refs"] == [1]
    assert result["citations"][1]["url"] == "https://example.com/delivery"
    assert card["scoring_eligible"] is False
    assert card["risk_score_eligible"] is False


def test_narrative_reasoning_card_builds_cached_excerpt_argument_card():
    result = build_external_argument_cards(
        stock_name="复旦微电",
        narrative_cards=[{
            "claim_id": "card:fpga",
            "display_topic": "FPGA产品与竞争",
            "claim": "复旦微电与国内FPGA同业形成差异化竞争。",
            "source_excerpt": "复旦微电走高可靠赛道，紫光同创专注通信，安路科技主攻民用市场。",
            "citation_refs": [7],
        }],
        citations={7: _citation()},
    )

    card = result["cards"][0]
    assert card["entity_scope"] == "target_with_peer_context"
    assert card["topic_family"] == "technology_product"
    assert card["evidence_units"][0]["evidence_status"] == "cached_excerpt"
    assert card["display_title"].endswith("（对比观察）")
    assert card["citation_refs"] == [7]


def test_digest_quote_wins_when_same_claim_also_has_narrative_card():
    result = build_external_argument_cards(
        stock_name="中际旭创",
        digest_claims=[_digest_claim()],
        narrative_cards=[{
            "claim_id": "claim:delivery",
            "display_topic": "供应链",
            "claim": "中际旭创800G交付计划下调传言仍需验证。",
            "source_excerpt": "缓存材料摘录。",
            "citation_refs": [9],
        }],
        citations={9: _citation("claim:delivery", "中际旭创：缓存观察")},
    )

    assert len(result["cards"]) == 1
    assert result["cards"][0]["evidence_units"][0]["evidence_status"] == "source_quote_verified"
    assert result["stats"]["merged_input_count"] == 1


def test_claim_number_or_model_missing_from_evidence_is_rejected():
    result = build_external_argument_cards(
        stock_name="中际旭创",
        digest_claims=[_digest_claim(
            claim="中际旭创1.6T产品将在2028年贡献30亿元收入。",
            source_quote="外部文章讨论了中际旭创新产品路线。",
        )],
    )

    assert result["cards"] == []
    assert result["stats"]["rejected_by_reason"]["unsupported_claim_anchor"] == 1


def test_digest_quote_hash_must_match_normalized_evidence():
    result = build_external_argument_cards(
        stock_name="中际旭创",
        digest_claims=[_digest_claim(source_quote_hash="mismatch")],
    )

    assert result["cards"] == []
    assert result["stats"]["rejected_by_reason"]["invalid_digest_claim"] == 1


def test_foreign_only_source_cannot_support_target_company_fact():
    result = build_external_argument_cards(
        stock_name="复旦微电",
        narrative_cards=[{
            "claim_id": "foreign",
            "display_topic": "EEPROM产品",
            "claim": "复旦微电EEPROM已经进入客户供应链。",
            "source_excerpt": "复旦微电EEPROM已经进入客户供应链。",
            "citation_refs": [1],
        }],
        citations={1: _citation("foreign", "聚辰股份：EEPROM产品导入进展")},
    )

    assert result["cards"] == []
    assert result["stats"]["rejected_by_reason"]["foreign_only_target_claim"] == 1


def test_peer_only_card_is_retained_as_preview_context_without_target_attribution():
    result = build_external_argument_cards(
        stock_name="复旦微电",
        narrative_cards=[{
            "claim_id": "peer",
            "display_topic": "行业竞争格局",
            "claim": "紫光同创在通信FPGA市场保持较高份额。",
            "source_excerpt": "紫光同创在5G通信FPGA市场的份额超过60%。",
            "citation_refs": [2],
        }],
        citations={2: _citation("peer", "紫光同创：通信FPGA进展")},
    )

    card = result["cards"][0]
    assert card["entity_scope"] == "peer_or_industry"
    assert card["display_title"] == "同业/行业背景（Preview）"
    assert "复旦微电" not in card["claim"]


def test_same_url_same_argument_is_deduped_but_distinct_argument_is_kept():
    shared = "https://example.com/shared"
    claims = [
        _digest_claim(claim_id="c1", source_ref=shared, source_url=shared),
        _digest_claim(claim_id="c2", source_ref=shared, source_url=shared),
        _digest_claim(
            claim_id="c3",
            topic="客户需求指引",
            claim="中际旭创2027年客户需求指引仍需跟踪。",
            source_quote="外部文章称中际旭创2027年客户需求指引仍需跟踪。",
            source_quote_hash=hashlib.sha256("外部文章称中际旭创2027年客户需求指引仍需跟踪。".encode("utf-8")).hexdigest(),
            source_ref=shared,
            source_url=shared,
        ),
    ]

    result = build_external_argument_cards(stock_name="中际旭创", digest_claims=claims)

    assert len(result["cards"]) == 2
    assert len({card["argument_key"] for card in result["cards"]}) == 2
    assert len(result["citations"]) == 1
    assert result["stats"]["deduped_count"] == 1
