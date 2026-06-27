"""Tests for curated external evidence-card pilot inputs."""

import hashlib
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "stocks.json"

sys.path.insert(0, str(REPO_ROOT / "scripts" / "utils"))
from curated_external_evidence_card_synthesis_items import (
    load_curated_external_evidence_card_synthesis_items,
)


def _normalized_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _stock_by_name(name: str) -> dict:
    stocks = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for stock in stocks:
        if stock.get("name") == name:
            return stock
    raise AssertionError(f"missing stock config: {name}")


def test_curated_external_black_sesame_pilot_references_committed_evidence_cards():
    stock = _stock_by_name("黑芝麻智能")
    source_intake = stock.get("source_intake") or {}
    pilot = source_intake.get("curated_external_evidence_cards_synthesis_display") or {}

    assert source_intake.get("enabled") is True
    assert pilot.get("enabled") is True
    assert pilot.get("min_cards") == 2
    assert pilot.get("min_total_excerpt_chars", 0) >= 600

    cards_path = REPO_ROOT / pilot["cards_json"]
    assert cards_path.exists()

    payload = json.loads(cards_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "curated_external_evidence_cards.v1"
    assert payload["wrote_knowledge"] is False
    assert payload["connected_synthesis"] is False
    assert len(payload.get("cards") or []) >= 2


def test_curated_external_zhongji_pending_pilot_config_and_fidelity():
    stock = _stock_by_name("中际旭创")
    source_intake = stock.get("source_intake") or {}
    pilot = source_intake.get("curated_external_evidence_cards_synthesis_display") or {}

    assert source_intake.get("enabled") is True
    assert pilot.get("enabled") is False
    assert pilot.get("cards_json") == "data/curated_external/evidence_cards/zhongjixuchuang_20260627.json"
    assert pilot.get("max_display_items") == 8
    assert pilot.get("min_cards") == 3
    assert pilot.get("min_total_excerpt_chars") == 1200

    cards_path = REPO_ROOT / pilot["cards_json"]
    assert cards_path.exists()

    payload = json.loads(cards_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "curated_external_evidence_cards.v1"
    assert payload["wrote_knowledge"] is False
    assert payload["connected_synthesis"] is False

    cards = payload.get("cards") or []
    assert len(cards) >= 3

    # Fidelity: source_excerpt must match its stated hash (no post-hoc rewriting).
    for card in cards:
        assert card.get("source_type") == "curated_external_analysis_evidence"
        assert card.get("knowledge_eligible") is not True
        assert card.get("scoring_eligible") is not True
        assert card.get("risk_score_eligible") is not True
        expected = card.get("source_excerpt_hash")
        actual = _normalized_hash(card.get("source_excerpt", ""))
        assert expected == actual, f"{card.get('card_id')}: source_excerpt/hash mismatch"

    # With the original (unmodified) enriched cards, the loader must reject them
    # for quality reasons (short metadata excerpts / noisy titles).  This proves
    # we are not bypassing the gate with hand-written summaries.
    items, stats = load_curated_external_evidence_card_synthesis_items(
        str(cards_path),
        max_items=pilot.get("max_display_items", 8),
        min_cards=pilot.get("min_cards", 3),
        min_total_excerpt_chars=pilot.get("min_total_excerpt_chars", 1200),
    )
    assert items == []
    assert stats["status"] != "ok"
    assert stats["cards_seen"] == len(cards)
    assert stats["cards_eligible"] == 0
    reasons = " ".join(stats.get("rejection_reasons") or []).lower()
    assert any(
        kw in reasons
        for kw in [
            "excerpt length",
            "title quality",
            "report metadata",
            "product_roadmap",
        ]
    )
