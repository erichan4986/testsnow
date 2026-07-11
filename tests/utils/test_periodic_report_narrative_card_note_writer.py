from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from periodic_report_narrative_card_note_writer import (
    NarrativeCardWritePlan,
    write_periodic_report_narrative_card_notes,
)


def _normalized_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _card(**overrides):
    card = {
        "schema_version": "periodic_report_narrative_evidence_card.v1",
        "source_type": "periodic_report_narrative_evidence",
        "card_id": "periodic:300308:2025:annual:narrative:management_market_view:0",
        "stock_code": "300308",
        "stock_name": "中际旭创",
        "report_year": 2025,
        "report_type": "annual",
        "card_type": "management_market_view",
        "title": "AI 数据中心需求",
        "source_block_id": "market_demand_outlook-0",
        "evidence_refs": ["market_demand_outlook-0"],
        "source_excerpt": "AI 数据中心建设推动 800G/1.6T 光模块需求增长。",
        "source_credit": 75,
        "knowledge_eligible": False,
        "synthesis_eligible": False,
        "experimental": True,
    }
    card.update(overrides)
    return card


def _pack(cards, **extra):
    pack = {
        "schema_version": "periodic_report_narrative_evidence_cards.v1",
        "stock_code": "300308",
        "stock_name": "中际旭创",
        "report_year": 2025,
        "report_type": "annual",
        "cards": cards,
        "diagnostics": [],
    }
    pack.update(extra)
    return pack


def _v2_card(**overrides):
    first = "公司研发投入占比18%。"
    second = "新产品完成客户验证。"
    card = {
        "schema_version": "periodic_report_narrative_evidence_card.v2",
        "selection_version": "annual_argument_selection.v2",
        "source_type": "periodic_report_narrative_evidence",
        "card_id": "annual-argument:0123456789abcdef0123",
        "stock_code": "300308",
        "stock_name": "中际旭创",
        "report_year": 2025,
        "report_type": "annual",
        "argument_family": "technology_product_progress",
        "argument_complete": True,
        "title": "技术与产品进展",
        "source_block_id": "rd_product_progress-0",
        "source_unit_ids": ["rd_product_progress-0:u0", "rd_product_progress-0:u1"],
        "source_units": [
            {
                "unit_id": "rd_product_progress-0:u0",
                "block_id": "rd_product_progress-0",
                "ordinal": 0,
                "start_pos": 0,
                "end_pos": len(first),
                "text": first,
            },
            {
                "unit_id": "rd_product_progress-0:u1",
                "block_id": "rd_product_progress-0",
                "ordinal": 1,
                "start_pos": len(first),
                "end_pos": len(first) + len(second),
                "text": second,
            },
        ],
        "source_excerpt": first + second,
        "fact_anchors": ["研发投入占比18%"],
        "secondary_signals": ["operating_progress"],
        "score_parts": {"anchored_fact": 1, "argument_complete": 4, "source_unit_count": 1},
        "quality_score": 6,
        "selection_reason": "signal:technology_product_progress",
        "source_credit": 75,
        "knowledge_eligible": False,
        "synthesis_eligible": False,
        "experimental": True,
    }
    card.update(overrides)
    return card


def _cards_dir(base: Path, stock_name: str = "中际旭创") -> Path:
    return base / "10-Stocks" / stock_name / "periodic_narrative_cards"


def test_writes_only_valid_narrative_cards_to_tmp_knowledge(tmp_path) -> None:
    plan = write_periodic_report_narrative_card_notes(
        stock_name="中际旭创",
        stock_code="300308",
        card_pack=_pack([_card()]),
        base_dir=tmp_path,
        collected_at="2026-06-21",
    )

    assert isinstance(plan, NarrativeCardWritePlan)
    assert len(plan.written) == 1
    path = Path(plan.written[0]["planned_path"])
    assert path.exists()
    assert path.parent == _cards_dir(tmp_path)
    assert path.name == "2025-annual-management-market-view-0.md"

    text = path.read_text(encoding="utf-8")
    assert "AI 数据中心" in text
    assert "market_demand_outlook-0" in text
    assert "periodic:300308:2025:annual:narrative:management_market_view:0" in text


