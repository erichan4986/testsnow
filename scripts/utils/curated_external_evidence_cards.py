"""Preview-only evidence cards for curated external synthesis display items.

This module is Phase 1 only: it reads local JSON/JSONL display items, creates
deterministic evidence cards plus excerpt packs, and never connects them to the
report pipeline, Knowledge, scoring, risk, or final recommendations.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


CARDS_SCHEMA_VERSION = "curated_external_evidence_cards.v1"
CARD_SCHEMA_VERSION = "periodic_report_narrative_evidence_card.v1"
SOURCE_TYPE = "curated_external_analysis_evidence"
DEFAULT_MAX_EXCERPT_CHARS = 1200


def normalized_hash(text: str) -> str:
    normalized = _normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_curated_external_evidence_cards(
    synthesis_items_jsonl_path: str | Path,
    *,
    stock_name: str = "",
    max_excerpt_chars: int = DEFAULT_MAX_EXCERPT_CHARS,
) -> Dict[str, Any]:
    raw_items = _read_json_or_jsonl(synthesis_items_jsonl_path)
    safe_items = [item for item in raw_items if _is_safe_display_item(item)]
    unique_items, deduped_sources = _dedupe_items(safe_items)

    cards: List[Dict[str, Any]] = []
    excerpt_packs: List[Dict[str, Any]] = []
    for index, item in enumerate(unique_items):
        card, pack = _build_card_and_pack(item, stock_name=stock_name, index=index, max_excerpt_chars=max_excerpt_chars)
        cards.append(card)
        excerpt_packs.append(pack)

    total_excerpt_chars = sum(
        len(excerpt.get("text", ""))
        for pack in excerpt_packs
        for excerpt in pack.get("excerpts", [])
    )
    return {
        "schema_version": CARDS_SCHEMA_VERSION,
        "status": "ok" if cards else "empty",
        "stock_name": stock_name,
        "cards": cards,
        "excerpt_packs": excerpt_packs,
        "counts": dict(Counter(card.get("topic", "") for card in cards)),
        "deduped_sources": deduped_sources,
        "excerpt_budget": {
            "max_excerpt_chars": max_excerpt_chars,
            "total_excerpt_chars": total_excerpt_chars,
            "cards_count": len(cards),
            "excerpt_packs_count": len(excerpt_packs),
        },
        "wrote_knowledge": False,
        "connected_synthesis": False,
    }


def build_curated_external_evidence_cards_markdown(summary: Dict[str, Any]) -> str:
    lines = [
        "# Curated External Evidence Cards Preview",
        "",
        "> Phase 1 preview-only evidence cards. Cards and excerpts are display-only; they do not write Knowledge, connect canonical synthesis, or enter scoring/risk/final recommendation.",
        "",
        "## Summary",
        "",
        f"- status: `{summary.get('status', '')}`",
        f"- stock_name: `{summary.get('stock_name', '')}`",
        f"- cards: `{len(summary.get('cards', []) or [])}`",
        f"- excerpt_packs: `{len(summary.get('excerpt_packs', []) or [])}`",
    ]
    budget = summary.get("excerpt_budget") or {}
    lines.extend([
        f"- max_excerpt_chars: `{budget.get('max_excerpt_chars', '')}`",
        f"- total_excerpt_chars: `{budget.get('total_excerpt_chars', '')}`",
        "",
    ])

    cards = summary.get("cards", []) or []
    packs = {pack.get("card_id"): pack for pack in summary.get("excerpt_packs", []) or []}
    if cards:
        lines.extend(["## Cards", ""])
        for idx, card in enumerate(cards, 1):
            lines.extend(_render_card_lines(idx, card, packs.get(card.get("card_id")) or {}))

    deduped = summary.get("deduped_sources", []) or []
    if deduped:
        lines.extend(["## Deduped Sources", ""])
        for record in deduped:
            lines.append(
                f"- reason: `{record.get('reason', '')}` | kept: `{record.get('kept_source_ref', '')}` | duplicate: `{record.get('duplicate_source_ref', '')}`"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _build_card_and_pack(
    item: Dict[str, Any],
    *,
    stock_name: str,
    index: int,
    max_excerpt_chars: int,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    topic = str(item.get("topic") or "other_observation")
    title = _clean_text(item.get("title") or item.get("source_ref") or "curated external material")
    source_ref = _canonical_source_ref(item)
    source_refs = _sorted_unique([source_ref, *[str(ref) for ref in item.get("source_refs", []) if ref]])
    source_content = _clean_text(item.get("content") or title)
    source_excerpt = _deterministic_excerpt(source_content, max_excerpt_chars=max_excerpt_chars)
    source_excerpt_hash = normalized_hash(source_excerpt)
    source_block_hash = normalized_hash(source_content)
    card_id = _card_id(topic=topic, source_ref=source_ref, index=index)
    evidence_refs = [source_ref]

    card = {
        "schema_version": CARD_SCHEMA_VERSION,
        "source_type": SOURCE_TYPE,
        "card_id": card_id,
        "stock_name": stock_name,
        "card_type": topic,
        "topic": topic,
        "title": title,
        "source_ref": source_ref,
        "source_refs": source_refs,
        "source_kind": str(item.get("source_kind") or ""),
        "evidence_refs": evidence_refs,
        "source_excerpt": source_excerpt,
        "source_excerpt_hash": source_excerpt_hash,
        "source_block_hash": source_block_hash,
        "keywords": _keywords_for_item(item),
        "confidence": 65,
        "source_credit": _source_credit(item),
        "verification_status": str(item.get("verification_status") or "professional_observation"),
        "knowledge_eligible": False,
        "synthesis_eligible": True,
        "synthesis_display_only": True,
        "scoring_eligible": False,
        "risk_score_eligible": False,
        "quality_action": "preview_only",
    }
    excerpt = {
        "excerpt_id": f"{card_id}:excerpt:0",
        "text": source_excerpt,
        "source_excerpt_hash": source_excerpt_hash,
        "char_count": len(source_excerpt),
        "normalized_substring_verified": _normalize_text(source_excerpt) in _normalize_text(source_content),
    }
    pack = {
        "pack_id": f"{card_id}:pack",
        "card_id": card_id,
        "source_ref": source_ref,
        "source_refs": source_refs,
        "source_content_hash": source_block_hash,
        "source_content_chars": len(source_content),
        "excerpts": [excerpt],
    }
    return card, pack


def _is_safe_display_item(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("quality_action") != "preview_only":
        return False
    if item.get("synthesis_display_only") is not True:
        return False
    if item.get("synthesis_eligible") is not True:
        return False
    for key in ("knowledge_eligible", "scoring_eligible", "risk_score_eligible"):
        if bool(item.get(key)):
            return False
    return True


def _dedupe_items(items: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    unique: List[Dict[str, Any]] = []
    deduped: List[Dict[str, Any]] = []
    seen_urls: Dict[str, Dict[str, Any]] = {}
    seen_content: Dict[str, Dict[str, Any]] = {}

    for item in items:
        canonical_url = _canonical_url(str(item.get("url") or item.get("source_ref") or ""))
        content_key = normalized_hash(item.get("content") or item.get("title") or "")
        existing = None
        reason = ""
        if canonical_url and canonical_url in seen_urls:
            existing = seen_urls[canonical_url]
            reason = "canonical_url"
        elif content_key in seen_content:
            existing = seen_content[content_key]
            reason = "content_fingerprint"

        if existing is not None:
            _merge_source_refs(existing, item)
            deduped.append({
                "reason": reason,
                "kept_source_ref": _canonical_source_ref(existing),
                "duplicate_source_ref": str(item.get("source_ref") or item.get("url") or ""),
            })
            continue

        copied = dict(item)
        _merge_source_refs(copied, item)
        unique.append(copied)
        if canonical_url:
            seen_urls[canonical_url] = copied
        seen_content[content_key] = copied

    return unique, deduped


def _merge_source_refs(target: Dict[str, Any], item: Dict[str, Any]) -> None:
    refs = list(target.get("source_refs") or [])
    for key in ("source_ref", "url", "path"):
        value = str(item.get(key) or "").strip()
        if value:
            refs.append(value)
    target["source_refs"] = _sorted_unique(refs)


def _canonical_source_ref(item: Dict[str, Any]) -> str:
    url = str(item.get("url") or "").strip()
    if url:
        return _canonical_url(url)
    source_ref = str(item.get("source_ref") or "").strip()
    if source_ref.startswith("http://") or source_ref.startswith("https://"):
        return _canonical_url(source_ref)
    if source_ref:
        return source_ref
    path = str(item.get("path") or "").strip()
    if path:
        return path
    return f"{item.get('source_kind', 'curated')}:{normalized_hash(item.get('title') or '')[:12]}"


def _canonical_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return ""
    parsed = urlsplit(url)
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
    ]
    query = urlencode(filtered_query, doseq=True)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), query, ""))


def _deterministic_excerpt(text: str, *, max_excerpt_chars: int) -> str:
    source = _clean_text(text)
    if max_excerpt_chars <= 0:
        return ""
    if len(source) <= max_excerpt_chars:
        return source
    return source[:max_excerpt_chars].rstrip()


def _source_credit(item: Dict[str, Any]) -> int:
    source_kind = str(item.get("source_kind") or "")
    if source_kind.startswith("wechat_"):
        return 55
    if source_kind in {"curated_preview", "jina_url", "local_file"}:
        return 60
    return 50


def _keywords_for_item(item: Dict[str, Any]) -> List[str]:
    terms = [
        str(item.get("topic") or ""),
        str(item.get("source_kind") or ""),
        str(item.get("account") or ""),
    ]
    return [term for term in _sorted_unique(terms) if term]


def _card_id(*, topic: str, source_ref: str, index: int) -> str:
    digest = normalized_hash(source_ref)[:16]
    return f"curated:{topic}:{digest}:{index}"


def _read_json_or_jsonl(path: str | Path) -> List[Any]:
    source = Path(path)
    if not source.exists():
        return []
    text = source.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("[") or text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("items", []) if isinstance(payload.get("items"), list) else [payload]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _render_card_lines(index: int, card: Dict[str, Any], pack: Dict[str, Any]) -> List[str]:
    lines = [
        f"### {index}. {card.get('title', '')}",
        "",
        f"- card_id: `{card.get('card_id', '')}`",
        f"- topic: `{card.get('topic', '')}`",
        f"- source_ref: `{card.get('source_ref', '')}`",
        f"- source_excerpt_hash: `{card.get('source_excerpt_hash', '')}`",
        f"- synthesis_display_only: `{str(bool(card.get('synthesis_display_only'))).lower()}`",
        f"- knowledge_eligible: `{str(bool(card.get('knowledge_eligible'))).lower()}`",
        f"- scoring_eligible: `{str(bool(card.get('scoring_eligible'))).lower()}`",
        f"- risk_score_eligible: `{str(bool(card.get('risk_score_eligible'))).lower()}`",
    ]
    excerpts = pack.get("excerpts", []) if isinstance(pack, dict) else []
    if excerpts:
        excerpt = excerpts[0]
        lines.append(f"- normalized_substring_verified: `{str(bool(excerpt.get('normalized_substring_verified'))).lower()}`")
        lines.extend(["", "> " + str(excerpt.get("text", "")).replace("\n", "\n> "), ""])
    else:
        lines.append("")
    return lines


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _clean_text(text: Any) -> str:
    return _normalize_text(str(text or ""))


def _sorted_unique(values: List[str]) -> List[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})
