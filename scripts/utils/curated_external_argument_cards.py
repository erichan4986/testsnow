"""Deterministic display-only argument cards for curated external evidence."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

try:
    from .synthesis_credit import citation_identity
except ImportError:
    from synthesis_credit import citation_identity


SOURCE_UNIT_SCHEMA = "curated_external_source_unit.v1"
SELECTION_SCHEMA = "curated_external_unit_selection.v1"
SELECTOR_VERSION = "external_unit_selector.v2"
ARGUMENT_CARD_V3_SCHEMA = "curated_external_argument_card.v3"
ARGUMENT_PACK_V3_SCHEMA = "curated_external_argument_pack.v3"
V3_VALIDATOR_VERSION = "external_argument_validator.v3"
_PEER_TERMS = ("同业", "竞品", "对比", "三巨头", "行业", "竞争格局")
_SOURCE_UNIT_BOUNDARY_RE = re.compile(
    r"(?:\.(?=\d)|[^。！？；.!?;])+(?:[。！？；!?;]|(?<!\d)\.(?!\d))"
)
_STRUCTURAL_SOURCE_LABEL_RE = re.compile(
    r"^(?:[（(]?[一二三四五六七八九十0-9]+[、.)）]?\s*)?"
    r"(?:行业观点|风险提示|投资建议|免责声明|目录|返回顶部|相关阅读)[：:]?$"
)
_SOURCE_NOISE_PREFIX_RE = re.compile(
    r"^(?:[A-Za-z]{1,4}\)\s*记者|本报告(?:系统)?(?:调研|研究|分析))",
    re.IGNORECASE,
)
_COVERAGE_FAMILY_RULES = (
    ("financial_quality", ("财务", "营收", "收入", "利润", "毛利", "费用", "现金流", "业绩")),
    ("technology_product", ("技术", "产品", "fpga", "cpo", "npo", "xpo", "硅光", "芯片", "mcu")),
    ("commercialization", ("商业化", "量产", "认证", "验证", "导入", "定点", "出货")),
    ("competitive_landscape", ("竞争", "同业", "格局", "份额", "市占率", "市场份额", "领先")),
    ("demand_customer", ("客户", "需求", "订单", "资本开支", "capex")),
    ("capacity_delivery", ("供应链", "交付", "产能", "物料", "原材料", "预付款")),
    ("policy_geopolitics", ("政策", "制裁", "管制", "清单", "地缘")),
    ("valuation_expectation", ("估值", "市值", "股价", "pe", "预期差", "情景")),
)
_SELECTOR_FORBIDDEN_FIELDS = {
    "claim", "source_quote", "topic_family", "entity_scope", "incremental_delta",
    "target_price", "score", "risk_score", "recommendation",
}
_V3_CARD_FORBIDDEN_FIELDS = _SELECTOR_FORBIDDEN_FIELDS - {"entity_scope"}
_SELECTOR_DECISION_KEYS = {"unit_id", "action", "group_id", "reason"}
_CONTINUATION_SUBJECT_RE = re.compile(
    r"^(?:(?:同时|此外|其中)[，,:：]?\s*)?(?:公司|本公司|该公司|该产品|上述产品|相关产品)"
)
_AMBIGUOUS_CONTINUATION_RE = re.compile(r"^(?:(?:同时|此外|其中)[，,:：]?\s*)?(?:其|双方)")
_CONTINUATION_RELATION_RE = re.compile(
    r"竞争对手|同行|同业|友商|供应商|合作方|合作伙伴|相比|相较|联合|共同"
)
_PEER_ACTION_RE = re.compile(r"发布|推出|量产|验证|导入|交付|订单|扩产|投产|合作|收购|限制|涨价|降价")
_NAMED_SUBJECT_ACTION_RE = re.compile(
    r"(?:^|[，、；;：:])([\u4e00-\u9fffA-Za-z]{2,16})(?:宣布|发布|推出|量产|验证|导入|交付|扩产|投产|合作|收购)"
)


def materialize_external_source_units(
    source_packets: list[dict], *, stock_name: str,
) -> list[dict]:
    """Split canonical source packets into immutable, complete source units."""
    del stock_name  # Transport is broad; target admission is a later deterministic step.
    units = []
    for packet in source_packets or []:
        if not isinstance(packet, Mapping):
            continue
        source_id = _clean(packet.get("source_id"))
        content = str(packet.get("content") or "")
        if not source_id or not content:
            continue
        source_hash = _clean(packet.get("source_content_hash")) or _hash(content)
        ordinal = 0
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or _STRUCTURAL_SOURCE_LABEL_RE.fullmatch(stripped):
                continue
            for match in _SOURCE_UNIT_BOUNDARY_RE.finditer(line):
                text = match.group(0).strip()
                if (not text or _STRUCTURAL_SOURCE_LABEL_RE.fullmatch(text)
                        or _SOURCE_NOISE_PREFIX_RE.match(text)):
                    continue
                unit_hash = _hash(text)
                units.append({
                    "schema_version": SOURCE_UNIT_SCHEMA,
                    "unit_id": f"external-unit:{source_id}:{ordinal}:{unit_hash[:16]}",
                    "source_id": source_id,
                    "source_ordinal": ordinal,
                    "text": text,
                    "source_block_hash": source_hash,
                    "unit_hash": unit_hash,
                    "target_bound": False,
                    "coverage_families": _coverage_families(text),
                })
                ordinal += 1
    return units


def enrich_external_evidence_group(units: list[dict], *, stock_name: str) -> dict:
    """Derive scope and coverage from exact evidence text, without model metadata."""
    texts = [str(unit.get("text") or "") for unit in units or [] if isinstance(unit, Mapping)]
    evidence = " ".join(text for text in texts if text)
    stock = _clean(stock_name)
    target_units = [unit for unit in units or [] if isinstance(unit, Mapping) and unit.get("target_bound")]
    families = _ordered_family_union(target_units or units)
    target_bound = bool(target_units) or bool(stock and stock in evidence)
    peer_context = any(term in evidence for term in _PEER_TERMS)
    entities = [entity for entity in _mentioned_entities(evidence) if entity != stock]
    scope = "peer_or_industry"
    if target_bound:
        scope = "target_with_peer_context" if peer_context or entities else "target"
    return {
        "entity_scope": scope,
        "target_entity": stock if target_bound else "",
        "coverage_families": families,
        "primary_family": families[0] if families else "other",
    }


def prepare_external_argument_material(
    units: list[dict], *, stock_name: str, baseline_text: str,
) -> dict:
    """Create deterministic target bundles and one optional peer selector pool."""
    baseline = _normalized_source_text(baseline_text)
    mandatory, optional, rejected, rows_by_id, source_units = [], [], {}, {}, {}
    for unit in units or []:
        if not isinstance(unit, Mapping):
            continue
        source_units.setdefault(str(unit.get("source_id") or ""), []).append(dict(unit))
        enriched = enrich_external_evidence_group([dict(unit)], stock_name=stock_name)
        row = {**dict(unit), **enriched, "target_bound": enriched["entity_scope"].startswith("target")}
        if not row["coverage_families"]:
            continue
        unit_id = str(row.get("unit_id") or "")
        if row["target_bound"]:
            if _normalized_source_text(row.get("text")) in baseline:
                rejected["baseline_duplicate"] = rejected.get("baseline_duplicate", 0) + 1
                continue
            row["admission"] = "mandatory_target"
            mandatory.append(row)
        else:
            row["admission"] = "optional_peer"
            optional.append(row)
        rows_by_id[unit_id] = row
    source_indexes = {}
    for source_id, members in source_units.items():
        members.sort(key=lambda unit: int(unit.get("source_ordinal") or 0))
        source_indexes.update((str(unit.get("unit_id") or ""), (source_id, index)) for index, unit in enumerate(members))
    continuation_ids, bundles = set(), []
    rejected_count = truncated_count = 0
    mandatory_ids = {str(row.get("unit_id") or "") for row in mandatory}
    for anchor in mandatory:
        location = source_indexes.get(str(anchor.get("unit_id") or ""))
        if location is None:
            continue
        source_id, anchor_index = location
        ordered = source_units[source_id]
        bundle = [anchor]
        for candidate in ordered[anchor_index + 1:anchor_index + 3]:
            candidate_id = str(candidate.get("unit_id") or "")
            if candidate_id in mandatory_ids:
                break
            state = _continuation_state(candidate, baseline=baseline)
            if state == "rejected":
                rejected_count += 1
                break
            if state != "accepted":
                break
            row = rows_by_id.get(candidate_id)
            if row is None or not row.get("coverage_families"):
                break
            bundle.append({**row, "target_bound": True, "admission": "target_continuation"})
            continuation_ids.add(candidate_id)
        next_index = anchor_index + len(bundle)
        if next_index < len(ordered) and len(bundle) == 3:
            next_state = _continuation_state(ordered[next_index], baseline=baseline)
            if next_state == "accepted":
                truncated_count += 1
            elif next_state == "rejected":
                rejected_count += 1
        bundles.append({
            "bundle_key": f"target-bundle:{source_id}:{anchor.get('source_ordinal')}",
            "units": bundle,
            "coverage_families": _ordered_family_union(bundle),
        })
    optional_raw = [
        row for row in optional if str(row.get("unit_id") or "") not in continuation_ids
    ]
    optional_pool, low_signal_count, duplicate_count = _eligible_optional_peer_units(
        optional_raw, baseline=baseline, rejected=rejected,
    )
    diagnostics = {
        "mandatory_target_unit_count": len(mandatory),
        "target_bundle_count": len(bundles),
        "continuation_rejected_count": rejected_count,
        "continuation_truncated_count": truncated_count,
        "optional_peer_raw_count": len(optional_raw),
        "optional_peer_eligible_count": len(optional_pool),
        "optional_peer_low_signal_count": low_signal_count,
        "optional_peer_duplicate_count": duplicate_count,
        "rejected_by_reason": rejected,
    }
    return {
        "target_bundles": bundles,
        "optional_peer_units": optional_pool,
        "diagnostics": diagnostics,
    }


def validate_external_unit_selection(
    source_units: list[dict], selection: dict, *, mandatory_ids: set[str],
) -> dict:
    """Validate an ID-only selector response before any card is built."""
    if not isinstance(selection, Mapping) or selection.get("schema_version") != SELECTION_SCHEMA:
        return {"status": "invalid", "reason": "selection_schema_mismatch"}
    if _SELECTOR_FORBIDDEN_FIELDS.intersection(selection):
        return {"status": "invalid", "reason": "selection_forbidden_field"}
    decisions = selection.get("decisions")
    if not isinstance(decisions, list):
        return {"status": "invalid", "reason": "selection_decisions_not_list"}
    expected_ids = [str(unit.get("unit_id") or "") for unit in source_units or []]
    expected = set(expected_ids)
    decision_ids = []
    for decision in decisions:
        if not isinstance(decision, Mapping):
            return {"status": "invalid", "reason": "selection_invalid_decision"}
        if _SELECTOR_FORBIDDEN_FIELDS.intersection(decision) or set(decision).difference(_SELECTOR_DECISION_KEYS):
            return {"status": "invalid", "reason": "selection_forbidden_field"}
        unit_id = str(decision.get("unit_id") or "")
        if not unit_id or decision.get("action") not in {"keep", "skip"}:
            return {"status": "invalid", "reason": "selection_invalid_decision"}
        decision_ids.append(unit_id)
    received = set(decision_ids)
    if len(decision_ids) != len(received):
        return {"status": "invalid", "reason": "selection_duplicate_unit_id"}
    if received.difference(expected):
        return {"status": "invalid", "reason": "selection_unknown_unit_id"}
    if expected.difference(received):
        return {"status": "invalid", "reason": "selection_missing_unit_id"}
    by_id = {str(decision["unit_id"]): decision for decision in decisions}
    if any(by_id[unit_id].get("action") != "keep" for unit_id in mandatory_ids):
        return {"status": "invalid", "reason": "mandatory_target_skipped"}
    units_by_id = {str(unit.get("unit_id") or ""): unit for unit in source_units or []}
    groups: dict[str, list[dict]] = {}
    for unit_id, decision in by_id.items():
        group_id = str(decision.get("group_id") or "")
        if decision.get("action") == "skip" and group_id:
            return {"status": "invalid", "reason": "selection_invalid_group"}
        if group_id:
            groups.setdefault(group_id, []).append(units_by_id[unit_id])
    for members in groups.values():
        ordinals = sorted(int(member.get("source_ordinal") or 0) for member in members)
        source_ids = {str(member.get("source_id") or "") for member in members}
        if (
            not 1 <= len(members) <= 3
            or len(source_ids) != 1
            or ordinals != list(range(ordinals[0], ordinals[0] + len(ordinals)))
        ):
            return {"status": "invalid", "reason": "selection_invalid_group"}
    return {"status": "ok", "reason": ""}


def _coverage_families(text: str) -> list[str]:
    lower = str(text or "").lower()
    return [
        family for family, terms in _COVERAGE_FAMILY_RULES
        if any(term.lower() in lower for term in terms)
    ]


def _ordered_family_union(units: list[dict]) -> list[str]:
    present = {
        family
        for unit in units or [] if isinstance(unit, Mapping)
        for family in unit.get("coverage_families") or []
    }
    return [family for family, _ in _COVERAGE_FAMILY_RULES if family in present]


def _continuation_state(unit: Mapping[str, Any], *, baseline: str) -> str:
    text = str(unit.get("text") or "").strip()
    normalized = _normalized_source_text(text)
    if not text or (normalized and normalized in baseline):
        return "rejected"
    if _AMBIGUOUS_CONTINUATION_RE.match(text):
        return "rejected"
    if not _CONTINUATION_SUBJECT_RE.match(text):
        return "other"
    return "rejected" if _CONTINUATION_RELATION_RE.search(text) else "accepted"


def _eligible_optional_peer_units(
    units: list[dict], *, baseline: str, rejected: dict,
) -> tuple[list[dict], int, int]:
    candidates, seen_exact = [], set()
    low_signal_count = duplicate_count = 0
    for unit in units:
        normalized = _normalized_source_text(unit.get("text"))
        if normalized and normalized in baseline:
            rejected["baseline_duplicate"] = rejected.get("baseline_duplicate", 0) + 1
            continue
        text = str(unit.get("text") or "")
        peer_context = any(term in text for term in _PEER_TERMS) or _NAMED_SUBJECT_ACTION_RE.search(text)
        if not (peer_context and (re.search(r"\d", text) or _PEER_ACTION_RE.search(text))):
            low_signal_count += 1
            continue
        if normalized in seen_exact:
            duplicate_count += 1
            continue
        seen_exact.add(normalized)
        candidates.append(unit)
    contained_ids = set()
    by_source: dict[str, list[dict]] = {}
    for unit in candidates:
        by_source.setdefault(str(unit.get("source_id") or ""), []).append(unit)
    for members in by_source.values():
        keys = {str(unit.get("unit_id") or ""): _normalized_source_text(unit.get("text")).rstrip("。！？；.!?;") for unit in members}
        for unit in members:
            unit_id = str(unit.get("unit_id") or "")
            key = keys[unit_id]
            if key and any(key != other and key in other for other in keys.values()):
                contained_ids.add(unit_id)
    duplicate_count += len(contained_ids)
    return [
        unit for unit in candidates if str(unit.get("unit_id") or "") not in contained_ids
    ], low_signal_count, duplicate_count

def _normalized_source_text(value: object) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def build_external_argument_pack(
    *, stock_name: str, source_packets: list[dict], baseline_text: str,
    selections: list[dict], selector_version: str = SELECTOR_VERSION,
    prepared_material: dict | None = None, selector_request_count: int = 0,
) -> dict:
    """Build a v3 pack from immutable units and ID-only selector decisions."""
    stock = _clean(stock_name)
    packets = [dict(packet) for packet in source_packets or [] if isinstance(packet, Mapping)]
    sources = {
        _clean(packet.get("source_id")): packet for packet in packets
        if _clean(packet.get("source_id"))
    }
    units = materialize_external_source_units(packets, stock_name=stock)
    prepared = prepared_material or prepare_external_argument_material(
        units, stock_name=stock, baseline_text=baseline_text,
    )
    peer_units = prepared["optional_peer_units"]
    batches = external_selection_batches(peer_units)
    if len(selections or []) != len(batches):
        return _v3_pack_result(
            stock, packets, baseline_text, status="selector_incomplete", selector_version=selector_version,
            diagnostics={**prepared["diagnostics"], "rejection_reasons": ["selection_batch_count_mismatch"]},
        )

    decisions = {}
    for batch_index, (batch, selection) in enumerate(zip(batches, selections or [])):
        checked = validate_external_unit_selection(batch, selection, mandatory_ids=set())
        if checked["status"] != "ok":
            return _v3_pack_result(
                stock, packets, baseline_text, status="selector_incomplete", selector_version=selector_version,
                diagnostics={**prepared["diagnostics"], "rejection_reasons": [checked["reason"]]},
            )
        decisions.update({
            str(row["unit_id"]): {**dict(row), "_batch_index": batch_index}
            for row in selection["decisions"]
        })

    cards, citations, identity_refs = [], {}, {}
    selected_groups = [
        bundle["units"] for bundle in prepared["target_bundles"]
    ] + _selected_unit_groups(peer_units, decisions)
    target_card_count = len(prepared["target_bundles"])
    for members in selected_groups:
        card = _build_v3_card(stock, members)
        for unit in card["evidence_units"]:
            source = sources.get(unit["source_id"])
            if source is None:
                return _v3_pack_result(
                    stock, packets, baseline_text, status="selector_incomplete", selector_version=selector_version,
                    diagnostics={**prepared["diagnostics"], "rejection_reasons": ["unknown_source_id"]},
                )
            meta = _citation_from_packet(source, unit["unit_hash"])
            identity = citation_identity(meta, fallback_ref=unit["source_id"])
            ref = identity_refs.get(identity)
            if ref is None:
                ref = len(citations) + 1
                identity_refs[identity], citations[ref] = ref, meta
            unit["citation_refs"] = [ref]
        card["citation_refs"] = list(dict.fromkeys(
            ref for unit in card["evidence_units"] for ref in unit["citation_refs"]
        ))
        card["source_identity"] = [
            list(citation_identity(citations[ref], fallback_ref=ref)) for ref in card["citation_refs"]
        ]
        cards.append(card)
    used_refs = {ref for card in cards for ref in card["citation_refs"]}
    return {
        "schema_version": ARGUMENT_PACK_V3_SCHEMA,
        "stock_name": stock,
        "status": "ready",
        "selector_version": selector_version,
        "validator_version": V3_VALIDATOR_VERSION,
        "source_packet_fingerprints": [
            {"source_id": source_id, "source_content_hash": _clean(packet.get("source_content_hash"))}
            for source_id, packet in sources.items()
        ],
        "baseline_fingerprint": f"sha256:{_hash(_normalized_source_text(baseline_text))}",
        "cards": cards,
        "citations": {ref: citations[ref] for ref in used_refs},
        "diagnostics": {
            **prepared["diagnostics"],
            "source_unit_count": len(units),
            "selector_batch_count": len(batches),
            "selector_request_count": selector_request_count,
            "accepted_count": len(cards),
            "accepted_target_card_count": target_card_count,
            "accepted_peer_card_count": len(cards) - target_card_count,
        },
    }


def _v3_pack_result(
    stock: str, packets: list[dict], baseline_text: str, *, status: str,
    selector_version: str, diagnostics: dict,
) -> dict:
    return {
        "schema_version": ARGUMENT_PACK_V3_SCHEMA,
        "stock_name": stock,
        "status": status,
        "selector_version": selector_version,
        "validator_version": V3_VALIDATOR_VERSION,
        "source_packet_fingerprints": [
            {"source_id": _clean(packet.get("source_id")), "source_content_hash": _clean(packet.get("source_content_hash"))}
            for packet in packets if _clean(packet.get("source_id"))
        ],
        "baseline_fingerprint": f"sha256:{_hash(_normalized_source_text(baseline_text))}",
        "cards": [], "citations": {}, "diagnostics": diagnostics,
    }


def external_selection_batches(units: list[dict], *, batch_size: int = 24) -> list[list[dict]]:
    """Return per-source selector batches in immutable source order."""
    grouped: dict[str, list[dict]] = {}
    for unit in units:
        grouped.setdefault(str(unit.get("source_id") or ""), []).append(unit)
    batches = []
    for members in grouped.values():
        ordered = sorted(members, key=lambda unit: int(unit.get("source_ordinal") or 0))
        batches.extend(ordered[start:start + batch_size] for start in range(0, len(ordered), batch_size))
    return batches


def _selected_unit_groups(units: list[dict], decisions: Mapping[str, Mapping[str, Any]]) -> list[list[dict]]:
    indexed = {str(unit["unit_id"]): (index, unit) for index, unit in enumerate(units)}
    groups: dict[tuple[int, str, str], list[tuple[int, dict]]] = {}
    standalone: list[tuple[int, list[dict]]] = []
    for unit_id, (index, unit) in indexed.items():
        decision = decisions[unit_id]
        if decision.get("action") != "keep":
            continue
        group_id = str(decision.get("group_id") or "")
        if group_id:
            group_key = (
                int(decision.get("_batch_index") or 0),
                str(unit.get("source_id") or ""),
                group_id,
            )
            groups.setdefault(group_key, []).append((index, unit))
        else:
            standalone.append((index, [unit]))
    grouped = [
        (
            min(index for index, _ in members),
            [unit for _, unit in sorted(members, key=lambda row: int(row[1].get("source_ordinal") or 0))],
        )
        for members in groups.values()
    ]
    return [members for _, members in sorted([*standalone, *grouped], key=lambda row: row[0])]


def _build_v3_card(stock: str, members: list[dict]) -> dict:
    enrichment = enrich_external_evidence_group(members, stock_name=stock)
    unit_ids = [str(unit["unit_id"]) for unit in members]
    argument_key = f"{enrichment['primary_family']}:{enrichment['entity_scope']}:{_hash('|'.join(unit_ids))[:20]}"
    evidence_units = [{
        "schema_version": SOURCE_UNIT_SCHEMA,
        "unit_id": str(unit["unit_id"]),
        "text": str(unit["text"]),
        "unit_hash": str(unit["unit_hash"]),
        "source_id": str(unit["source_id"]),
        "source_ordinal": int(unit["source_ordinal"]),
        "source_block_hash": str(unit["source_block_hash"]),
        "evidence_status": "source_unit_verified",
        "citation_refs": [],
    } for unit in members]
    card = {
        "schema_version": ARGUMENT_CARD_V3_SCHEMA,
        "card_id": f"external-argument:{stock}:{_hash(argument_key)[:16]}",
        "stock_name": stock,
        "entity_scope": enrichment["entity_scope"],
        "target_entity": enrichment["target_entity"],
        "coverage_families": enrichment["coverage_families"],
        "primary_family": enrichment["primary_family"],
        "evidence_units": evidence_units,
        "argument_key": argument_key,
        "citation_refs": [], "source_identity": [],
        "quality_action": "preview_only", "synthesis_display_only": True,
        "knowledge_eligible": False, "scoring_eligible": False, "risk_score_eligible": False,
        "verification_status": "professional_observation",
    }
    return card


def read_external_argument_pack(
    pack_json: str | Path | None, *, expected_stock_name: str,
) -> dict:
    """Read a v3 pack without opening source packets, legacy caches, or an LLM."""
    if not pack_json:
        return _pack_read_result("missing_config")
    path = Path(pack_json)
    if not path.exists():
        return _pack_read_result("missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _pack_read_result("reader_error", reason=str(exc))
    if not isinstance(payload, Mapping):
        return _pack_read_result("invalid", reason="pack_not_object")
    if payload.get("schema_version") != ARGUMENT_PACK_V3_SCHEMA:
        return _pack_read_result("stale", reason="schema_version_mismatch")
    if (payload.get("selector_version"), payload.get("validator_version")) != (
        SELECTOR_VERSION, V3_VALIDATOR_VERSION,
    ):
        return _pack_read_result("stale", reason="producer_version_mismatch")
    if _clean(payload.get("stock_name")) != _clean(expected_stock_name):
        return _pack_read_result("stock_identity_mismatch")
    if payload.get("status") != "ready":
        return _pack_read_result("invalid", reason="pack_not_ready")
    citations = _normalized_citations(payload.get("citations") or {})
    cards = payload.get("cards") or []
    fingerprints = payload.get("source_packet_fingerprints") or []
    if not isinstance(cards, list) or not isinstance(fingerprints, list):
        return _pack_read_result("invalid", reason="invalid_pack_collections")
    source_hashes = {}
    for row in fingerprints:
        if not isinstance(row, Mapping):
            return _pack_read_result("invalid", reason="invalid_source_fingerprint")
        source_id = _clean(row.get("source_id"))
        source_hash = _clean(row.get("source_content_hash"))
        if not source_id or not source_hash or source_id in source_hashes:
            return _pack_read_result("invalid", reason="invalid_source_fingerprint")
        source_hashes[source_id] = source_hash
    for card in cards:
        reason = _stored_v3_card_error(card, citations, source_hashes, expected_stock_name)
        if reason:
            return _pack_read_result("invalid", reason=reason)
    ref_unit_hashes: dict[int, set[str]] = {}
    for card in cards:
        for unit in card.get("evidence_units") or []:
            for ref in unit.get("citation_refs") or []:
                ref_unit_hashes.setdefault(int(ref), set()).add(_clean(unit.get("unit_hash")))
    if any(
        _clean(citations[ref].get("source_quote_hash")) not in hashes
        for ref, hashes in ref_unit_hashes.items()
    ):
        return _pack_read_result("invalid", reason="citation_quote_hash_mismatch")
    return {
        "status": "ok" if cards else "empty",
        "cards": cards,
        "citations": citations,
        "stats": payload.get("diagnostics") or {},
        "pack": payload,
    }


def _citation_from_packet(source: Mapping[str, Any], quote_hash: str) -> dict:
    return {
        "source": "微信公众号精选观察", "author": _clean(source.get("account")),
        "title": _clean(source.get("title")) or "外部观点",
        "url": _clean(source.get("source_url") or source.get("source_ref")),
        "source_ref": _clean(source.get("source_ref")), "source_id": _clean(source.get("source_id")),
        "source_block_hash": _clean(source.get("source_content_hash")),
        "source_quote_hash": quote_hash, "publish_time": _clean(source.get("publish_time")),
        "source_type": "curated_external_analysis_evidence", "source_credit": int(source.get("source_credit") or 55),
        "verification_status": "professional_observation", "quality_action": "preview_only",
        "synthesis_display_only": True, "scoring_eligible": False, "risk_score_eligible": False,
    }


def _stored_v3_card_error(
    card: object,
    citations: Mapping[int, dict],
    source_hashes: Mapping[str, str],
    stock_name: str,
) -> str:
    if not isinstance(card, Mapping) or card.get("schema_version") != ARGUMENT_CARD_V3_SCHEMA:
        return "invalid_card_schema"
    if _clean(card.get("stock_name")) != _clean(stock_name):
        return "card_stock_mismatch"
    if _V3_CARD_FORBIDDEN_FIELDS.intersection(card):
        return "forbidden_card_field"
    safe_values = (
        card.get("quality_action"), card.get("synthesis_display_only"),
        card.get("knowledge_eligible"), card.get("scoring_eligible"), card.get("risk_score_eligible"),
    )
    if safe_values != ("preview_only", True, False, False, False):
        return "unsafe_card_flags"
    scope = card.get("entity_scope")
    if scope not in {"target", "target_with_peer_context", "peer_or_industry"}:
        return "invalid_entity_scope"
    families = card.get("coverage_families")
    if not isinstance(families, list) or not all(isinstance(family, str) for family in families):
        return "invalid_coverage_families"
    if families and card.get("primary_family") not in families:
        return "invalid_primary_family"
    units = card.get("evidence_units")
    if not isinstance(units, list) or not 1 <= len(units) <= 3:
        return "invalid_evidence_count"
    source_ids, ordinals, evidence_refs = set(), [], []
    for unit in units:
        if not isinstance(unit, Mapping) or unit.get("schema_version") != SOURCE_UNIT_SCHEMA:
            return "invalid_evidence_unit"
        text = unit.get("text")
        if not isinstance(text, str) or _hash(text) != _clean(unit.get("unit_hash")):
            return "evidence_hash_mismatch"
        source_id = _clean(unit.get("source_id"))
        source_hash = _clean(unit.get("source_block_hash"))
        if not _clean(unit.get("unit_id")) or not source_id or not source_hash:
            return "invalid_evidence_identity"
        if source_hashes.get(source_id) != source_hash:
            return "evidence_source_mismatch"
        refs = _normalized_refs(unit.get("citation_refs"))
        if not refs or not _refs_exist(refs, citations):
            return "dangling_evidence_ref"
        if any(
            _clean(citations[ref].get("source_id")) != source_id
            or _clean(citations[ref].get("source_block_hash")) != source_hash
            for ref in refs
        ):
            return "citation_source_mismatch"
        source_ids.add(source_id)
        try:
            ordinals.append(int(unit.get("source_ordinal")))
        except (TypeError, ValueError):
            return "invalid_evidence_identity"
        evidence_refs.extend(refs)
    if len(source_ids) != 1 or ordinals != list(range(ordinals[0], ordinals[0] + len(ordinals))):
        return "invalid_evidence_group"
    card_refs = _normalized_refs(card.get("citation_refs"))
    if not card_refs or card_refs != list(dict.fromkeys(evidence_refs)) or not _refs_exist(card_refs, citations):
        return "dangling_card_ref"
    expected_identity = [list(citation_identity(citations[ref], fallback_ref=ref)) for ref in card_refs]
    if card.get("source_identity") != expected_identity:
        return "source_identity_mismatch"
    return ""


def _refs_exist(refs: object, citations: Mapping[int, dict]) -> bool:
    if not isinstance(refs, list):
        return False
    try:
        return all(int(ref) in citations for ref in refs)
    except (TypeError, ValueError):
        return False


def _normalized_refs(refs: object) -> list[int]:
    if not isinstance(refs, list):
        return []
    try:
        return [int(ref) for ref in refs]
    except (TypeError, ValueError):
        return []


def _pack_read_result(status: str, *, reason: str = "") -> dict:
    stats = {"rejection_reasons": [reason]} if reason else {}
    return {"status": status, "cards": [], "citations": {}, "stats": stats, "pack": None}


def _mentioned_entities(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,16}(?:股份|科技|电子|微电|智能|集团)", text)))


def _normalized_citations(citations: Mapping[Any, Any]) -> dict[int, dict]:
    result = {}
    for key, value in citations.items():
        try:
            ref = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(value, Mapping):
            result[ref] = dict(value)
    return result


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