def test_writes_complete_v2_card_without_card_type_and_with_json_sections(tmp_path) -> None:
    plan = write_periodic_report_narrative_card_notes(
        stock_name="中际旭创",
        stock_code="300308",
        card_pack=_pack([_v2_card()]),
        base_dir=tmp_path,
        collected_at="2026-06-21",
    )

    path = Path(plan.written[0]["planned_path"])
    assert path.name == "2025-annual-technology-product-progress-0.md"
    text = path.read_text(encoding="utf-8")
    assert "selection_version: annual_argument_selection.v2" in text
    assert "argument_family: technology_product_progress" in text
    assert "argument_complete: true" in text
    assert "card_type:" not in text
    assert "## Source Units" in text
    assert "## Selection Diagnostics" in text
    assert json.dumps(_v2_card()["source_units"], ensure_ascii=False, indent=2, sort_keys=True) in text
    assert json.dumps(
        {"score_parts": _v2_card()["score_parts"], "selection_reason": _v2_card()["selection_reason"]},
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) in text


def test_filters_non_narrative_cards_and_missing_evidence(tmp_path) -> None:
    mixed = [
        _card(),
        _card(
            source_type="periodic_report_filing_fact",
            card_id="periodic:300308:2025:annual:revenue",
        ),
        _card(
            source_type="periodic_report_derived_fact",
            card_id="periodic:300308:2025:annual:ratio",
        ),
        _card(
            card_id="periodic:300308:2025:annual:narrative:financial_note:1",
            card_type="financial_note",
            source_excerpt="",
        ),
    ]

    plan = write_periodic_report_narrative_card_notes(
        stock_name="中际旭创",
        stock_code="300308",
        card_pack=_pack(mixed),
        base_dir=tmp_path,
    )

    assert len(plan.written) == 1
    assert len(plan.filtered) == 3
    files = sorted(p.name for p in _cards_dir(tmp_path).glob("*.md"))
    assert files == ["2025-annual-management-market-view-0.md"]


def test_frontmatter_keeps_card_material_guardrails(tmp_path) -> None:
    plan = write_periodic_report_narrative_card_notes(
        stock_name="中际旭创",
        stock_code="300308",
        card_pack=_pack([_card(knowledge_eligible=True, source_credit=99)]),
        base_dir=tmp_path,
    )

    text = Path(plan.written[0]["planned_path"]).read_text(encoding="utf-8")
    assert "source_type: periodic_report_narrative_evidence" in text
    assert "knowledge_fact_status: narrative_evidence" in text
    assert "knowledge_eligible: false" in text
    assert "knowledge_persisted: true" in text
    assert "synthesis_eligible: false" in text
    assert "experimental: true" in text
    assert "source_credit: 75" in text
    assert "confirmed_fact" not in text
    assert "fact_candidate" not in text
    assert "claim_status" not in text
    assert "verification_status" not in text


def test_note_frontmatter_persists_source_hashes_and_computes_excerpt_hash(tmp_path) -> None:
    card = _card(source_block_hash="a" * 64)
    plan = write_periodic_report_narrative_card_notes(
        stock_name="中际旭创",
        stock_code="300308",
        card_pack=_pack([card]),
        base_dir=tmp_path,
    )

    text = Path(plan.written[0]["planned_path"]).read_text(encoding="utf-8")
    assert f'source_excerpt_hash: "{_normalized_hash(card["source_excerpt"])}"' in text
    assert f"source_block_hash: {'a' * 64}" in text


def test_dry_run_returns_plan_without_writing_file(tmp_path) -> None:
    plan = write_periodic_report_narrative_card_notes(
        stock_name="中际旭创",
        stock_code="300308",
        card_pack=_pack([_card()]),
        base_dir=tmp_path,
        dry_run=True,
    )

    assert len(plan.written) == 1
    planned = Path(plan.written[0]["planned_path"])
    assert not planned.exists()
    assert planned.name == "2025-annual-management-market-view-0.md"
    assert not _cards_dir(tmp_path).exists()


def test_duplicate_existing_file_is_skipped_by_default(tmp_path) -> None:
    pack = _pack([_card()])
    first = write_periodic_report_narrative_card_notes(
        stock_name="中际旭创",
        stock_code="300308",
        card_pack=pack,
        base_dir=tmp_path,
    )
    assert len(first.written) == 1

    second = write_periodic_report_narrative_card_notes(
        stock_name="中际旭创",
        stock_code="300308",
        card_pack=pack,
        base_dir=tmp_path,
    )

    assert second.written == []
    assert len(second.skipped_existing) == 1
    assert second.skipped_existing[0]["card_id"] == (
        "periodic:300308:2025:annual:narrative:management_market_view:0"
    )


