from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_narrative_pack_store import (  # noqa: E402
    PeriodicNarrativePackStorageError,
    load_validated_periodic_narrative_pack_set,
    normalized_source_excerpt_hash,
    periodic_narrative_stock_root,
    write_periodic_report_narrative_pack,
)


def _card(
    *, card_id: str = "annual-argument:0123456789abcdef0123", unit_id: str = "rd-0:u0", block_id: str = "rd-0"
) -> dict:
    excerpt = "公司研发投入18%，新产品完成客户验证。"
    return {
        "schema_version": "periodic_report_narrative_evidence_card.v2",
        "selection_version": "annual_argument_selection.v2",
        "card_id": card_id,
        "argument_family": "technology_product_progress",
        "argument_complete": True,
        "title": "技术与产品进展",
        "source_block_id": block_id,
        "source_unit_ids": [unit_id],
        "source_units": [{
            "unit_id": unit_id,
            "block_id": block_id,
            "ordinal": 0,
            "start_pos": 0,
            "end_pos": len(excerpt),
            "text": excerpt,
        }],
        "source_excerpt": excerpt,
        "fact_anchors": ["研发投入18%"],
        "secondary_signals": ["operating_progress"],
        "score_parts": {"anchored_fact": 1, "argument_complete": 4, "source_unit_count": 1},
        "quality_score": 6,
        "selection_reason": "signal:technology_product_progress",
        "source_type": "periodic_report_narrative_evidence",
        "source_credit": 75,
        "report_year": 2025,
        "report_type": "annual",
    }


def _pack(cards: list[dict], *, candidates: list[dict] | None = None, diagnostics: dict | None = None) -> dict:
    return {
        "schema_version": "periodic_report_narrative_evidence_cards.v2",
        "selection_version": "annual_argument_selection.v2",
        "stock_code": "300308",
        "stock_name": "中际旭创",
        "report_year": 2025,
        "report_type": "annual",
        "cards": cards,
        "candidate_cards": list(cards if candidates is None else candidates),
        "diagnostics": {} if diagnostics is None else diagnostics,
    }


def test_normalized_source_excerpt_hash_matches_whitespace_normalization() -> None:
    assert normalized_source_excerpt_hash("研发\n投入  18%") == normalized_source_excerpt_hash("研发 投入 18%")


def test_write_bootstraps_manifest_and_roundtrips_validated_pack_set(tmp_path: Path) -> None:
    coverage = {
        "schema_version": "annual_document_coverage_manifest.v1",
        "stage": "producer",
        "status": "ready",
        "summary": {"recognized_section_count": 2},
    }
    card_pack = _pack([_card()], diagnostics={"candidate_count": 1, "coverage_manifest": coverage})

    result = write_periodic_report_narrative_pack(
        stock_name="中际旭创",
        stock_code="300308",
        card_pack=card_pack,
        base_dir=tmp_path,
    )

    assert result.state == "bootstrap"
    assert result.pack_path.exists()
    assert result.manifest_path.exists()
    loaded = load_validated_periodic_narrative_pack_set(
        stock_name="中际旭创", stock_code="300308", base_dir=tmp_path
    )
    assert loaded["cards"] == card_pack["cards"]
    assert loaded["packs"][0]["producer_diagnostics"] == card_pack["diagnostics"]
    assert loaded["packs"][0]["producer_diagnostics"]["coverage_manifest"] == coverage
    assert loaded["entries"] == [{
        "report_year": 2025,
        "report_type": "annual",
        "pack_path": "periodic_narrative_packs/2025-annual.json",
        "cards_sha256": loaded["packs"][0]["integrity"]["cards_sha256"],
        "payload_sha256": loaded["packs"][0]["integrity"]["payload_sha256"],
    }]
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["periods"][0]["pack_path"] == "periodic_narrative_packs/2025-annual.json"


def test_public_stock_root_uses_pack_store_path_sanitization(tmp_path: Path) -> None:
    assert periodic_narrative_stock_root(tmp_path, "../中际/旭创") == (
        tmp_path / "10-Stocks" / "中际-旭创"
    )


def test_writer_rejects_divergent_candidate_cards_without_creating_storage(tmp_path: Path) -> None:
    with pytest.raises(PeriodicNarrativePackStorageError, match="candidate_cards_mismatch"):
        write_periodic_report_narrative_pack(
            stock_name="中际旭创",
            stock_code="300308",
            card_pack=_pack([_card()], candidates=[]),
            base_dir=tmp_path,
        )

    assert not (tmp_path / "10-Stocks").exists()


def test_writer_upserts_existing_valid_manifest_without_dropping_other_period(tmp_path: Path) -> None:
    first = write_periodic_report_narrative_pack(
        stock_name="中际旭创", stock_code="300308", card_pack=_pack([_card()]), base_dir=tmp_path
    )
    second_pack = _pack([_card(card_id="annual-argument:11111111111111111111", unit_id="rd-1:u0", block_id="rd-1")])
    second_pack["report_year"] = 2024
    second_pack["cards"][0]["report_year"] = 2024
    second_pack["candidate_cards"][0]["report_year"] = 2024

    second = write_periodic_report_narrative_pack(
        stock_name="中际旭创", stock_code="300308", card_pack=second_pack, base_dir=tmp_path
    )

    assert second.state == "upsert"
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert [(item["report_year"], item["report_type"]) for item in manifest["periods"]] == [
        (2024, "annual"),
        (2025, "annual"),
    ]


def test_writer_requires_explicit_repair_for_orphan_pack_directory(tmp_path: Path) -> None:
    packs = tmp_path / "10-Stocks" / "中际旭创" / "periodic_narrative_packs"
    packs.mkdir(parents=True)
    (packs / "2024-annual.json").write_text("{}", encoding="utf-8")

    with pytest.raises(PeriodicNarrativePackStorageError, match="repair_required"):
        write_periodic_report_narrative_pack(
            stock_name="中际旭创", stock_code="300308", card_pack=_pack([_card()]), base_dir=tmp_path
        )

    assert not (packs / "2025-annual.json").exists()


def test_loader_rejects_manifest_path_escape(tmp_path: Path) -> None:
    result = write_periodic_report_narrative_pack(
        stock_name="中际旭创", stock_code="300308", card_pack=_pack([_card()]), base_dir=tmp_path
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    manifest["periods"][0]["pack_path"] = "../escape.json"
    manifest["periods_sha256"] = hashlib.sha256(
        json.dumps(manifest["periods"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    result.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(PeriodicNarrativePackStorageError, match="manifest_path_invalid"):
        load_validated_periodic_narrative_pack_set(
            stock_name="中际旭创", stock_code="300308", base_dir=tmp_path
        )
