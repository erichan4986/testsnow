from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from curated_external_topic_narrative import (
    NARRATIVE_ENVELOPE_SCHEMA,
    NARRATIVE_PRODUCER_VERSION,
    build_external_topic_narrative_envelope,
    build_external_topic_narrative_prompt,
    external_topic_source_fingerprint,
    read_external_topic_narratives,
    validate_external_topic_narrative_draft,
)


def _unit(unit_id, text, ref):
    return {
        "unit_id": unit_id,
        "unit_hash": f"hash:{unit_id}",
        "text": text,
        "citation_refs": [ref],
        "source_ordinal": ref,
    }


def _card(key, scope, family, units):
    return {
        "card_id": f"card:{key}",
        "argument_key": key,
        "entity_scope": scope,
        "primary_family": family,
        "evidence_units": units,
    }


def _pack():
    return {
        "schema_version": "curated_external_argument_pack.v3",
        "selector_version": "external_unit_selector.v2",
        "validator_version": "external_argument_validator.v3",
        "stock_name": "测试股",
        "cards": [
            _card("target-tech", "target", "technology_product", [
                _unit("u1", "测试股新一代芯片进入客户验证阶段，后续仍需观察量产节奏。", 1),
                _unit("u2", "公司平台支持4-128TOPS算力配置。", 2),
            ]),
            _card("target-peer-tech", "target_with_peer_context", "technology_product", [
                _unit("u3", "测试股与同业均在推进先进封装方案。", 3),
            ]),
            _card("peer-demand", "peer_or_industry", "demand_customer", [
                _unit("u4", "行业客户正在提高下一代产品验证要求。", 4),
            ]),
        ],
        "diagnostics": {"ignored": True},
    }


def _valid_draft():
    return {
        "schema_version": "curated_external_topic_narrative_draft.v1",
        "groups": [
            {
                "scope_bucket": "target",
                "primary_family": "technology_product",
                "parts": [
                    {"argument_key": "target-tech", "unit_id": "u1", "quote": "测试股新一代芯片进入客户验证阶段，", "relation": "first"},
                    {"argument_key": "target-tech", "unit_id": "u2", "quote": "公司平台支持4-128TOPS算力配置。", "relation": "continuation"},
                    {"argument_key": "target-peer-tech", "unit_id": "u3", "quote": "测试股与同业均在推进先进封装方案。", "relation": "separate"},
                ],
            },
            {
                "scope_bucket": "peer_or_industry",
                "primary_family": "demand_customer",
                "parts": [
                    {"argument_key": "peer-demand", "unit_id": "u4", "quote": "行业客户正在提高下一代产品验证要求。", "relation": "first"},
                ],
            },
        ],
    }


def test_fingerprint_tracks_canonical_cards_but_ignores_diagnostics_and_narrative():
    pack = _pack()
    baseline = external_topic_source_fingerprint(pack)
    changed_metadata = deepcopy(pack)
    changed_metadata["diagnostics"] = {"other": 1}
    changed_metadata["topic_narratives"] = {"ignored": True}
    assert external_topic_source_fingerprint(changed_metadata) == baseline
    changed_unit = deepcopy(pack)
    changed_unit["cards"][0]["evidence_units"][0]["unit_hash"] = "changed"
    assert external_topic_source_fingerprint(changed_unit) != baseline


def test_valid_draft_covers_every_unit_and_merges_target_scope_variants():
    result = validate_external_topic_narrative_draft(_pack(), _valid_draft())
    assert result["status"] == "ready"
    assert len(result["groups"]) == 2
    target = result["groups"][0]
    assert target["scope_bucket"] == "target"
    assert [part["unit_id"] for part in target["parts"]] == ["u1", "u2", "u3"]
    assert all("citation_refs" not in part for part in target["parts"])


