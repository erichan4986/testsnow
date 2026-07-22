"""Validated ID-only paragraph ordering for external-material display."""

from __future__ import annotations

from collections.abc import Mapping

NARRATIVE_PLAN_SCHEMA = "curated_external_narrative_plan.v1"
_GROUP_FIELDS = {"scope_bucket", "primary_family", "card_ids"}


def deterministic_narrative_plan(pack: Mapping) -> dict:
    """Group canonical cards without generating prose or semantic relations."""
    groups: dict[tuple[str, str], list[str]] = {}
    for card in pack.get("cards") or []:
        if not isinstance(card, Mapping):
            continue
        key = (_scope_bucket(card.get("entity_scope")), str(card.get("primary_family") or ""))
        card_id = str(card.get("card_id") or "")
        if key[1] and card_id:
            groups.setdefault(key, []).append(card_id)
    return {
        "schema_version": NARRATIVE_PLAN_SCHEMA,
        "groups": [
            {"scope_bucket": scope, "primary_family": family, "card_ids": ids}
            for (scope, family), ids in groups.items()
        ],
    }


def validate_external_narrative_plan(pack: Mapping, plan: Mapping) -> dict:
    """Reject any planner payload that can introduce prose or unsupported semantics."""
    if not isinstance(plan, Mapping) or plan.get("schema_version") != NARRATIVE_PLAN_SCHEMA:
        return _result("invalid", "plan_schema")
    groups = plan.get("groups")
    if not isinstance(groups, list):
        return _result("invalid", "plan_groups")
    cards = {str(card.get("card_id") or ""): card for card in pack.get("cards") or [] if isinstance(card, Mapping)}
    expected = set(cards)
    received = []
    for group in groups:
        if not isinstance(group, Mapping) or set(group) != _GROUP_FIELDS:
            return _result("invalid", "plan_group_fields")
        scope, family, card_ids = group.get("scope_bucket"), group.get("primary_family"), group.get("card_ids")
        if scope not in {"target", "peer_or_industry"} or not isinstance(family, str) or not isinstance(card_ids, list) or not card_ids:
            return _result("invalid", "plan_group_shape")
        for card_id in card_ids:
            card = cards.get(str(card_id))
            if card is None or _scope_bucket(card.get("entity_scope")) != scope or card.get("primary_family") != family:
                return _result("invalid", "plan_card_reference")
            received.append(str(card_id))
    return _result("ok", "") if set(received) == expected and len(received) == len(expected) else _result("invalid", "plan_coverage")


def _scope_bucket(value: object) -> str:
    return "peer_or_industry" if value == "peer_or_industry" else "target"


def _result(status: str, reason: str) -> dict:
    return {"status": status, "reason": reason}