def test_refresh_existing_overwrites_deterministically(tmp_path) -> None:
    pack = _pack([_card()])
    write_periodic_report_narrative_card_notes(
        stock_name="中际旭创",
        stock_code="300308",
        card_pack=pack,
        base_dir=tmp_path,
        collected_at="2026-06-21",
    )
    path = _cards_dir(tmp_path) / "2025-annual-management-market-view-0.md"
    original = path.read_text(encoding="utf-8")

    plan = write_periodic_report_narrative_card_notes(
        stock_name="中际旭创",
        stock_code="300308",
        card_pack=pack,
        base_dir=tmp_path,
        collected_at="2026-06-21",
        refresh_existing=True,
    )

    assert len(plan.refreshed) == 1
    assert plan.written == []
    assert path.read_text(encoding="utf-8") == original


def test_refresh_existing_frontmatter_only_adds_hashes_without_touching_body(tmp_path) -> None:
    pack = _pack([_card(source_block_hash="c" * 64)])
    write_periodic_report_narrative_card_notes(
        stock_name="中际旭创",
        stock_code="300308",
        card_pack=_pack([_card()]),
        base_dir=tmp_path,
        collected_at="2026-06-21",
    )
    path = _cards_dir(tmp_path) / "2025-annual-management-market-view-0.md"
    original = path.read_text(encoding="utf-8")
    manual_body = original + "\n## Manual Note\n\n保留人工补充。\n"
    path.write_text(manual_body, encoding="utf-8")

    plan = write_periodic_report_narrative_card_notes(
        stock_name="中际旭创",
        stock_code="300308",
        card_pack=pack,
        base_dir=tmp_path,
        collected_at="2026-06-22",
        refresh_existing=True,
        refresh_frontmatter_only=True,
    )

    refreshed = path.read_text(encoding="utf-8")
    assert len(plan.refreshed) == 1
    assert plan.refreshed[0]["reason"] == "refreshed_frontmatter_hashes"
    assert "## Manual Note\n\n保留人工补充。\n" in refreshed
    assert f'source_excerpt_hash: "{_normalized_hash(_card()["source_excerpt"])}"' in refreshed
    assert f"source_block_hash: {'c' * 64}" in refreshed
    assert refreshed.split("---", 2)[2] == manual_body.split("---", 2)[2]


def test_hostile_stock_name_and_card_type_cannot_escape_cards_dir(tmp_path) -> None:
    plan = write_periodic_report_narrative_card_notes(
        stock_name="../../evil",
        stock_code="300308",
        card_pack=_pack([
            _card(
                card_id="periodic:300308:2025:annual:narrative:../../evil:0",
                card_type="../../evil",
            )
        ]),
        base_dir=tmp_path,
    )

    base = tmp_path.resolve()
    assert len(plan.written) == 1
    for entry in plan.written:
        resolved = Path(entry["planned_path"]).resolve()
        assert str(resolved).startswith(str(base) + "/")
        assert resolved.parent.name == "periodic_narrative_cards"

    for created in tmp_path.rglob("*.md"):
        assert str(created.resolve()).startswith(str(base) + "/")


def test_stock_code_mismatch_is_filtered_and_note_uses_api_stock_identity(tmp_path) -> None:
    mismatched = _card(
        stock_code="000000",
        stock_name="错误公司",
        card_id="periodic:000000:2025:annual:narrative:business_model:0",
    )

    plan = write_periodic_report_narrative_card_notes(
        stock_name="中际旭创",
        stock_code="300308",
        card_pack=_pack([_card(), mismatched]),
        base_dir=tmp_path,
    )

    assert len(plan.written) == 1
    assert len(plan.filtered) == 1
    assert "stock_code mismatch" in plan.filtered[0]["reason"]

    text = Path(plan.written[0]["planned_path"]).read_text(encoding="utf-8")
    assert 'stock: "中际旭创"' in text
    assert 'code: "300308"' in text
    assert "错误公司" not in text