def test_quote_must_be_exact_complete_prefix_and_keep_subject():
    for quote in ("新一代芯片进入客户验证阶段，", "测试股新一代芯片进入客户验证阶", "测试股新一代芯片进入客户验证阶段……"):
        draft = _valid_draft()
        draft["groups"][0]["parts"][0]["quote"] = quote
        result = validate_external_topic_narrative_draft(_pack(), draft)
        assert result["status"] == "partial"
        assert result["diagnostics"]["rejected_by_reason"]


def test_missing_or_duplicate_unit_rejects_only_that_group():
    for mutate in ("missing", "duplicate"):
        draft = _valid_draft()
        if mutate == "missing":
            draft["groups"][0]["parts"].pop(1)
        else:
            draft["groups"][0]["parts"].append(dict(draft["groups"][0]["parts"][1]))
        result = validate_external_topic_narrative_draft(_pack(), draft)
        assert result["status"] == "partial"
        assert [group["scope_bucket"] for group in result["groups"]] == ["peer_or_industry"]


def test_scope_topic_order_relation_and_unknown_keys_fail_closed():
    mutations = []
    cross_scope = _valid_draft(); cross_scope["groups"][0]["parts"][0]["argument_key"] = "peer-demand"; cross_scope["groups"][0]["parts"][0]["unit_id"] = "u4"; cross_scope["groups"][0]["parts"][0]["quote"] = "行业客户正在提高下一代产品验证要求。"; mutations.append(cross_scope)
    wrong_topic = _valid_draft(); wrong_topic["groups"][0]["primary_family"] = "financial_quality"; mutations.append(wrong_topic)
    wrong_order = _valid_draft(); wrong_order["groups"][0]["parts"][0], wrong_order["groups"][0]["parts"][1] = wrong_order["groups"][0]["parts"][1], wrong_order["groups"][0]["parts"][0]; mutations.append(wrong_order)
    wrong_relation = _valid_draft(); wrong_relation["groups"][0]["parts"][1]["relation"] = "first"; mutations.append(wrong_relation)
    prose = _valid_draft(); prose["groups"][0]["summary"] = "自由改写"; mutations.append(prose)
    for draft in mutations:
        assert validate_external_topic_narrative_draft(_pack(), draft)["status"] != "ready"


def test_envelope_persists_only_validated_groups_and_no_raw_response():
    draft = _valid_draft()
    draft["groups"][0]["parts"][0]["quote"] = "错误改写"
    envelope = build_external_topic_narrative_envelope(_pack(), draft)
    assert envelope["schema_version"] == NARRATIVE_ENVELOPE_SCHEMA
    assert envelope["producer_version"] == NARRATIVE_PRODUCER_VERSION
    assert envelope["status"] == "partial"
    assert len(envelope["groups"]) == 1
    assert "raw_response" not in str(envelope)
    assert "错误改写" not in str(envelope)


def test_reader_distinguishes_missing_stale_invalid_and_ready_without_touching_core():
    pack = _pack()
    assert read_external_topic_narratives(pack)["status"] == "missing"
    pack["topic_narratives"] = build_external_topic_narrative_envelope(pack, _valid_draft())
    assert read_external_topic_narratives(pack)["status"] == "ready"
    stale = deepcopy(pack); stale["topic_narratives"]["source_pack_fingerprint"] = "stale"
    assert read_external_topic_narratives(stale)["status"] == "stale"
    invalid = deepcopy(pack); invalid["topic_narratives"]["groups"][0]["parts"][0]["quote"] = "改写"
    assert read_external_topic_narratives(invalid)["status"] == "invalid"


def test_prompt_contains_ids_and_exact_text_but_forbids_prose_and_decision_fields():
    prompt = build_external_topic_narrative_prompt(_pack())
    assert "target-tech" in prompt and "u1" in prompt
    assert "测试股新一代芯片进入客户验证阶段" in prompt
    assert "不得改写" in prompt and "目标价" in prompt and "评分" in prompt
