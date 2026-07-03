"""Display-only helpers for curated external deep-analysis material."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

try:
    from .curated_external_display_lint import lint_curated_external_display_text
except ImportError:
    from curated_external_display_lint import lint_curated_external_display_text


SYNTHESIS_KEYS = [
    "industry_logic",
    "fundamentals",
    "valuation_debate",
    "funding_sentiment",
    "events_catalysts",
]

NARRATIVE_SOURCE_TYPES = {
    "curated_external_analysis_evidence",
    "xueqiu_column_observation",
    "xueqiu_comment_observation",
    "xueqiu_selected_observation",
    "zhihu_selected_observation",
    "wechat_selected_observation",
    "wechat_column_observation",
}

NARRATIVE_VERIFICATION_STATUSES = {
    "professional_observation",
    "tentative_unverified",
}

SOURCE_EXCERPT_MAX_CHARS = 200


def build_curated_external_narrative_display(narrative_json: str | Path | None) -> dict:
    """Build a 4.4-only display object from cached external narrative JSON."""
    if not narrative_json:
        return _result(
            "missing_config",
            stats={"rejection_reasons": ["curated_external_viewpoint_narrative_json not set"]},
        )

    try:
        narrative = json.loads(Path(narrative_json).read_text(encoding="utf-8"))
    except Exception as exc:
        return _result("reader_error", stats={"rejection_reasons": [str(exc)]})

    status = str(narrative.get("status") or "")
    stats = narrative.get("stats") or {}
    if status != "ok":
        return _result(status, stats=stats)

    paragraphs = [p for p in narrative.get("paragraphs") or [] if isinstance(p, dict)]
    citations = normalize_viewpoint_narrative_citations(narrative.get("citations") or {})
    paragraphs = hydrate_viewpoint_narrative_citation_refs(paragraphs, citations)
    reasoning_cards = normalize_viewpoint_narrative_reasoning_cards(
        narrative.get("reasoning_cards") or [],
        citations,
    )
    if not paragraphs or not citations:
        return _result("empty", stats=stats)

    display = {
        "industry_logic": flatten_viewpoint_narrative_paragraphs(paragraphs),
        "fundamentals": "",
        "valuation_debate": "",
        "funding_sentiment": "",
        "events_catalysts": "",
        "core_facts": [],
        "citations": citations,
        "_curated_external_narrative": True,
        "_curated_external_narrative_paragraphs": paragraphs,
        "_curated_external_reasoning_cards": reasoning_cards,
        "_curated_external_taxonomy_version": "external_viewpoint.v1",
        "_items_count": len(paragraphs),
        "_sources": list(citations.values()),
    }
    lint = lint_curated_external_display_text(display)
    if not lint.get("ok"):
        return _result("lint_failed", stats=stats, lint=lint)

    return _result(
        "ok",
        stats=stats,
        lint=lint,
        display=display,
        synthesis_text=flatten_synthesis_text(display),
    )


def normalize_viewpoint_narrative_citations(citations: Dict[Any, Any]) -> Dict[int, dict]:
    normalized = {}
    for key, value in (citations or {}).items():
        try:
            ref_id = int(key)
        except (TypeError, ValueError):
            continue
        if not isinstance(value, dict):
            continue
        if (
            value.get("source_type") in NARRATIVE_SOURCE_TYPES
            and value.get("verification_status") in NARRATIVE_VERIFICATION_STATUSES
        ):
            normalized[ref_id] = value
    return normalized


def hydrate_viewpoint_narrative_citation_refs(
    paragraphs: list,
    citations: Dict[int, dict],
) -> list:
    """Fill missing paragraph citation refs from claim_refs and citation metadata."""
    claim_to_ref: Dict[str, int] = {}
    suffix_to_ref: Dict[str, int] = {}
    for ref_id, meta in citations.items():
        claim_id = str(meta.get("claim_id") or "").strip()
        if not claim_id:
            continue
        claim_to_ref[claim_id] = ref_id
        suffix_to_ref[claim_id.rsplit(":", 1)[-1]] = ref_id

    hydrated = []
    for paragraph in paragraphs:
        if not isinstance(paragraph, dict):
            continue
        existing_refs = paragraph.get("citation_refs") or []
        if existing_refs:
            hydrated.append(paragraph)
            continue
        refs = []
        seen = set()
        for claim_ref in paragraph.get("claim_refs") or []:
            claim_key = str(claim_ref or "").strip()
            ref_id = claim_to_ref.get(claim_key)
            if ref_id is None:
                ref_id = suffix_to_ref.get(claim_key.rsplit(":", 1)[-1])
            if ref_id is None or ref_id in seen:
                continue
            seen.add(ref_id)
            refs.append(ref_id)
        hydrated.append({**paragraph, "citation_refs": refs} if refs else paragraph)
    return hydrated


def normalize_viewpoint_narrative_reasoning_cards(
    cards: list,
    citations: Dict[int, dict],
) -> list:
    claim_to_ref = {
        str(meta.get("claim_id") or "").strip(): ref_id
        for ref_id, meta in citations.items()
        if str(meta.get("claim_id") or "").strip()
    }
    normalized = []
    for card in cards or []:
        if not isinstance(card, dict):
            continue
        claim_id = str(card.get("claim_id") or "").strip()
        refs = []
        for ref in card.get("citation_refs") or []:
            try:
                ref_id = int(ref)
            except (TypeError, ValueError):
                continue
            if ref_id in citations and ref_id not in refs:
                refs.append(ref_id)
        if not refs and claim_id in claim_to_ref:
            refs = [claim_to_ref[claim_id]]
        if not refs:
            continue

        excerpt, truncated = truncate_curated_source_excerpt(card.get("source_excerpt", ""))
        normalized.append({
            "claim_id": claim_id,
            "display_topic": str(card.get("display_topic") or ""),
            "claim": str(card.get("claim") or "").strip(),
            "source_excerpt": excerpt,
            "excerpt_truncated": bool(card.get("excerpt_truncated")) or truncated,
            "reasoning_steps": clean_string_list(card.get("reasoning_steps")),
            "numbers_used": clean_string_list(card.get("numbers_used")),
            "assumptions": clean_string_list(card.get("assumptions")),
            "counterpoints": clean_string_list(card.get("counterpoints")),
            "verification_need": str(card.get("verification_need") or "").strip(),
            "citation_refs": refs,
        })
    return normalized[:8]


def clean_string_list(value: Any) -> list:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:4]


def truncate_curated_source_excerpt(value: Any) -> tuple[str, bool]:
    text = str(value or "").strip()
    if len(text) <= SOURCE_EXCERPT_MAX_CHARS:
        return text, False
    prefix_len = max(0, SOURCE_EXCERPT_MAX_CHARS - 3)
    return text[:prefix_len].rstrip("，。；;、") + "...", True


def flatten_viewpoint_narrative_paragraphs(paragraphs: list) -> str:
    parts = []
    for paragraph in paragraphs:
        heading = str(paragraph.get("heading") or "").strip()
        text = str(paragraph.get("text") or "").strip()
        refs = paragraph.get("citation_refs") or []
        rendered = attach_refs_to_sentence(text, refs)
        if heading:
            parts.append(f"{heading}：{rendered}")
        elif rendered:
            parts.append(rendered)
    return "\n\n".join(parts)


def attach_refs_to_sentence(text: str, refs: list) -> str:
    unique_refs = []
    seen = set()
    for ref in refs:
        if not str(ref).isdigit():
            continue
        ref_id = int(ref)
        if ref_id in seen:
            continue
        seen.add(ref_id)
        unique_refs.append(ref_id)
    ref_text = "".join(f"[^{ref_id}]" for ref_id in unique_refs)
    stripped = str(text or "").strip()
    if not ref_text:
        return stripped
    if stripped.endswith(("。", "；", ";", "！", "？")):
        return f"{stripped[:-1]}{ref_text}{stripped[-1]}"
    return f"{stripped}{ref_text}"


def flatten_synthesis_text(synthesis: dict) -> str:
    return "\n".join(str(synthesis.get(k, "")) for k in SYNTHESIS_KEYS if synthesis.get(k))


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
