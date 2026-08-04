"""Report display adapter for one validated v4 external-material pack."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

try:
    from .curated_external_display_lint import (
        CURATED_EXTERNAL_QUOTE_HEADER,
        lint_curated_external_display_text,
    )
    from .external_narrative_plan import (
        deterministic_narrative_plan,
        validate_external_narrative_plan,
    )
    from .external_pack import read_external_argument_pack_v4
except ImportError:
    from curated_external_display_lint import CURATED_EXTERNAL_QUOTE_HEADER, lint_curated_external_display_text
    from external_narrative_plan import deterministic_narrative_plan, validate_external_narrative_plan
    from external_pack import read_external_argument_pack_v4


SYNTHESIS_KEYS = (
    "industry_logic", "fundamentals", "valuation_debate", "funding_sentiment", "events_catalysts",
)


def build_curated_external_argument_display(
    pack_json: str | Path | Mapping | None,
    *,
    expected_stock_name: str,
) -> dict:
    """Adapt a single strict v4 pack into the established report display envelope."""
    stock = str(expected_stock_name or "").strip()
    if not stock:
        return _result("missing_stock_identity")
    pack, status = _load_pack(pack_json)
    if pack is None:
        return _result(status)
    reader = read_external_argument_pack_v4(pack, expected_stock_name=stock)
    if reader["status"] != "ok":
        return _result(reader["status"], stats=pack.get("diagnostics") or {})
    cards = _display_cards(pack.get("cards") or [])
    if not cards:
        return _result("empty", stats=pack.get("diagnostics") or {})
    plan = _narrative_plan(pack, cards)
    if plan is None:
        return _result("invalid", stats=pack.get("diagnostics") or {})
    citations = _citations(pack.get("citations"))
    target_text = [_render_card(card) for card in cards if card.get("entity_scope") != "peer_or_industry"]
    peer_text = [_render_card(card) for card in cards if card.get("entity_scope") == "peer_or_industry"]
    industry_blocks = [CURATED_EXTERNAL_QUOTE_HEADER, *target_text]
    if peer_text:
        industry_blocks.extend(["**同业/行业背景（Preview）**", *peer_text])
    display = {
        "industry_logic": "\n\n".join(industry_blocks),
        "fundamentals": "",
        "valuation_debate": "",
        "funding_sentiment": "",
        "events_catalysts": "",
        "core_facts": [],
        "citations": citations,
        "_curated_external_argument_cards": cards,
        "_curated_external_topic_narratives": _narrative_parts(plan, cards),
        "_curated_external_taxonomy_version": "external_argument.v4",
        "_items_count": len(cards),
        "_sources": list(citations.values()),
    }
    lint = lint_curated_external_display_text(display)
    if not lint.get("ok"):
        return _result("lint_failed", stats=pack.get("diagnostics") or {}, lint=lint)
    return _result(
        "ok",
        stats=pack.get("diagnostics") or {},
        lint=lint,
        display=display,
        synthesis_text=flatten_synthesis_text(display),
    )


def _load_pack(value: str | Path | Mapping | None) -> tuple[dict | None, str]:
    if value is None:
        return None, "missing_config"
    if isinstance(value, Mapping):
        return dict(value), "ok"
    path = Path(value)
    if not path.exists():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "invalid"
    return (dict(payload), "ok") if isinstance(payload, Mapping) else (None, "invalid")


def _display_cards(cards: list) -> list[dict]:
    return sorted(
        (dict(card) for card in cards if isinstance(card, Mapping)),
        key=lambda card: (card.get("entity_scope") == "peer_or_industry", str(card.get("card_id") or "")),
    )


def _narrative_plan(pack: Mapping, cards: list[dict]) -> dict | None:
    plan = pack.get("narrative_plan") or deterministic_narrative_plan({"cards": cards})
    return dict(plan) if validate_external_narrative_plan({"cards": cards}, plan)["status"] == "ok" else None


def _narrative_parts(plan: Mapping, cards: list[dict]) -> list[dict]:
    by_id = {str(card.get("card_id") or ""): card for card in cards}
    groups = []
    for group in plan.get("groups") or []:
        parts = []
        for card_id in group.get("card_ids") or []:
            card = by_id.get(str(card_id))
            if card is None:
                continue
            for index, unit in enumerate(card.get("evidence_units") or []):
                if not isinstance(unit, Mapping) or not str(unit.get("text") or "").strip():
                    continue
                parts.append({
                    "argument_key": str(card.get("argument_key") or ""),
                    "unit_id": str(unit.get("unit_id") or ""),
                    "quote": str(unit.get("text") or "").strip(),
                    "relation": "first" if not parts and index == 0 else "continuation",
                })
        if parts:
            groups.append({
                "scope_bucket": str(group.get("scope_bucket") or ""),
                "primary_family": str(group.get("primary_family") or ""),
                "parts": parts,
            })
    return groups


def _citations(value: object) -> dict[int, dict]:
    return {
        int(key): dict(item)
        for key, item in (value or {}).items()
        if str(key).isdigit() and isinstance(item, Mapping)
    }


def _render_card(card: Mapping) -> str:
    return "\n".join(
        f"> {_append_refs_to_exact_source(str(unit.get('text') or '').strip(), unit.get('citation_refs') or [])}"
        for unit in card.get("evidence_units") or []
        if isinstance(unit, Mapping) and str(unit.get("text") or "").strip()
    )


def _append_refs_to_exact_source(text: str, refs: list) -> str:
    suffix = "".join(f"[^{ref}]" for ref in dict.fromkeys(int(ref) for ref in refs if str(ref).isdigit()))
    return f"{text}{suffix}"


def attach_refs_to_sentence(text: str, refs: list) -> str:
    unique = list(dict.fromkeys(int(ref) for ref in refs if str(ref).isdigit()))
    suffix, value = "".join(f"[^{ref}]" for ref in unique), str(text or "").strip()
    if not suffix:
        return value
    return f"{value[:-1]}{suffix}{value[-1]}" if value.endswith(("。", "；", ";", "！", "？")) else f"{value}{suffix}"


def flatten_synthesis_text(synthesis: Mapping) -> str:
    return "\n".join(str(synthesis.get(key, "")) for key in SYNTHESIS_KEYS if synthesis.get(key))


def _result(
    status: str,
    *,
    stats: dict | None = None,
    lint: dict | None = None,
    display: dict | None = None,
    synthesis_text: str = "",
) -> dict:
    return {
        "status": status,
        "stats": stats or {},
        "lint": lint or {},
        "display": display,
        "synthesis_text": synthesis_text,
    }
