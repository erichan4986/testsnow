"""Contracts for immutable v3 external evidence units and packs."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

import curated_external_argument_cards as cards_module
from curated_external_topic_narrative import build_external_topic_narrative_envelope
from curated_external_argument_cards import (
    build_external_argument_pack, enrich_external_evidence_group, materialize_external_source_units,
    read_external_argument_pack, validate_external_unit_selection,
)


def _packet(stock="测试股", content="测试股产品完成客户导入。测试股毛利率改善；行业竞争加剧。"):
    return {"source_id": "source:one", "stock_name": stock, "title": "观察", "account": "作者",
            "publish_time": "2026-07-15", "source_ref": "https://example.com/a", "source_url": "https://example.com/a",
            "content": content, "source_content_hash": hashlib.sha256(content.encode()).hexdigest()}


def _selection(units):
    return {"schema_version": "curated_external_unit_selection.v1", "decisions": [
        {"unit_id": unit["unit_id"], "action": "keep", "group_id": "", "reason": "incremental_target_fact"}
        for unit in units
    ]}


def test_v3_pack_uses_canonical_unversioned_public_api_names():
    assert hasattr(cards_module, "build_external_argument_pack")
    assert hasattr(cards_module, "read_external_argument_pack")
    assert not hasattr(cards_module, "build_external_argument_pack_v3")
    assert not hasattr(cards_module, "read_external_argument_pack_v3")


def test_materialized_units_are_exact_complete_stable_source_substrings():
    packet = _packet(content="行业观点\n测试股产品完成客户导入。测试股毛利率改善；\n不完整尾部")
    units = materialize_external_source_units([packet], stock_name="测试股")
    assert [unit["text"] for unit in units] == ["测试股产品完成客户导入。", "测试股毛利率改善；"]
    assert all(unit["text"] in packet["content"] and unit["unit_hash"] for unit in units)
    assert units[0]["source_ordinal"] == 0


def test_materialized_units_preserve_decimal_and_product_model_dots():
    packet = _packet(content="测试股已量产1.6T产品，收入同比增长19.30%。")

    units = materialize_external_source_units([packet], stock_name="测试股")

    assert [unit["text"] for unit in units] == ["测试股已量产1.6T产品，收入同比增长19.30%。"]


def test_materialized_units_drop_incomplete_numeric_dot_tail():
    packet = _packet(content="行业数据显示TOP8占比64.")

    units = materialize_external_source_units([packet], stock_name="测试股")

    assert units == []


def test_materialized_units_drop_narrow_report_structural_residue():
    packet = _packet(content=(
        "cn)记者赵奕 上海报道行业需求增长20%。\n"
        "本报告系统调研了行业竞争格局。"
    ))

    units = materialize_external_source_units([packet], stock_name="测试股")

    assert units == []


def test_enrichment_and_preparation_are_deterministic_and_uncapped_for_target_evidence():
    units = materialize_external_source_units([_packet()], stock_name="测试股")
    enriched = enrich_external_evidence_group(units[:2], stock_name="测试股")
    prepared = cards_module.prepare_external_argument_material(
        units, stock_name="测试股", baseline_text="",
    )
    assert enriched["entity_scope"] == "target"
    assert {"technology_product", "financial_quality"}.issubset(enriched["coverage_families"])
    assert prepared["diagnostics"]["mandatory_target_unit_count"] == 2
    assert cards_module.prepare_external_argument_material(
        units, stock_name="测试股", baseline_text=units[0]["text"],
    )["diagnostics"]["rejected_by_reason"] == {"baseline_duplicate": 1}


def test_selection_rejects_missing_forbidden_or_invalid_groups_and_accepts_exact_ids():
    units = materialize_external_source_units([_packet()], stock_name="测试股")
    mandatory = {unit["unit_id"] for unit in units[:2]}
    assert validate_external_unit_selection(units, {"schema_version": "curated_external_unit_selection.v1", "decisions": []}, mandatory_ids=mandatory)["status"] == "invalid"
    forbidden = _selection(units) | {"claim": "不能出现"}
    assert validate_external_unit_selection(units, forbidden, mandatory_ids=mandatory)["reason"] == "selection_forbidden_field"
    assert validate_external_unit_selection(units, _selection(units), mandatory_ids=mandatory)["status"] == "ok"


def test_v3_pack_persists_only_exact_evidence_and_reader_fails_closed(tmp_path):
    packet = _packet(); units = materialize_external_source_units([packet], stock_name="测试股")
    pack = build_external_argument_pack(stock_name="测试股", source_packets=[packet], baseline_text="", selections=[])
    path = tmp_path / "pack.json"; path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    result = read_external_argument_pack(path, expected_stock_name="测试股")
    assert result["status"] == "ok" and all("claim" not in card for card in result["cards"])
    pack["cards"][0]["scoring_eligible"] = True; path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    assert read_external_argument_pack(path, expected_stock_name="测试股")["status"] == "invalid"


def test_v3_reader_keeps_core_ready_when_optional_narrative_is_missing_or_invalid(tmp_path):
    packet = _packet()
    pack = build_external_argument_pack(stock_name="测试股", source_packets=[packet], baseline_text="", selections=[])
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    missing = read_external_argument_pack(path, expected_stock_name="测试股")
    assert missing["status"] == "ok"
    assert missing["topic_narrative_status"] == "missing"
    assert missing["topic_narratives"] == []

    pack["topic_narratives"] = {"bad": True}
    path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    invalid = read_external_argument_pack(path, expected_stock_name="测试股")
    assert invalid["status"] == "ok"
    assert invalid["topic_narrative_status"] == "invalid"
    assert invalid["cards"]


def test_v3_reader_returns_validated_optional_narratives_separately(tmp_path):
    packet = _packet(content="测试股产品完成客户导入。")
    pack = build_external_argument_pack(stock_name="测试股", source_packets=[packet], baseline_text="", selections=[])
    card, unit = pack["cards"][0], pack["cards"][0]["evidence_units"][0]
    draft = {"schema_version": "curated_external_topic_narrative_draft.v1", "groups": [{
        "scope_bucket": "target", "primary_family": card["primary_family"], "parts": [{
            "argument_key": card["argument_key"], "unit_id": unit["unit_id"],
            "quote": unit["text"], "relation": "first",
        }],
    }]}
    pack["topic_narratives"] = build_external_topic_narrative_envelope(pack, draft)
    path = tmp_path / "pack.json"; path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")

    result = read_external_argument_pack(path, expected_stock_name="测试股")

    assert result["status"] == "ok" and result["topic_narrative_status"] == "ready"
    assert result["topic_narratives"][0]["parts"][0]["unit_id"] == unit["unit_id"]


def test_v3_pack_fails_closed_when_prepared_target_references_unknown_source():
    packet = _packet()
    units = materialize_external_source_units([packet], stock_name="测试股")
    prepared = cards_module.prepare_external_argument_material(
        units, stock_name="测试股", baseline_text="",
    )
    prepared = json.loads(json.dumps(prepared))
    prepared["target_bundles"][0]["units"][0]["source_id"] = "source:missing"

    pack = build_external_argument_pack(
        stock_name="测试股", source_packets=[packet], baseline_text="", selections=[],
        prepared_material=prepared,
    )

    assert pack["status"] == "selector_incomplete"
    assert pack["diagnostics"]["rejection_reasons"] == ["unknown_source_id"]


def test_v3_reader_rejects_stale_schema_stock_mismatch_and_dangling_citation(tmp_path):
    packet = _packet(); units = materialize_external_source_units([packet], stock_name="测试股")
    pack = build_external_argument_pack(stock_name="测试股", source_packets=[packet], baseline_text="", selections=[])
    path = tmp_path / "pack.json"
    for mutate, expected in ((lambda data: data.update(schema_version="old"), "stale"),
                             (lambda data: data.update(stock_name="另一家"), "stock_identity_mismatch"),
                             (lambda data: data["cards"][0].update(citation_refs=[99]), "invalid")):
        payload = json.loads(json.dumps(pack)); mutate(payload); path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        assert read_external_argument_pack(path, expected_stock_name="测试股")["status"] == expected


def test_v1_selector_pack_is_stale_after_selector_v2_refresh(tmp_path):
    packet = _packet()
    units = materialize_external_source_units([packet], stock_name="测试股")
    pack = build_external_argument_pack(
        stock_name="测试股", source_packets=[packet], baseline_text="", selections=[],
    )
    pack["selector_version"] = "external_unit_selector.v1"
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")

    assert read_external_argument_pack(path, expected_stock_name="测试股")["status"] == "stale"


def test_same_group_id_in_different_source_batches_does_not_merge_cards():
    packets = [
        _packet(content="英伟达发布800G产品并启动量产。") | {
            "source_id": "source:a", "source_ref": "https://example.com/a",
            "source_url": "https://example.com/a",
        },
        _packet(content="华为发布900G产品并启动量产。") | {
            "source_id": "source:b", "source_ref": "https://example.com/b",
            "source_url": "https://example.com/b",
        },
    ]
    for packet in packets:
        packet["source_content_hash"] = hashlib.sha256(packet["content"].encode()).hexdigest()
    selections = []
    for packet in packets:
        unit = materialize_external_source_units([packet], stock_name="测试股")[0]
        selections.append({"schema_version": "curated_external_unit_selection.v1", "decisions": [{
            "unit_id": unit["unit_id"], "action": "keep", "group_id": "argument-1", "reason": "keep",
        }]})

    pack = build_external_argument_pack(
        stock_name="测试股", source_packets=packets, baseline_text="", selections=selections,
    )

    assert len(pack["cards"]) == 2
    assert [{unit["source_id"] for unit in card["evidence_units"]} for card in pack["cards"]] == [
        {"source:a"}, {"source:b"},
    ]


def test_selected_group_persists_members_in_source_order_not_target_first_pool_order():
    units = [
        {"unit_id": "target-7", "source_id": "source:one", "source_ordinal": 7},
        {"unit_id": "peer-5", "source_id": "source:one", "source_ordinal": 5},
        {"unit_id": "peer-6", "source_id": "source:one", "source_ordinal": 6},
    ]
    decisions = {
        unit["unit_id"]: {"action": "keep", "group_id": "argument", "_batch_index": 0}
        for unit in units
    }

    groups = cards_module._selected_unit_groups(units, decisions)

    assert [[unit["source_ordinal"] for unit in group] for group in groups] == [[5, 6, 7]]


def test_target_group_coverage_uses_target_bound_unit_families_not_peer_text():
    target = {
        "text": "测试股经营改善。", "target_bound": True,
        "coverage_families": ["financial_quality"],
    }
    peer = {
        "text": "同业供应链交付承压。", "target_bound": False,
        "coverage_families": ["capacity_delivery"],
    }

    enriched = enrich_external_evidence_group([target, peer], stock_name="测试股")

    assert enriched["entity_scope"] == "target_with_peer_context"
    assert enriched["coverage_families"] == ["financial_quality"]


def test_preparation_attaches_only_closed_syntax_target_continuations():
    units = materialize_external_source_units([_packet(content=(
        "测试股产品完成客户导入。公司毛利率改善。该产品已完成客户验证。"
        "公司竞争对手英伟达已发布新品。双方将共同推进合作。"
    ))], stock_name="测试股")

    prepared = cards_module.prepare_external_argument_material(
        units, stock_name="测试股", baseline_text="",
    )

    assert [[unit["source_ordinal"] for unit in bundle["units"]] for bundle in prepared["target_bundles"]] == [[0, 1, 2]]
    assert prepared["target_bundles"][0]["bundle_key"] == "target-bundle:source:one:0"
    assert prepared["target_bundles"][0]["coverage_families"] == [
        "financial_quality", "technology_product", "commercialization", "demand_customer",
    ]
    assert prepared["diagnostics"]["continuation_rejected_count"] == 1


def test_preparation_rejects_ambiguous_pronoun_and_multi_entity_continuations():
    for continuation in ("其竞争对手英伟达已发布新品。", "双方将共同推进合作。"):
        units = materialize_external_source_units([_packet(content=(
            "测试股产品完成客户导入。" + continuation
        ))], stock_name="测试股")

        prepared = cards_module.prepare_external_argument_material(
            units, stock_name="测试股", baseline_text="",
        )

        assert [[unit["source_ordinal"] for unit in bundle["units"]] for bundle in prepared["target_bundles"]] == [[0]]
        assert prepared["diagnostics"]["continuation_rejected_count"] == 1


def test_preparation_starts_a_new_bundle_for_next_explicit_target_fact():
    units = materialize_external_source_units([_packet(content=(
        "测试股产品完成客户导入。公司毛利率改善。测试股新产品验证通过。"
    ))], stock_name="测试股")

    prepared = cards_module.prepare_external_argument_material(
        units, stock_name="测试股", baseline_text="",
    )

    assert [[unit["source_ordinal"] for unit in bundle["units"]] for bundle in prepared["target_bundles"]] == [[0, 1], [2]]
    assert prepared["diagnostics"]["mandatory_target_unit_count"] == 2


def test_preparation_records_truncated_target_continuation_without_losing_anchor():
    units = materialize_external_source_units([_packet(content=(
        "测试股产品完成客户导入。公司毛利率改善。该产品已完成客户验证。相关产品开始量产。"
    ))], stock_name="测试股")

    prepared = cards_module.prepare_external_argument_material(
        units, stock_name="测试股", baseline_text="",
    )

    assert [[unit["source_ordinal"] for unit in bundle["units"]] for bundle in prepared["target_bundles"]] == [[0, 1, 2]]
    assert prepared["diagnostics"]["continuation_truncated_count"] == 1


def test_preparation_filters_low_signal_peer_but_keeps_named_action_with_anchor():
    units = materialize_external_source_units([_packet(content=(
        "行业竞争格局加剧。英伟达发布800G产品并启动量产。"
    ))], stock_name="测试股")

    prepared = cards_module.prepare_external_argument_material(
        units, stock_name="测试股", baseline_text="",
    )

    assert [unit["text"] for unit in prepared["optional_peer_units"]] == ["英伟达发布800G产品并启动量产。"]
    assert prepared["diagnostics"]["optional_peer_raw_count"] == 2
    assert prepared["diagnostics"]["optional_peer_eligible_count"] == 1
    assert prepared["diagnostics"]["optional_peer_low_signal_count"] == 1


def test_preparation_dedupes_exact_across_sources_and_containment_within_source():
    exact = "英伟达发布800G产品并启动量产。"
    contained = "英伟达发布800G产品。"
    richer = "英伟达发布800G产品并启动量产，订单持续增长。"
    packets = [
        _packet(content=exact) | {"source_id": "source:first", "source_ref": "https://example.com/first"},
        _packet(content=exact) | {"source_id": "source:second", "source_ref": "https://example.com/second"},
        _packet(content=contained + richer) | {"source_id": "source:third", "source_ref": "https://example.com/third"},
    ]
    for packet in packets:
        packet["source_content_hash"] = hashlib.sha256(packet["content"].encode()).hexdigest()
    units = materialize_external_source_units(packets, stock_name="测试股")

    prepared = cards_module.prepare_external_argument_material(
        units, stock_name="测试股", baseline_text="",
    )

    assert [unit["text"] for unit in prepared["optional_peer_units"]] == [exact, richer]
    assert prepared["diagnostics"]["optional_peer_duplicate_count"] == 2


def test_preparation_preserves_all_distinct_high_value_peer_units_without_cap():
    packets = []
    for index in range(25):
        content = f"光模块行业2026年产品迭代第{index}次，订单增长{index + 1}%。"
        packet = _packet(content=content) | {
            "source_id": f"source:{index}", "source_ref": f"https://example.com/{index}",
        }
        packet["source_content_hash"] = hashlib.sha256(content.encode()).hexdigest()
        packets.append(packet)
    units = materialize_external_source_units(packets, stock_name="测试股")

    prepared = cards_module.prepare_external_argument_material(
        units, stock_name="测试股", baseline_text="",
    )

    assert len(prepared["optional_peer_units"]) == 25
    assert prepared["diagnostics"]["optional_peer_eligible_count"] == 25


def test_v3_reader_rejects_broken_source_identity_chain(tmp_path):
    packet = _packet()
    units = materialize_external_source_units([packet], stock_name="测试股")
    pack = build_external_argument_pack(
        stock_name="测试股", source_packets=[packet], baseline_text="", selections=[],
    )
    mutations = (
        lambda payload: payload["cards"][0]["evidence_units"][0].update(source_id="source:forged"),
        lambda payload: payload["cards"][0]["evidence_units"][0].update(source_block_hash="forged-hash"),
        lambda payload: next(iter(payload["citations"].values())).update(source_id="source:forged"),
        lambda payload: next(iter(payload["citations"].values())).update(source_block_hash="forged-hash"),
        lambda payload: next(iter(payload["citations"].values())).update(source_quote_hash="forged-hash"),
        lambda payload: payload["cards"][0]["evidence_units"][0].update(citation_refs=[2]),
        lambda payload: payload["cards"][0].update(source_identity=[["url", "https://forged.example"]]),
        lambda payload: payload["cards"][0]["evidence_units"][0].update(source_ordinal="bad"),
    )
    path = tmp_path / "pack.json"
    for mutate in mutations:
        payload = json.loads(json.dumps(pack))
        mutate(payload)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result = read_external_argument_pack(path, expected_stock_name="测试股")
        assert result["status"] == "invalid"
