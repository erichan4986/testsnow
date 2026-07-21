"""Display-only projection for the canonical external argument pack."""

from __future__ import annotations

from pathlib import Path

try:
    from .curated_external_argument_cards import read_external_argument_pack
    from .curated_external_display_lint import (
        CURATED_EXTERNAL_QUOTE_HEADER, lint_curated_external_display_text,
    )
except ImportError:
    from curated_external_argument_cards import read_external_argument_pack
    from curated_external_display_lint import (
        CURATED_EXTERNAL_QUOTE_HEADER, lint_curated_external_display_text,
    )


SYNTHESIS_KEYS = ("industry_logic", "fundamentals", "valuation_debate", "funding_sentiment", "events_catalysts")


def build_curated_external_argument_display(pack_json: str | Path | None, *, expected_stock_name: str) -> dict:
    """Project stored v3 evidence exactly; report time never reads source caches."""
    stock = str(expected_stock_name or "").strip()
    if not stock:
        return _result("missing_stock_identity")
    result = read_external_argument_pack(pack_json, expected_stock_name=stock)
    if result["status"] != "ok":
        return _result(result["status"], stats=result.get("stats") or {})
    cards = sorted(
        result["cards"],
        key=lambda card: str(card.get("entity_scope") or "") == "peer_or_industry",
    )
    citations = result["citations"]
    target_text = [_render_card(card) for card in cards if card.get("entity_scope") != "peer_or_industry"]
    peer_text = [_render_card(card) for card in cards if card.get("entity_scope") == "peer_or_industry"]
    industry_blocks = [CURATED_EXTERNAL_QUOTE_HEADER, *target_text]
    if peer_text:
        industry_blocks.extend(["**同业/行业背景（Preview）**", *peer_text])
    display = {
        "industry_logic": "\n\n".join(industry_blocks),
        "fundamentals": "", "valuation_debate": "", "funding_sentiment": "", "events_catalysts": "",
        "core_facts": [], "citations": citations, "_curated_external_argument_cards": cards,
        "_curated_external_taxonomy_version": "external_argument.v3", "_items_count": len(cards),
        "_sources": list(citations.values()),
    }
    if result.get("topic_narratives"):
        display["_curated_external_topic_narratives"] = result["topic_narratives"]
    lint = lint_curated_external_display_text(display)
    if not lint.get("ok"):
        return _result("lint_failed", stats=result.get("stats") or {}, lint=lint)
    return _result("ok", stats=result.get("stats") or {}, lint=lint, display=display,
                   synthesis_text=flatten_synthesis_text(display))


def _render_card(card: dict) -> str:
    return "\n".join(
        f"> {_append_refs_to_exact_source(str(unit.get('text') or '').strip(), unit.get('citation_refs') or [])}"
        for unit in card.get("evidence_units") or [] if str(unit.get("text") or "").strip()
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


def flatten_synthesis_text(synthesis: dict) -> str:
    return "\n".join(str(synthesis.get(key, "")) for key in SYNTHESIS_KEYS if synthesis.get(key))


def _result(status: str, *, stats: dict | None = None, lint: dict | None = None,
            display: dict | None = None, synthesis_text: str = "") -> dict:
    return {"status": status, "stats": stats or {}, "lint": lint or {}, "display": display,
            "synthesis_text": synthesis_text}
