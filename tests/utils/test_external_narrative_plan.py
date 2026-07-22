"""ID-only narrative plan contracts for v4 external packs."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "utils"))

from external_narrative_plan import (  # type: ignore[import-not-found]
    NARRATIVE_PLAN_SCHEMA,
    deterministic_narrative_plan,
    validate_external_narrative_plan,
)


def _pack() -> dict:
    return {
        "schema_version": "curated_external_argument_pack.v4",
        "cards": [
            {"card_id": "target-tech", "entity_scope": "target", "primary_family": "technology_product"},
            {"card_id": "target-demand", "entity_scope": "target", "primary_family": "demand_customer"},
            {"card_id": "peer-tech", "entity_scope": "peer_or_industry", "primary_family": "technology_product"},
        ],
    }


def test_narrative_plan_rejects_prose_quote_and_relation_fields():
    result = validate_external_narrative_plan(_pack(), {
        "schema_version": NARRATIVE_PLAN_SCHEMA,
        "groups": [{
            "scope_bucket": "target", "primary_family": "technology_product",
            "card_ids": ["target-tech"], "text": "新的事实总结", "relation": "contrast",
        }],
    })

    assert result == {"status": "invalid", "reason": "plan_group_fields"}


def test_deterministic_plan_groups_cards_by_scope_and_family_in_card_order():
    plan = deterministic_narrative_plan(_pack())

    assert plan == {
        "schema_version": NARRATIVE_PLAN_SCHEMA,
        "groups": [
            {"scope_bucket": "target", "primary_family": "technology_product", "card_ids": ["target-tech"]},
            {"scope_bucket": "target", "primary_family": "demand_customer", "card_ids": ["target-demand"]},
            {"scope_bucket": "peer_or_industry", "primary_family": "technology_product", "card_ids": ["peer-tech"]},
        ],
    }
    assert validate_external_narrative_plan(_pack(), plan) == {"status": "ok", "reason": ""}
