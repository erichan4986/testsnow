"""Tests for curated external evidence-card pilot inputs."""

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "stocks.json"


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


def test_curated_external_zhongji_is_not_enabled_until_cards_pass_gate():
    stocks = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    stock = next((item for item in stocks if item.get("name") == "中际旭创"), None)
    if stock is None:
        return

    source_intake = stock.get("source_intake") or {}
    pilot = source_intake.get("curated_external_evidence_cards_synthesis_display") or {}
    assert pilot.get("enabled") is not True
