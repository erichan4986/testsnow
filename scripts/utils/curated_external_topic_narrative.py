"""Pure contracts for optional extractive external-topic narratives."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

try:
    from .curated_external_argument_cards import clean_external_text, external_scope_bucket, external_unit_key
except ImportError:
    from curated_external_argument_cards import clean_external_text, external_scope_bucket, external_unit_key


NARRATIVE_DRAFT_SCHEMA = "curated_external_topic_narrative_draft.v1"
NARRATIVE_ENVELOPE_SCHEMA, NARRATIVE_PRODUCER_VERSION = (
    "curated_external_topic_narratives.v1", "external_topic_narrative.v1",
)
_DRAFT_KEYS = {"schema_version", "groups"}
_GROUP_KEYS = {"scope_bucket", "primary_family", "parts"}
_PART_KEYS = {"argument_key", "unit_id", "quote", "relation"}
_RELATIONS = {"first", "continuation", "separate"}
_BOUNDARY = "，,；;。！？!?：:"
_ENVELOPE_KEYS = {"schema_version", "producer_version", "source_pack_fingerprint", "status", "groups", "diagnostics"}


def external_topic_source_fingerprint(pack: Mapping[str, Any]) -> str:
    def card_signature(card: Mapping[str, Any]) -> dict:
        return {
            "card_id": card.get("card_id"), "argument_key": card.get("argument_key"),
            "entity_scope": card.get("entity_scope"), "primary_family": card.get("primary_family"),
            "units": [{"unit_id": unit.get("unit_id"), "unit_hash": unit.get("unit_hash")} for unit in card.get("evidence_units") or [] if isinstance(unit, Mapping)],
        }
    projection = {key: pack.get(key) for key in ("schema_version", "selector_version", "validator_version")} | {
        "stock_name": clean_external_text(pack.get("stock_name")),
        "cards": [card_signature(card) for card in pack.get("cards") or [] if isinstance(card, Mapping)],
    }
    encoded = json.dumps(projection, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()

def build_external_topic_narrative_prompt(pack: Mapping[str, Any]) -> str:
    groups = [{
        "scope_bucket": scope, "primary_family": family,
        "cards": [{"argument_key": card["argument_key"],
                   "units": [{"unit_id": unit["unit_id"], "text": unit["text"]} for unit in card["evidence_units"]]}
                  for card in cards],
    } for (scope, family), cards in _canonical_groups(pack).items()]
    payload = json.dumps(groups, ensure_ascii=False, separators=(",", ":"))
    return (
        "你是投研外部材料的抽取式段落编排器。不得改写、补写或删除任何 evidence unit；"
        "每个 unit 必须恰好输出一次，只能从原文起点截取完整前缀，保留原主语。"
        "quote 不得含引用、目标价、评分、风险评分、推荐或其他自由总结。"
        "relation 只能是 first、continuation、separate；保持输入卡片与 unit 顺序。\n"
        f"输入分组：{payload}\n"
        f'输出 JSON：{{"schema_version":"{NARRATIVE_DRAFT_SCHEMA}","groups":['
        '{"scope_bucket":"...","primary_family":"...","parts":['
        '{"argument_key":"...","unit_id":"...","quote":"原文完整前缀",'
        '"relation":"first|continuation|separate"}]}]}'
    )

def validate_external_topic_narrative_draft(pack: Mapping[str, Any], draft: object) -> dict:
    groups = _canonical_groups(pack)
    if (not groups or not isinstance(draft, Mapping) or set(draft) != _DRAFT_KEYS or
            draft.get("schema_version") != NARRATIVE_DRAFT_SCHEMA or not isinstance(draft.get("groups"), list)):
        return _result("invalid", [], {"draft_schema": 1})
    accepted, rejected, seen = [], {}, set()
    for raw_group in draft["groups"]:
        key = _group_key(raw_group)
        if key in seen:
            _bump(rejected, "duplicate_group")
            continue
        seen.add(key)
        valid, reason = _validate_group(raw_group, groups.get(key))
        accepted.append(valid) if valid else _bump(rejected, reason)
    for key in groups:
        if key not in seen:
            _bump(rejected, "missing_group")
    status = "ready" if len(accepted) == len(groups) and not rejected else "partial" if accepted else "invalid"
    return _result(status, accepted, rejected)

def build_external_topic_narrative_envelope(
    pack: Mapping[str, Any], draft_or_none: object, status_reason: str = "",
) -> dict:
    validation = (_result("unavailable", [], {status_reason or "request_unavailable": 1}) if draft_or_none is None
                  else validate_external_topic_narrative_draft(pack, draft_or_none))
    if validation["status"] == "invalid":
        validation["status"] = "unavailable"
    return {"schema_version": NARRATIVE_ENVELOPE_SCHEMA, "producer_version": NARRATIVE_PRODUCER_VERSION,
            "source_pack_fingerprint": external_topic_source_fingerprint(pack), **validation}

def read_external_topic_narratives(pack: Mapping[str, Any]) -> dict:
    envelope = pack.get("topic_narratives")
    if envelope is None:
        return {"status": "missing", "groups": [], "diagnostics": {}}
    if (not isinstance(envelope, Mapping) or set(envelope) != _ENVELOPE_KEYS or
            envelope.get("schema_version") != NARRATIVE_ENVELOPE_SCHEMA or
            envelope.get("producer_version") != NARRATIVE_PRODUCER_VERSION):
        return _read_error("invalid", "envelope_schema")
    if envelope.get("source_pack_fingerprint") != external_topic_source_fingerprint(pack):
        return _read_error("stale", "fingerprint_mismatch")
    status = envelope.get("status")
    if status == "unavailable":
        return {"status": status, "groups": [], "diagnostics": dict(envelope.get("diagnostics") or {})}
    validation = validate_external_topic_narrative_draft(pack, {
        "schema_version": NARRATIVE_DRAFT_SCHEMA, "groups": envelope.get("groups"),
    })
    return validation if status in {"ready", "partial"} and validation["status"] == status else {
        "status": "invalid", "groups": [], "diagnostics": validation["diagnostics"],
    }

def _canonical_groups(pack: Mapping[str, Any]) -> dict[tuple[str, str], list[dict]]:
    result, card_ids, argument_keys = {}, set(), set()
    for card in pack.get("cards") or []:
        if not isinstance(card, Mapping):
            continue
        card_id, argument_key = clean_external_text(card.get("card_id")), clean_external_text(card.get("argument_key"))
        if not card_id or not argument_key or card_id in card_ids or argument_key in argument_keys:
            return {}
        card_ids.add(card_id)
        argument_keys.add(argument_key)
        units = [dict(unit) for unit in card.get("evidence_units") or [] if isinstance(unit, Mapping)]
        if units:
            scope = external_scope_bucket(card.get("entity_scope"))
            key = (scope, clean_external_text(card.get("primary_family")) or "other")
            result.setdefault(key, []).append({**dict(card), "argument_key": argument_key, "evidence_units": units})
    return result

def _validate_group(raw: object, cards: list[dict] | None) -> tuple[dict | None, str]:
    if not isinstance(raw, Mapping) or set(raw) != _GROUP_KEYS or not cards:
        return None, "unknown_or_invalid_group"
    parts = raw.get("parts")
    expected = [(*external_unit_key(card["argument_key"], unit.get("unit_id")), unit) for card in cards for unit in card["evidence_units"]]
    if not isinstance(parts, list) or len(parts) != len(expected):
        return None, "unit_coverage_mismatch"
    accepted = []
    for index, (part, (argument_key, unit_id, unit)) in enumerate(zip(parts, expected)):
        if not isinstance(part, Mapping) or set(part) != _PART_KEYS:
            return None, "invalid_part_shape"
        if external_unit_key(part.get("argument_key"), part.get("unit_id")) != (argument_key, unit_id):
            return None, "unit_order_or_owner_mismatch"
        relation, quote = clean_external_text(part.get("relation")), clean_external_text(part.get("quote"))
        if relation not in _RELATIONS or (index == 0) != (relation == "first"):
            return None, "invalid_relation"
        if not _valid_quote(quote, clean_external_text(unit.get("text"))):
            return None, "invalid_quote"
        accepted.append({"argument_key": argument_key, "unit_id": unit_id, "quote": quote, "relation": relation})
    return {"scope_bucket": clean_external_text(raw.get("scope_bucket")), "primary_family": clean_external_text(raw.get("primary_family")),
            "parts": accepted}, ""

def _valid_quote(quote: str, source: str) -> bool:
    return bool(quote and source.startswith(quote) and re.search(r"[\u4e00-\u9fffA-Za-z0-9]", quote)
                and not quote.endswith(("…", "...")) and (quote == source or quote[-1] in _BOUNDARY))

def _group_key(group: object) -> tuple[str, str]:
    return (clean_external_text(group.get("scope_bucket")), clean_external_text(group.get("primary_family"))) if isinstance(group, Mapping) else ("", "")

def _result(status: str, groups: list[dict], rejected: dict[str, int]) -> dict:
    return {"status": status, "groups": groups, "diagnostics": {"accepted_group_count": len(groups),
                                                                  "rejected_by_reason": dict(rejected)}}

def _read_error(status: str, reason: str) -> dict:
    return {"status": status, "groups": [], "diagnostics": {"rejected_by_reason": {reason: 1}}}


def _bump(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1
