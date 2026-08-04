"""Strict v4 argument packs built from canonical external source documents."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from typing import Any

try:
    from .external_evidence import (
        EXTERNAL_FAMILY_ORDER,
        validate_external_evidence_unit,
    )
    from .external_scope import resolve_external_scope, validate_scope_provenance
    from .external_source_document import validate_external_source_document
    from .external_narrative_plan import validate_external_narrative_plan
except ImportError:
    from external_evidence import EXTERNAL_FAMILY_ORDER, validate_external_evidence_unit
    from external_scope import resolve_external_scope, validate_scope_provenance
    from external_source_document import validate_external_source_document
    from external_narrative_plan import validate_external_narrative_plan

ARGUMENT_CARD_SCHEMA = "curated_external_argument_card.v4"
ARGUMENT_PACK_SCHEMA = "curated_external_argument_pack.v4"
SELECTION_SCHEMA = "curated_external_unit_selection.v2"
PACK_VALIDATOR_VERSION = "external_argument_validator.v4"
MAX_SELECTOR_PROMPT_CHARS = 24_000

_TARGET_ORIGINS = {"explicit_target", "target_document_context", "target_peer_relation"}
_FORBIDDEN_FIELDS = {
    "claim", "source_quote", "topic_family", "entity_scope", "incremental_delta",
    "target_price", "score", "risk_score", "recommendation", "text", "relation",
}
_FORBIDDEN_CARD_FIELDS = _FORBIDDEN_FIELDS - {"entity_scope", "text"}


def prepare_external_argument_material_v4(
    documents: Iterable[Mapping[str, Any]], *, stock_name: str, baseline_text: str,
) -> dict:
    """Resolve immutable v4 units before target admission or peer selection."""
    target, peer, rejected, all_units = [], [], {}, []
    baseline = _normalized(baseline_text)
    valid_documents, rejected_documents = _valid_source_documents(documents)
    for document in valid_documents:
        for unit in resolve_external_scope(document, stock_name=stock_name):
            all_units.append(unit)
            if unit.get("argument_status") != "admitted":
                rejected[str(unit.get("argument_status") or "incomplete")] = rejected.get(str(unit.get("argument_status") or "incomplete"), 0) + 1
                continue
            if _normalized(unit.get("text")) in baseline:
                rejected["baseline_duplicate"] = rejected.get("baseline_duplicate", 0) + 1
                continue
            origin = str((unit.get("scope_provenance") or {}).get("origin") or "")
            if origin in _TARGET_ORIGINS:
                target.append(unit)
            elif origin in {"explicit_peer", "industry_context"}:
                peer.append(unit)
            else:
                rejected[origin or "ambiguous"] = rejected.get(origin or "ambiguous", 0) + 1
    return {
        "source_document_hashes": [str(document.get("document_hash") or "") for document in valid_documents],
        "target_cards": _cards_from_runs(stock_name, target, _target_unit_scope),
        "peer_units": peer,
        "all_units": all_units,
        "diagnostics": {
            "source_unit_count": len(all_units), "target_unit_count": len(target),
            "peer_unit_count": len(peer), "rejected_by_reason": rejected,
            "rejected_source_documents": rejected_documents,
        },
    }


def external_selection_batches_v4(
    units: Iterable[Mapping[str, Any]], *, max_chars: int = MAX_SELECTOR_PROMPT_CHARS,
) -> list[list[dict]]:
    """Pack whole source blocks into the fewest character-bounded peer-selector batches."""
    blocks: list[list[dict]] = []
    current_key, current = None, []
    for unit in sorted((dict(row) for row in units if isinstance(row, Mapping)), key=_unit_order):
        key = (unit.get("source_id"), unit.get("block_id"))
        if current and key != current_key:
            blocks.append(current)
            current = []
        current_key = key
        current.append(unit)
    if current:
        blocks.append(current)
    batches, batch, size = [], [], 0
    for block in blocks:
        block_size = sum(len(str(unit.get("text") or "")) + 96 for unit in block)
        if batch and size + block_size > max_chars:
            batches.append(batch)
            batch, size = [], 0
        batch.extend(block)
        size += block_size
    return [batch for batch in (*batches, batch) if batch]


def build_external_argument_pack_v4(
    documents: list[dict], *, stock_name: str, baseline_text: str,
    selections: list[dict], prepared_material: Mapping[str, Any] | None = None,
    selector_request_count: int = 0,
) -> dict:
    """Build a ready v4 pack or a fail-closed selector-incomplete result."""
    valid_documents, rejected_documents = _valid_source_documents(documents)
    prepared = (
        dict(prepared_material)
        if isinstance(prepared_material, Mapping)
        else prepare_external_argument_material_v4(documents, stock_name=stock_name, baseline_text=baseline_text)
    )
    if rejected_documents:
        diagnostics = dict(prepared.get("diagnostics") or {})
        diagnostics["rejected_source_documents"] = rejected_documents
        prepared["diagnostics"] = diagnostics
    if rejected_documents or not valid_documents:
        return _failure_pack("source_input_degraded", stock_name, prepared)
    batches = external_selection_batches_v4(prepared["peer_units"])
    if len(selections) != len(batches):
        return _failure_pack(
            "selector_incomplete", stock_name, prepared,
            source_documents=valid_documents, rejection_reason="selection_batch_count_mismatch",
        )
    selected_peer = []
    for batch, selection in zip(batches, selections):
        result = validate_external_unit_selection_v4(batch, selection)
        if result["status"] != "ok":
            return _failure_pack(
                "selector_incomplete", stock_name, prepared,
                source_documents=valid_documents, rejection_reason=result["reason"],
            )
        decisions = {str(row["unit_id"]): row for row in selection["decisions"]}
        selected_peer.extend(_selected_peer_cards(stock_name, batch, decisions))
    cards = [*prepared["target_cards"], *selected_peer]
    citations = _attach_citations(cards, valid_documents)
    return {
        "schema_version": ARGUMENT_PACK_SCHEMA,
        "status": "ready", "stock_name": stock_name,
        "validator_version": PACK_VALIDATOR_VERSION,
        "source_documents": valid_documents,
        "baseline_fingerprint": _hash(_normalized(baseline_text)),
        "cards": cards, "citations": citations,
        "diagnostics": {
            **prepared["diagnostics"], "selector_batch_count": len(batches),
            "selector_request_count": selector_request_count,
            "accepted_target_card_count": len(prepared["target_cards"]),
            "accepted_peer_card_count": len(selected_peer), "accepted_count": len(cards),
        },
    }


def _valid_source_documents(documents: Iterable[Mapping[str, Any]]) -> tuple[list[dict], dict[str, list[str]]]:
    valid, rejected = [], {}
    for document in documents:
        if not isinstance(document, Mapping):
            rejected.setdefault("invalid_source_document", []).append("")
            continue
        result = validate_external_source_document(document)
        if result["status"] == "ok":
            valid.append(dict(document))
            continue
        reason = str(result["reason"] or "invalid_source_document")
        rejected.setdefault(reason, []).append(str(document.get("source_id") or ""))
    return valid, rejected


def validate_external_unit_selection_v4(batch: Iterable[Mapping[str, Any]], selection: Mapping[str, Any]) -> dict:
    """Validate an ID-only selection response against one exact peer batch."""
    if not isinstance(selection, Mapping) or selection.get("schema_version") != SELECTION_SCHEMA:
        return _result("invalid", "selection_schema")
    if _FORBIDDEN_FIELDS.intersection(selection):
        return _result("invalid", "selection_forbidden_field")
    decisions = selection.get("decisions")
    if not isinstance(decisions, list):
        return _result("invalid", "selection_decisions")
    expected = {str(unit.get("unit_id") or "") for unit in batch}
    received, groups = set(), {}
    for row in decisions:
        if not isinstance(row, Mapping) or set(row).difference({"unit_id", "action", "group_id"}):
            return _result("invalid", "selection_shape")
        unit_id, action, group_id = str(row.get("unit_id") or ""), row.get("action"), str(row.get("group_id") or "")
        if not unit_id or action not in {"keep", "skip"} or unit_id in received:
            return _result("invalid", "selection_decision")
        received.add(unit_id)
        if group_id and action == "keep":
            groups.setdefault(group_id, []).append(unit_id)
    if received != expected:
        return _result("invalid", "selection_coverage")
    units = {str(unit.get("unit_id") or ""): unit for unit in batch}
    for unit_ids in groups.values():
        members = [units[unit_id] for unit_id in unit_ids]
        source_ids = {str(unit.get("source_id") or "") for unit in members}
        block_ids = {str(unit.get("block_id") or "") for unit in members}
        ordinals = sorted(int(unit.get("unit_ordinal") or 0) for unit in members)
        if len(source_ids) != 1 or len(block_ids) != 1 or ordinals != list(range(ordinals[0], ordinals[0] + len(ordinals))):
            return _result("invalid", "selection_invalid_group")
    return _result("ok", "")


def read_external_argument_pack_v4(pack: Mapping[str, Any], *, expected_stock_name: str) -> dict:
    """Read one v4 pack through the sole strict validation path."""
    if not isinstance(pack, Mapping) or pack.get("schema_version") != ARGUMENT_PACK_SCHEMA:
        return _result("invalid", "schema_version")
    if pack.get("status") != "ready" or pack.get("stock_name") != expected_stock_name:
        return _result("invalid", "pack_identity")
    diagnostics = pack.get("diagnostics")
    if isinstance(diagnostics, Mapping) and diagnostics.get("rejected_source_documents"):
        return _result("invalid", "source_input_degraded")
    documents = pack.get("source_documents")
    if not isinstance(documents, list):
        return _result("invalid", "source_documents")
    by_source = {}
    for document in documents:
        status = validate_external_source_document(document)
        if status["status"] != "ok":
            return _result("invalid", status["reason"])
        source_id = str(document.get("source_id") or "")
        if not source_id or source_id in by_source:
            return _result("invalid", "source_identity")
        by_source[source_id] = document
    citations = _normalized_citations(pack.get("citations"))
    seen_units, referenced_citations = set(), set()
    for card in pack.get("cards") or []:
        if not isinstance(card, Mapping) or card.get("schema_version") != ARGUMENT_CARD_SCHEMA:
            return _result("invalid", "card_schema")
        if _FORBIDDEN_CARD_FIELDS.intersection(card):
            return _result("invalid", "forbidden_card_field")
        scope = str(card.get("entity_scope") or "")
        target_entity = str(card.get("target_entity") or "")
        if scope not in {"target", "target_with_peer_context", "peer_or_industry"}:
            return _result("invalid", "card_scope")
        if (scope == "peer_or_industry" and target_entity) or (
            scope != "peer_or_industry" and target_entity != expected_stock_name
        ):
            return _result("invalid", "card_target_entity")
        families = card.get("coverage_families")
        if not isinstance(families, list) or card.get("primary_family") not in families:
            return _result("invalid", "card_family")
        units = card.get("evidence_units")
        if not isinstance(units, list) or not units:
            return _result("invalid", "card_units")
        origins, card_refs, checked_units = set(), [], []
        for unit in units:
            unit_id = str(unit.get("unit_id") or "") if isinstance(unit, Mapping) else ""
            if not unit_id or unit_id in seen_units:
                return _result("invalid", "duplicate_unit")
            seen_units.add(unit_id)
            document = by_source.get(str(unit.get("source_id") or ""))
            if document is None:
                return _result("invalid", "unit_source")
            evidence = validate_external_evidence_unit(unit, document)
            if evidence["status"] != "ok":
                return evidence
            scope = validate_scope_provenance(unit, document, stock_name=expected_stock_name)
            if scope["status"] != "ok":
                return scope
            refs = unit.get("citation_refs") or []
            if not refs or any(ref not in citations for ref in refs):
                return _result("invalid", "unit_citations")
            if any(
                citation.get("source_id") != document.get("source_id")
                or citation.get("source_ref") != document.get("source_ref")
                or citation.get("source_document_hash") != document.get("document_hash")
                for ref in refs
                for citation in (citations[ref],)
            ):
                return _result("invalid", "citation_identity")
            card_refs.extend(refs)
            referenced_citations.update(refs)
            checked_units.append(unit)
            origins.add(str((unit.get("scope_provenance") or {}).get("origin") or ""))
        if (
            len({str(unit.get("source_id") or "") for unit in checked_units}) != 1
            or len({str(unit.get("block_id") or "") for unit in checked_units}) != 1
        ):
            return _result("invalid", "card_units")
        ordinals = [int(unit.get("unit_ordinal") or 0) for unit in checked_units]
        if ordinals != list(range(ordinals[0], ordinals[0] + len(ordinals))):
            return _result("invalid", "card_units")
        expected_families = _family_union(checked_units)
        if (
            card.get("coverage_families") != expected_families
            or card.get("primary_family") != _primary_family(checked_units[0])
            or any(_primary_family(unit) != card.get("primary_family") for unit in checked_units)
        ):
            return _result("invalid", "card_family")
        expected_refs = list(dict.fromkeys(card_refs))
        expected_identity = [[citations[ref]["source_ref"], citations[ref]["source_id"]] for ref in expected_refs]
        if card.get("citation_refs") != expected_refs or card.get("source_identity") != expected_identity:
            return _result("invalid", "card_citations")
        if card.get("entity_scope") != _card_scope(origins):
            return _result("invalid", "card_scope")
    if set(citations) != referenced_citations:
        return _result("invalid", "unused_citations")
    if "narrative_plan" in pack:
        narrative = validate_external_narrative_plan(pack, pack["narrative_plan"])
        if narrative["status"] != "ok":
            return _result("invalid", f"narrative_{narrative['reason']}")
    return _result("ok", "")


def _selected_peer_cards(stock_name: str, batch: list[dict], decisions: Mapping[str, Mapping[str, Any]]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for unit in batch:
        decision = decisions[str(unit["unit_id"])]
        if decision.get("action") != "keep":
            continue
        key = str(decision.get("group_id") or unit["unit_id"])
        groups.setdefault(key, []).append(unit)
    cards = []
    for members in groups.values():
        cards.extend(_cards_from_runs(stock_name, members, lambda _: "peer_or_industry"))
    return cards


def _cards_from_runs(stock_name: str, units: Iterable[Mapping[str, Any]], scope_for: Any) -> list[dict]:
    cards, members, previous = [], [], ()
    for unit in sorted((dict(unit) for unit in units), key=_unit_order):
        scope = str(scope_for(unit))
        key = (str(unit.get("source_id") or ""), str(unit.get("block_id") or ""), scope, _primary_family(unit))
        previous_ordinal = int(members[-1].get("unit_ordinal") or 0) if members else -1
        if members and (key != previous or int(unit.get("unit_ordinal") or 0) != previous_ordinal + 1):
            cards.append(_card(stock_name, members, scope=previous[2]))
            members = []
        members.append(unit)
        previous = key
    if members:
        cards.append(_card(stock_name, members, scope=previous[2]))
    return cards


def _target_unit_scope(unit: Mapping[str, Any]) -> str:
    return "target_with_peer_context" if (unit.get("scope_provenance") or {}).get("origin") == "target_peer_relation" else "target"


def _card(stock_name: str, members: Iterable[Mapping[str, Any]], *, scope: str) -> dict:
    units = [dict(unit) for unit in sorted(members, key=_unit_order)]
    primary = _primary_family(units[0])
    families = _family_union(units)
    token = _hash("|".join(str(unit["unit_id"]) for unit in units))[-16:]
    return {
        "schema_version": ARGUMENT_CARD_SCHEMA,
        "card_id": f"external-card:{token}",
        "argument_key": f"{primary}:{scope}:{token}",
        "entity_scope": scope, "target_entity": stock_name if scope.startswith("target") else "",
        "primary_family": primary, "coverage_families": families,
        "evidence_units": units, "citation_refs": [], "source_identity": [],
    }


def _attach_citations(cards: list[dict], documents: Iterable[Mapping[str, Any]]) -> dict[int, dict]:
    sources = {str(document.get("source_id") or ""): document for document in documents}
    refs, by_source = {}, {}
    for card in cards:
        card_refs = []
        for unit in card["evidence_units"]:
            source_id = str(unit["source_id"])
            ref = by_source.get(source_id)
            if ref is None:
                ref = len(refs) + 1
                source = sources[source_id]
                refs[ref] = _citation_from_document(source)
                by_source[source_id] = ref
            unit["citation_refs"] = [ref]
            card_refs.append(ref)
        card["citation_refs"] = list(dict.fromkeys(card_refs))
        card["source_identity"] = [[refs[ref]["source_ref"], refs[ref]["source_id"]] for ref in card["citation_refs"]]
    return refs


def _citation_from_document(document: Mapping[str, Any]) -> dict:
    return {
        "source": "外部材料精选观察",
        "author": document.get("account", ""),
        "title": document.get("title", "") or "外部观点",
        "url": document.get("source_url", "") or document.get("source_ref", ""),
        "source_ref": document.get("source_ref", ""),
        "source_id": document.get("source_id", ""),
        "source_document_hash": document.get("document_hash", ""),
        "publish_time": document.get("publish_time", ""),
        "source_kind": document.get("source_kind", ""),
        "source_type": "curated_external_analysis_evidence",
        "source_credit": 55,
        "verification_status": "professional_observation",
        "quality_action": "preview_only",
        "synthesis_display_only": True,
        "knowledge_eligible": False,
        "scoring_eligible": False,
        "risk_score_eligible": False,
    }


def _failure_pack(
    status: str, stock_name: str, prepared: Mapping[str, Any], *,
    source_documents: Iterable[Mapping[str, Any]] = (), rejection_reason: str | None = None,
) -> dict:
    diagnostics = dict(prepared.get("diagnostics") or {})
    if rejection_reason:
        diagnostics["rejection_reasons"] = [rejection_reason]
    return {
        "schema_version": ARGUMENT_PACK_SCHEMA,
        "status": status,
        "stock_name": stock_name,
        "validator_version": PACK_VALIDATOR_VERSION,
        "source_documents": list(source_documents),
        "cards": [], "citations": {},
        "diagnostics": diagnostics,
    }


def _primary_family(unit: Mapping[str, Any]) -> str:
    families = set(unit.get("coverage_families") or [])
    return next((family for family in EXTERNAL_FAMILY_ORDER if family in families), "other")


def _family_union(units: Iterable[Mapping[str, Any]]) -> list[str]:
    families = {family for unit in units for family in unit.get("coverage_families") or []}
    return [family for family in EXTERNAL_FAMILY_ORDER if family in families]


def _card_scope(origins: set[str]) -> str:
    if "target_peer_relation" in origins:
        return "target_with_peer_context"
    return "target" if origins.intersection(_TARGET_ORIGINS) else "peer_or_industry"


def _unit_order(unit: Mapping[str, Any]) -> tuple:
    return str(unit.get("source_id") or ""), int(unit.get("block_ordinal") or 0), int(unit.get("unit_ordinal") or 0)


def _normalized(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalized_citations(value: Any) -> dict[int, dict]:
    return {int(key): dict(row) for key, row in (value or {}).items() if str(key).isdigit() and isinstance(row, Mapping)}


def _result(status: str, reason: str) -> dict:
    return {"status": status, "reason": reason}
