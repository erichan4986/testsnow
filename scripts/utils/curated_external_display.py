"""Display-only helpers for curated external deep-analysis material."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

try:
    from .curated_external_display_lint import lint_curated_external_display_text
    from .synthesis_credit import citation_identity
except ImportError:
    from curated_external_display_lint import lint_curated_external_display_text
    from synthesis_credit import citation_identity


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
GENERIC_REASONING_MARKERS = ("外部材料提出该增量变量", "交叉验证")
GENERIC_ASSUMPTION_MARKERS = ("仍属外部观察", "未获官方确认")
GENERIC_COUNTERPOINT_MARKERS = ("下游需求", "交付节奏", "可能失效")
GENERIC_VERIFICATION_MARKERS = ("跟踪后续公告", "订单或行业数据", "验证该论断")
_FOREIGN_COMPANY_SUFFIXES = ("股份", "科技", "电子", "微电", "智能", "集团")
_PEER_CONTEXT_TERMS = ("同业", "竞品", "行业", "产业链", "市场")


def build_curated_external_narrative_display(
    narrative_json: str | Path | None,
    *,
    expected_stock_name: str,
) -> dict:
    """Build a 4.4-only display object from cached external narrative JSON."""
    expected_stock_name = str(expected_stock_name or "").strip()
    if not expected_stock_name:
        return _result("missing_stock_identity")
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
    if str(narrative.get("stock_name") or "").strip() != expected_stock_name:
        return _result("stock_identity_mismatch", stats=stats)

    paragraphs = [p for p in narrative.get("paragraphs") or [] if isinstance(p, dict)]
    citations, citation_ref_map = _dedupe_viewpoint_narrative_citations(
        normalize_viewpoint_narrative_citations(narrative.get("citations") or {})
    )
    paragraphs = hydrate_viewpoint_narrative_citation_refs(
        paragraphs, citations, citation_ref_map,
    )
    reasoning_cards = normalize_viewpoint_narrative_reasoning_cards(
        narrative.get("reasoning_cards") or [],
        citations, citation_ref_map,
    )
    paragraphs, reasoning_cards, citations = _filter_external_entity_scope(
        paragraphs, reasoning_cards, citations, expected_stock_name,
    )
    if not citations or not (paragraphs or reasoning_cards):
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
        "_items_count": len(paragraphs) + len(reasoning_cards),
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


def classify_external_source_title(title: Any, expected_stock_name: str) -> str:
    """Classify only source-title scope; ambiguous titles remain Preview-safe."""
    normalized_title = _compact_text(title)
    expected = _compact_text(expected_stock_name)
    if expected and expected in normalized_title:
        return "target"
    prefix = re.split(r"[:：]", normalized_title, maxsplit=1)[0]
    if re.match(r"^.{1,24}[（(]\d{6}[）)]", normalized_title):
        return "foreign_company"
    if ":" in normalized_title or "：" in normalized_title:
        if prefix.endswith(_FOREIGN_COMPANY_SUFFIXES):
            return "foreign_company"
    return "ambiguous"


def resolve_viewpoint_claim_id(claim_ref: Any, claim_ids: set[str]) -> str | None:
    """Resolve exact claim IDs, allowing only an unambiguous suffix fallback."""
    claim_ref = str(claim_ref or "").strip()
    if not claim_ref:
        return None
    if claim_ref in claim_ids:
        return claim_ref
    suffix = claim_ref.rsplit(":", 1)[-1]
    matches = [
        claim_id for claim_id in claim_ids
        if claim_id.rsplit(":", 1)[-1] == suffix
    ]
    return matches[0] if len(matches) == 1 else None


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


def _dedupe_viewpoint_narrative_citations(
    citations: Dict[int, dict],
) -> tuple[Dict[int, dict], Dict[int, int]]:
    canonical_by_identity: Dict[tuple, int] = {}
    deduped: Dict[int, dict] = {}
    ref_map: Dict[int, int] = {}
    for ref_id in sorted(citations):
        meta = citations[ref_id]
        identity = citation_identity(meta, fallback_ref=ref_id)
        canonical_ref = canonical_by_identity.get(identity) if identity[:1] == ("url",) else None
        if canonical_ref is None:
            canonical_ref = ref_id
            if identity[:1] == ("url",):
                canonical_by_identity[identity] = canonical_ref
            deduped[canonical_ref] = dict(meta)
        ref_map[ref_id] = canonical_ref
        claim_ids = deduped[canonical_ref].setdefault("claim_ids", [])
        for claim_id in _citation_claim_ids(meta):
            if claim_id not in claim_ids:
                claim_ids.append(claim_id)
    return deduped, ref_map


def _citation_claim_ids(meta: dict) -> list[str]:
    claim_ids = meta.get("claim_ids") or []
    if not isinstance(claim_ids, list):
        claim_ids = [claim_ids]
    claim_id = str(meta.get("claim_id") or "").strip()
    return [str(value).strip() for value in [*claim_ids, claim_id] if str(value).strip()]


def _compact_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def _remap_citation_refs(
    refs: list,
    citations: Dict[int, dict],
    citation_ref_map: Dict[int, int] | None,
) -> list[int]:
    remapped = []
    for ref in refs or []:
        try:
            ref_id = int(ref)
        except (TypeError, ValueError):
            continue
        ref_id = (citation_ref_map or {}).get(ref_id, ref_id)
        if ref_id in citations and ref_id not in remapped:
            remapped.append(ref_id)
    return remapped


def hydrate_viewpoint_narrative_citation_refs(
    paragraphs: list,
    citations: Dict[int, dict],
    citation_ref_map: Dict[int, int] | None = None,
) -> list:
    """Fill missing paragraph citation refs from claim_refs and citation metadata."""
    claim_to_ref: Dict[str, int] = {}
    for ref_id, meta in citations.items():
        for claim_id in _citation_claim_ids(meta):
            claim_to_ref[claim_id] = ref_id
    claim_ids = set(claim_to_ref)

    hydrated = []
    for paragraph in paragraphs:
        if not isinstance(paragraph, dict):
            continue
        existing_refs = paragraph.get("citation_refs") or []
        if existing_refs:
            refs = _remap_citation_refs(existing_refs, citations, citation_ref_map)
            if refs:
                hydrated.append({**paragraph, "citation_refs": refs})
                continue
        refs = []
        seen = set()
        for claim_ref in paragraph.get("claim_refs") or []:
            claim_id = resolve_viewpoint_claim_id(claim_ref, claim_ids)
            ref_id = claim_to_ref.get(claim_id or "")
            if ref_id is None or ref_id in seen:
                continue
            seen.add(ref_id)
            refs.append(ref_id)
        hydrated.append({**paragraph, "citation_refs": refs} if refs or existing_refs else paragraph)
    return hydrated


def normalize_viewpoint_narrative_reasoning_cards(
    cards: list,
    citations: Dict[int, dict],
    citation_ref_map: Dict[int, int] | None = None,
) -> list:
    claim_to_ref = {
        claim_id: ref_id
        for ref_id, meta in citations.items()
        for claim_id in _citation_claim_ids(meta)
    }
    claim_ids = set(claim_to_ref)
    normalized = []
    for card in cards or []:
        if not isinstance(card, dict):
            continue
        claim_id = resolve_viewpoint_claim_id(card.get("claim_id"), claim_ids)
        if not claim_id:
            continue
        refs = _remap_citation_refs(card.get("citation_refs") or [], citations, citation_ref_map)
        if not refs and claim_id in claim_to_ref:
            refs = [claim_to_ref[claim_id]]
        if not refs:
            continue

        excerpt, truncated = truncate_curated_source_excerpt(card.get("source_excerpt", ""))
        normalized.append({
            "claim_id": claim_id,
            "heading": str(card.get("heading") or "").strip(),
            "display_topic": str(card.get("display_topic") or ""),
            "claim": str(card.get("claim") or "").strip(),
            "source_excerpt": excerpt,
            "excerpt_truncated": bool(card.get("excerpt_truncated")) or truncated,
            "reasoning_steps": _reasoning_steps_from_card(card),
            "numbers_used": clean_string_list(card.get("numbers_used")),
            "assumptions": _assumptions_from_card(card),
            "counterpoints": _counterpoints_from_card(card),
            "verification_need": _verification_need_from_card(card),
            "citation_refs": refs,
        })
    return normalized[:8]


def _reasoning_steps_from_card(card: dict) -> list:
    values = clean_string_list(card.get("reasoning_steps"))
    if values and not _is_generic_values(values, GENERIC_REASONING_MARKERS):
        return values
    claim = str(card.get("claim") or "").strip()
    numbers = clean_string_list(card.get("numbers_used"))
    steps = []
    if claim:
        steps.append(f"先识别外部观点指向的变量：{_short_clause(claim)}")
    if numbers:
        steps.append(f"再核对关键数字口径：{'、'.join(numbers[:3])}是否能与正式披露或同行口径对应")
    else:
        steps.append("再用公告、调研纪要或财报拆分交叉验证该观点是否有正式证据")
    return steps[:4]


def _assumptions_from_card(card: dict) -> list:
    values = clean_string_list(card.get("assumptions"))
    if values and not _is_generic_values(values, GENERIC_ASSUMPTION_MARKERS):
        return values
    claim = _short_clause(str(card.get("claim") or ""))
    if claim:
        return [f"{claim}后续能被订单、财报拆分或正式披露验证"]
    return []


def _counterpoints_from_card(card: dict) -> list:
    values = clean_string_list(card.get("counterpoints"))
    if values and not _is_generic_values(values, GENERIC_COUNTERPOINT_MARKERS):
        return values
    text = f"{card.get('claim', '')} {card.get('source_excerpt', '')}"
    if any(term in text for term in ("估值", "PE", "市值", "股价")):
        return ["若盈利修复低于外部假设，估值分歧可能向保守情景收敛"]
    if any(term in text for term in ("G60", "千帆", "卫星", "星座")):
        return ["若后续无中标、订单或星座配套披露，该线索只能保留为待验证观察"]
    if any(term in text for term in ("唯一", "第一", "份额", "市占率")):
        return ["若缺少第三方口径或正式披露，排名/唯一性表述需降权"]
    if any(term in text for term in ("亏损", "下降", "承压", "价格")):
        return ["若价格或毛利率趋势改善，该负面线索可能减弱"]
    return ["若正式公告或财报拆分无法验证，该观点需降权"]


def _verification_need_from_card(card: dict) -> str:
    value = str(card.get("verification_need") or "").strip()
    if value and not _is_generic_text(value, GENERIC_VERIFICATION_MARKERS):
        return value
    claim = _short_clause(str(card.get("claim") or ""))
    if claim:
        return f"跟踪与“{claim}”相关的公告、订单、调研纪要和财报拆分。"
    return ""


def _is_generic_values(values: list, markers: tuple[str, ...]) -> bool:
    return any(_is_generic_text(value, markers) for value in values)


def _is_generic_text(value: str, markers: tuple[str, ...]) -> bool:
    text = str(value or "").strip()
    return bool(text) and all(marker in text for marker in markers)


def _short_clause(text: str, limit: int = 42) -> str:
    clause = str(text or "").strip().split("；", 1)[0].split("。", 1)[0]
    return clause[:limit]


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


def _filter_external_entity_scope(
    paragraphs: list,
    cards: list,
    citations: Dict[int, dict],
    expected_stock_name: str,
) -> tuple[list, list, Dict[int, dict]]:
    refs_by_claim: Dict[str, set[int]] = {}
    for ref_id, meta in citations.items():
        for claim_id in _citation_claim_ids(meta):
            refs_by_claim.setdefault(claim_id, set()).add(ref_id)
    claim_ids = set(refs_by_claim)

    def item_claim_ids(item: dict) -> set[str]:
        raw_refs = [item.get("claim_id"), *(item.get("claim_refs") or [])]
        return {
            claim_id for ref in raw_refs
            if (claim_id := resolve_viewpoint_claim_id(ref, claim_ids))
        }

    rejected = set()
    for item in [*cards, *paragraphs]:
        texts = [str(item.get(key) or "") for key in ("claim", "source_excerpt", "display_topic", "heading", "text")]
        for claim_id in item_claim_ids(item):
            titles = [citations[ref].get("title") for ref in refs_by_claim[claim_id]]
            if is_foreign_only_target_claim(texts, titles, expected_stock_name):
                rejected.add(claim_id)

    filtered_paragraphs = [
        _with_peer_context(item, citations, expected_stock_name)
        for item in paragraphs if not item_claim_ids(item) & rejected
    ]
    filtered_cards = [
        _with_peer_context(item, citations, expected_stock_name)
        for item in cards if not item_claim_ids(item) & rejected
    ]

    used_refs = {
        ref
        for item in [*filtered_paragraphs, *filtered_cards]
        for ref in item.get("citation_refs") or []
        if ref in citations
    }
    kept_citations = {ref: meta for ref, meta in citations.items() if ref in used_refs}
    return filtered_paragraphs, filtered_cards, kept_citations


def is_foreign_only_target_claim(
    texts: list[str],
    source_titles: list[Any],
    expected_stock_name: str,
) -> bool:
    target = _compact_text(expected_stock_name)
    evidence = "".join(_compact_text(text) for text in texts)
    return bool(target and target in evidence and source_titles and all(
        classify_external_source_title(title, expected_stock_name) == "foreign_company"
        for title in source_titles
    ))


def filter_external_viewpoint_claims(
    claims: list[dict], expected_stock_name: str,
) -> tuple[list[dict], list[str]]:
    """Drop foreign-only target facts and label standalone peer context."""
    kept, rejected, target = [], [], _compact_text(expected_stock_name)
    for claim in claims:
        texts = [str(claim.get(key) or "") for key in ("claim", "source_quote", "heading", "topic")]
        title = claim.get("source_title") or claim.get("title") or ""
        if is_foreign_only_target_claim(texts, [title], expected_stock_name):
            claim_id = str(claim.get("claim_id") or "")
            if claim_id:
                rejected.append(claim_id)
            continue
        if target not in _compact_text(" ".join(texts)) and classify_external_source_title(
            title, expected_stock_name,
        ) == "foreign_company":
            claim = {**claim, "entity_context": "peer_or_industry_context", "heading": "同业/行业背景（Preview）"}
        kept.append(claim)
    return kept, rejected


def _with_peer_context(item: dict, citations: Dict[int, dict], expected_stock_name: str) -> dict:
    text = " ".join(str(item.get(key) or "") for key in ("heading", "claim", "source_excerpt", "text"))
    refs = [ref for ref in item.get("citation_refs") or [] if ref in citations]
    has_target = _compact_text(expected_stock_name) in _compact_text(text)
    foreign_only = bool(refs) and all(
        classify_external_source_title(citations[ref].get("title"), expected_stock_name)
        == "foreign_company"
        for ref in refs
    )
    if not has_target and (foreign_only or any(term in text for term in _PEER_CONTEXT_TERMS)):
        return {**item, "entity_context": "peer_or_industry_context", "heading": "同业/行业背景（Preview）"}
    return item


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
