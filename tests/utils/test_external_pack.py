"""Contracts for the strict v4 external argument pack."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from external_pack import (  # type: ignore[import-not-found]
    ARGUMENT_PACK_SCHEMA,
    build_external_argument_pack_v4,
    external_selection_batches_v4,
    prepare_external_argument_material_v4,
    read_external_argument_pack_v4,
)
from external_source_document import build_external_source_document


def _document(content: str, *, source_id: str = "source:test") -> dict:
    return build_external_source_document({
        "source_id": source_id, "stock_name": "测试股", "title": "测试股经营跟踪",
        "source_kind": "media", "source_ref": f"https://example.test/{source_id}",
        "source_url": f"https://example.test/{source_id}", "content": content,
    })


def _keep_everything(prepared: dict) -> list[dict]:
    return [{
        "schema_version": "curated_external_unit_selection.v2",
        "decisions": [{"unit_id": unit["unit_id"], "action": "keep", "group_id": ""}
                      for unit in batch],
    } for batch in external_selection_batches_v4(prepared["peer_units"])]


def test_pack_embeds_documents_and_rejects_forged_unit_offset():
    documents = [_document(
        "测试股产品完成客户导入。\n\n公司已接到全年订单。\n\n2027年行业仍面临产能紧张。"
    )]
    prepared = prepare_external_argument_material_v4(
        documents, stock_name="测试股", baseline_text="",
    )
    pack = build_external_argument_pack_v4(
        documents, stock_name="测试股", baseline_text="", selections=_keep_everything(prepared),
        prepared_material=prepared,
    )

    assert pack["schema_version"] == ARGUMENT_PACK_SCHEMA
    assert pack["source_documents"] == documents
    assert read_external_argument_pack_v4(pack, expected_stock_name="测试股")["status"] == "ok"
    forged = copy.deepcopy(pack)
    forged["cards"][0]["evidence_units"][0]["end"] += 1
    assert read_external_argument_pack_v4(forged, expected_stock_name="测试股") == {
        "status": "invalid", "reason": "unit_offset",
    }


def test_one_unit_has_one_card_owner_when_multiple_families_match():
    documents = [_document("测试股产品完成客户导入，订单增长明显。")]
    prepared = prepare_external_argument_material_v4(documents, stock_name="测试股", baseline_text="")
    pack = build_external_argument_pack_v4(
        documents, stock_name="测试股", baseline_text="", selections=[], prepared_material=prepared,
    )

    unit_ids = [unit["unit_id"] for card in pack["cards"] for unit in card["evidence_units"]]
    assert len(unit_ids) == len(set(unit_ids)) == 1
    assert pack["cards"][0]["coverage_families"] == [
        "technology_product", "commercialization", "demand_customer",
    ]


def test_target_cards_split_noncontiguous_same_family_runs_in_source_order():
    documents = [_document(
        "测试股营收增长明显。测试股产品完成客户导入。测试股利润改善。"
    )]
    pack = build_external_argument_pack_v4(
        documents, stock_name="测试股", baseline_text="", selections=[],
    )

    assert [card["primary_family"] for card in pack["cards"]] == [
        "financial_quality", "technology_product", "financial_quality",
    ]
    assert [len(card["evidence_units"]) for card in pack["cards"]] == [1, 1, 1]


def test_duplicate_text_never_removes_a_source_unit_position():
    documents = [_document(
        "测试股营收增长明显。测试股产品完成客户导入。测试股营收增长明显。"
    )]
    pack = build_external_argument_pack_v4(
        documents, stock_name="测试股", baseline_text="", selections=[],
    )

    assert [card["primary_family"] for card in pack["cards"]] == [
        "financial_quality", "technology_product", "financial_quality",
    ]
    assert [unit["unit_ordinal"] for card in pack["cards"] for unit in card["evidence_units"]] == [0, 1, 2]


def test_target_card_run_does_not_jump_over_an_industry_unit():
    documents = [_document(
        "测试股产品完成客户导入。2027年行业需求增长。测试股技术持续演进。"
    )]
    prepared = prepare_external_argument_material_v4(
        documents, stock_name="测试股", baseline_text="",
    )
    pack = build_external_argument_pack_v4(
        documents, stock_name="测试股", baseline_text="", selections=_keep_everything(prepared),
        prepared_material=prepared,
    )

    target_cards = [card for card in pack["cards"] if card["entity_scope"] == "target"]
    assert [
        [unit["unit_ordinal"] for unit in card["evidence_units"]]
        for card in target_cards
    ] == [[0], [2]]


def test_target_peer_relation_stays_in_target_with_peer_context_card():
    documents = [_document("测试股相比华工科技具备更大产能。")]
    prepared = prepare_external_argument_material_v4(documents, stock_name="测试股", baseline_text="")
    pack = build_external_argument_pack_v4(
        documents, stock_name="测试股", baseline_text="", selections=[], prepared_material=prepared,
    )

    assert pack["cards"][0]["entity_scope"] == "target_with_peer_context"


def test_selector_group_cannot_cross_source_or_block():
    documents = [_document("2027年行业需求增长。\n\n行业产能仍紧张。")]
    prepared = prepare_external_argument_material_v4(documents, stock_name="测试股", baseline_text="")
    batch = external_selection_batches_v4(prepared["peer_units"])[0]
    selection = {
        "schema_version": "curated_external_unit_selection.v2",
        "decisions": [{"unit_id": unit["unit_id"], "action": "keep", "group_id": "same"} for unit in batch],
    }
    pack = build_external_argument_pack_v4(
        documents, stock_name="测试股", baseline_text="", selections=[selection], prepared_material=prepared,
    )

    assert pack["status"] == "selector_incomplete"
    assert pack["diagnostics"]["rejection_reasons"] == ["selection_invalid_group"]
    assert pack["source_documents"] == documents
    assert pack["cards"] == []
    assert pack["citations"] == {}


def test_pack_uses_prepared_material_without_reresolving_scope():
    documents = [_document("测试股产品完成客户导入。\n\n行业产能仍紧张。")]
    prepared = prepare_external_argument_material_v4(documents, stock_name="测试股", baseline_text="")
    prepared = {**prepared, "peer_units": []}

    pack = build_external_argument_pack_v4(
        documents, stock_name="测试股", baseline_text="", selections=[], prepared_material=prepared,
    )

    assert pack["status"] == "ready"
    assert all(card["entity_scope"] != "peer_or_industry" for card in pack["cards"])


def test_reader_rejects_citation_that_no_longer_matches_embedded_document():
    documents = [_document("测试股产品完成客户导入。")]
    pack = build_external_argument_pack_v4(
        documents, stock_name="测试股", baseline_text="", selections=[],
    )
    forged = copy.deepcopy(pack)
    forged["citations"][1]["source_id"] = "source:forged"

    assert read_external_argument_pack_v4(forged, expected_stock_name="测试股") == {
        "status": "invalid", "reason": "citation_identity",
    }


def test_reader_rejects_unsafe_card_fields_and_invalid_narrative_plan():
    documents = [_document("测试股产品完成客户导入。")]
    pack = build_external_argument_pack_v4(
        documents, stock_name="测试股", baseline_text="", selections=[],
    )
    unsafe = copy.deepcopy(pack)
    unsafe["cards"][0]["score"] = 10
    assert read_external_argument_pack_v4(unsafe, expected_stock_name="测试股") == {
        "status": "invalid", "reason": "forbidden_card_field",
    }
    invalid_plan = copy.deepcopy(pack)
    invalid_plan["narrative_plan"] = {
        "schema_version": "curated_external_narrative_plan.v1", "groups": [],
    }
    assert read_external_argument_pack_v4(invalid_plan, expected_stock_name="测试股") == {
        "status": "invalid", "reason": "narrative_plan_coverage",
    }


def test_pack_rejects_cutover_when_any_comparative_source_is_degraded():
    valid = _document("测试股产品完成客户导入。", source_id="source:valid")
    degraded = build_external_source_document({
        "source_id": "source:degraded", "stock_name": "测试股", "title": "测试股与华工科技技术对比",
        "source_kind": "media", "source_ref": "https://example.test/degraded",
        "source_url": "https://example.test/degraded", "content": "测试股与华工科技对比：" + "内容" * 600,
    })

    pack = build_external_argument_pack_v4(
        [valid, degraded], stock_name="测试股", baseline_text="", selections=[],
    )

    assert pack["status"] == "source_input_degraded"
    assert pack["source_documents"] == []
    assert pack["cards"] == []
    assert "rejection_reasons" not in pack["diagnostics"]
    assert pack["diagnostics"]["rejected_source_documents"] == {
        "scope_input_degraded": ["source:degraded"],
    }
    assert read_external_argument_pack_v4(pack, expected_stock_name="测试股") == {
        "status": "invalid", "reason": "pack_identity",
    }


def test_reader_rejects_pre_fix_ready_pack_that_recorded_degraded_sources():
    pack = build_external_argument_pack_v4(
        [_document("测试股产品完成客户导入。")],
        stock_name="测试股", baseline_text="", selections=[],
    )
    pack["diagnostics"]["rejected_source_documents"] = {
        "scope_input_degraded": ["source:degraded"],
    }

    assert read_external_argument_pack_v4(pack, expected_stock_name="测试股") == {
        "status": "invalid", "reason": "source_input_degraded",
    }


def test_reader_rejects_card_with_mismatched_target_identity_or_family():
    documents = [_document("测试股产品完成客户导入。")]
    pack = build_external_argument_pack_v4(
        documents, stock_name="测试股", baseline_text="", selections=[],
    )
    wrong_target = copy.deepcopy(pack)
    wrong_target["cards"][0]["target_entity"] = "另一家公司"
    assert read_external_argument_pack_v4(wrong_target, expected_stock_name="测试股") == {
        "status": "invalid", "reason": "card_target_entity",
    }
    wrong_family = copy.deepcopy(pack)
    wrong_family["cards"][0]["primary_family"] = "other"
    assert read_external_argument_pack_v4(wrong_family, expected_stock_name="测试股") == {
        "status": "invalid", "reason": "card_family",
    }


def test_reader_rejects_card_level_citations_not_owned_by_its_units():
    documents = [
        _document("测试股产品完成客户导入。", source_id="source:first"),
        _document("测试股已接到全年订单。", source_id="source:second"),
    ]
    pack = build_external_argument_pack_v4(
        documents, stock_name="测试股", baseline_text="", selections=[],
    )
    forged = copy.deepcopy(pack)
    forged["cards"][0]["citation_refs"] = [2]

    assert read_external_argument_pack_v4(forged, expected_stock_name="测试股") == {
        "status": "invalid", "reason": "card_citations",
    }


def test_reader_rejects_unreferenced_citations():
    documents = [_document("测试股产品完成客户导入。")]
    pack = build_external_argument_pack_v4(
        documents, stock_name="测试股", baseline_text="", selections=[],
    )
    forged = copy.deepcopy(pack)
    forged["citations"][99] = copy.deepcopy(forged["citations"][1])

    assert read_external_argument_pack_v4(forged, expected_stock_name="测试股") == {
        "status": "invalid", "reason": "unused_citations",
    }


def test_reader_rejects_noncanonical_card_family_metadata_and_unit_order():
    documents = [_document("测试股营收增长明显。测试股利润改善。")]
    pack = build_external_argument_pack_v4(
        documents, stock_name="测试股", baseline_text="", selections=[],
    )
    wrong_family = copy.deepcopy(pack)
    wrong_family["cards"][0]["coverage_families"].append("technology_product")
    assert read_external_argument_pack_v4(wrong_family, expected_stock_name="测试股") == {
        "status": "invalid", "reason": "card_family",
    }
    reversed_units = copy.deepcopy(pack)
    reversed_units["cards"][0]["evidence_units"].reverse()
    assert read_external_argument_pack_v4(reversed_units, expected_stock_name="测试股") == {
        "status": "invalid", "reason": "card_units",
    }
