"""Deterministic display-only argument cards for curated external evidence."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Mapping

try:
    from .synthesis_credit import citation_identity
except ImportError:
    from synthesis_credit import citation_identity


ARGUMENT_CARD_SCHEMA = "curated_external_argument_card.v2"
_SAFE_SOURCE_TYPES = {
    "curated_external_analysis_evidence", "xueqiu_column_observation",
    "xueqiu_comment_observation", "xueqiu_selected_observation",
    "zhihu_selected_observation", "wechat_selected_observation",
    "wechat_column_observation",
}
_COMPANY_SUFFIXES = ("股份", "科技", "电子", "微电", "智能", "集团")
_PEER_TERMS = ("同业", "竞品", "对比", "三巨头", "行业", "竞争格局")
_STRONG_TERMS = ("唯一", "第一", "首家", "确认", "已落地", "锁定", "市占率", "份额")
_GENERIC_DELTAS = ("baseline未明确提及", "baseline未提及该外部观察", "新增外部观察")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_MODEL_RE = re.compile(r"(?i)(?<![A-Za-z0-9])(?:[A-Za-z]{1,8}\d[A-Za-z0-9.]{0,12}|\d+(?:\.\d+)?[A-Za-z]{1,8})(?![A-Za-z0-9])")
_TOPIC_RULES = (
    ("capacity_delivery", ("供应链", "交付", "产能", "物料", "原材料", "预付款")),
    ("demand_customer", ("客户", "需求", "订单", "资本开支", "capex")),
    ("technology_product", ("技术", "产品", "fpga", "cpo", "npo", "xpo", "硅光", "芯片")),
    ("financial_quality", ("财务", "营收", "利润", "毛利", "费用", "现金流")),
    ("valuation_expectation", ("估值", "市值", "股价", "pe", "预期差", "情景")),
    ("competitive_landscape", ("竞争", "同业", "格局", "份额", "市占率")),
    ("policy_geopolitics", ("政策", "制裁", "管制", "清单", "地缘")),
    ("commercialization", ("商业化", "量产", "认证", "验证", "导入", "定点")),
)
_TOPIC_ALIASES = {
    "supply_delivery_capacity": "capacity_delivery", "order_capacity_delivery": "capacity_delivery",
    "technology_route": "technology_product", "product_route": "technology_product",
    "financial_quality": "financial_quality", "competition_commercialization": "competitive_landscape",
    "market_expectation": "valuation_expectation", "risk_rumor_rebuttal": "policy_geopolitics",
}


def build_external_argument_cards(
    *, stock_name: str, digest_claims: Iterable[Mapping[str, Any]] = (),
    narrative_cards: Iterable[Mapping[str, Any]] = (), citations: Mapping[Any, Any] | None = None,
) -> dict:
    """Adapt safe digest/narrative inputs through one admission and dedupe path."""
    stock, citation_map = _clean(stock_name), _normalized_citations(citations or {})
    identity_refs = {citation_identity(meta, fallback_ref=ref): ref for ref, meta in citation_map.items()}
    candidates, rejected, digest_ids, merged = [], {}, set(), 0
    for source in digest_claims or ():
        if not isinstance(source, Mapping):
            continue
        claim_id = _clean(source.get("claim_id"))
        digest_ids.add(claim_id) if claim_id else None
        candidate = _candidate(source, "digest", citation_map, identity_refs)
        candidates.append(candidate) if candidate else _bump(rejected, "invalid_digest_claim")
    for source in narrative_cards or ():
        if not isinstance(source, Mapping):
            continue
        if _clean(source.get("claim_id")) in digest_ids:
            merged += 1
            continue
        candidate = _candidate(source, "narrative", citation_map, identity_refs)
        candidates.append(candidate) if candidate else _bump(rejected, "invalid_narrative_card")

    accepted = []
    for candidate in candidates:
        card, reason = _build_card(stock, candidate)
        accepted.append(card) if card else _bump(rejected, reason or "invalid_card")
    deduped, duplicate_count = {}, 0
    for card in accepted:
        previous = deduped.get(card["argument_key"])
        if previous is not None:
            duplicate_count += 1
        if previous is None or _card_quality(card) > _card_quality(previous):
            deduped[card["argument_key"]] = card
    cards = list(deduped.values())
    used_refs = {ref for card in cards for ref in card["citation_refs"]}
    return {
        "cards": cards,
        "citations": {ref: meta for ref, meta in citation_map.items() if ref in used_refs},
        "stats": {"input_count": len(candidates) + merged, "accepted_count": len(cards),
                  "merged_input_count": merged, "deduped_count": duplicate_count,
                  "rejected_by_reason": rejected},
    }


def _candidate(source: Mapping[str, Any], kind: str, citations: dict, identity_refs: dict) -> dict | None:
    if kind == "digest":
        if not _safe_digest(source):
            return None
        meta, evidence, status = _citation_from_claim(source), _clean(source.get("source_quote")), "source_quote_verified"
        identity = citation_identity(meta, fallback_ref=source.get("claim_id"))
        ref = identity_refs.get(identity)
        if ref is None:
            ref = max(citations, default=0) + 1
            citations[ref], identity_refs[identity] = meta, ref
        refs, metas = [ref], [meta]
    else:
        refs = _safe_refs(source.get("citation_refs"), citations)
        evidence, status = _clean(source.get("source_excerpt_full") or source.get("source_excerpt")), "cached_excerpt"
        if not refs or not evidence:
            return None
        metas = [citations[ref] for ref in refs]
    claim = _clean(source.get("claim"))
    if not claim:
        return None
    return {
        "claim_id": _clean(source.get("claim_id")), "claim": claim, "evidence": evidence,
        "evidence_status": status, "topic": _clean(source.get("display_topic") or source.get("topic") or source.get("primary_topic")),
        "heading": _clean(source.get("heading")), "incremental_delta": _clean(source.get("why_incremental")),
        "baseline_overlap": _clean(source.get("baseline_overlap") or "none"),
        "citation_refs": refs, "citation_meta": metas,
    }


def _build_card(stock: str, candidate: dict) -> tuple[dict | None, str]:
    claim, evidence = candidate["claim"], candidate["evidence"]
    entity_scope, reason = _entity_scope(stock, claim, evidence, candidate["topic"], candidate["citation_meta"])
    if reason or candidate["baseline_overlap"] == "duplicate" or not _anchors_supported(claim, evidence):
        return None, reason or ("baseline_duplicate" if candidate["baseline_overlap"] == "duplicate" else "unsupported_claim_anchor")
    bounded = _bounded_claim(claim)
    if not bounded:
        return None, "claim_not_bounded"
    topic, refs = _topic_family(candidate["topic"]), list(candidate["citation_refs"])
    delta = candidate["incremental_delta"]
    delta = "" if any(marker in delta for marker in _GENERIC_DELTAS) else delta
    title = candidate["heading"] or candidate["topic"] or "外部待验证变量"
    if entity_scope == "peer_or_industry":
        title = "同业/行业背景（Preview）"
    elif entity_scope == "target_with_peer_context" and not title.endswith("（对比观察）"):
        title += "（对比观察）"
    argument_key = _argument_key(topic, entity_scope, bounded)
    evidence_unit = {
        "text": evidence, "evidence_status": candidate["evidence_status"],
        "source_id": _clean(candidate["citation_meta"][0].get("source_id")),
        "source_quote_hash": _hash(evidence), "citation_refs": refs,
    }
    return {
        "schema_version": ARGUMENT_CARD_SCHEMA, "card_id": f"external-argument:{stock}:{_hash(argument_key)[:16]}",
        "stock_name": stock, "topic_family": topic, "entity_scope": entity_scope,
        "target_entity": stock if entity_scope.startswith("target") else "",
        "mentioned_entities": _mentioned_entities(f"{claim} {evidence}"), "claim": bounded,
        "evidence_units": [evidence_unit], "incremental_delta": delta,
        "baseline_overlap": candidate["baseline_overlap"], "display_title": title,
        "argument_key": argument_key, "citation_refs": refs,
        "source_identity": [list(citation_identity(meta, fallback_ref=ref)) for ref, meta in zip(refs, candidate["citation_meta"])],
        "quality_action": "preview_only", "synthesis_display_only": True, "knowledge_eligible": False,
        "scoring_eligible": False, "risk_score_eligible": False,
        "verification_status": "professional_observation",
        "diagnostics": {"lexical_overlap": _lexical_overlap(claim, evidence)},
    }, ""


def _safe_digest(source: Mapping[str, Any]) -> bool:
    quote = _clean(source.get("source_quote"))
    return bool(
        source.get("schema_version") == "curated_external_viewpoint_claim.v1"
        and source.get("quality_action") == "preview_only" and source.get("knowledge_eligible") is False
        and source.get("synthesis_display_only") is True and source.get("scoring_eligible") is False
        and source.get("risk_score_eligible") is False and source.get("verification_status") == "professional_observation"
        and _clean(source.get("claim")) and quote and _clean(source.get("source_quote_hash")) == _hash(quote)
    )


def _safe_refs(raw_refs: Any, citations: Mapping[int, dict]) -> list[int]:
    refs = []
    for raw in raw_refs or ():
        try:
            ref = int(raw)
        except (TypeError, ValueError):
            continue
        meta = citations.get(ref) or {}
        safe = meta.get("source_type") in _SAFE_SOURCE_TYPES and meta.get("verification_status") in {"professional_observation", "tentative_unverified"}
        if safe and ref not in refs:
            refs.append(ref)
    return refs


def _citation_from_claim(source: Mapping[str, Any]) -> dict:
    return {
        "source": source.get("source_label") or "微信公众号精选观察", "author": source.get("source_account") or "",
        "title": source.get("source_title") or "外部观点", "url": source.get("source_ref") or source.get("source_url") or "",
        "source_id": source.get("source_id") or "", "source_type": "curated_external_analysis_evidence",
        "source_credit": source.get("source_credit", 55), "verification_status": "professional_observation",
        "claim_id": source.get("claim_id") or "", "source_quote_hash": source.get("source_quote_hash") or "",
        "quality_action": "preview_only", "synthesis_display_only": True,
        "scoring_eligible": False, "risk_score_eligible": False,
    }


def _entity_scope(stock: str, claim: str, evidence: str, topic: str, metas: list[dict]) -> tuple[str, str]:
    text, titles = f"{claim} {evidence} {topic}", [_clean(meta.get("title")) for meta in metas]
    target = bool(stock and stock in text)
    scopes = [_title_scope(title, stock) for title in titles]
    others = [entity for entity in _mentioned_entities(text) if entity != stock and not entity.startswith(stock)]
    if target and titles and all(scope == "foreign_company" for scope in scopes):
        return "", "foreign_only_target_claim"
    peer_context = any(term.lower() in text.lower() for term in _PEER_TERMS)
    if target:
        return ("target_with_peer_context" if peer_context or others else "target"), ""
    if stock and "target" in scopes and not others:
        return "target", ""
    if peer_context or others or "foreign_company" in scopes:
        return "peer_or_industry", ""
    if re.match(r"^(?:公司|本公司|该公司|其|该企业)", claim):
        return "", "ambiguous_entity"
    return "peer_or_industry", ""


def _title_scope(title: str, stock: str) -> str:
    compact = re.sub(r"\s+", "", title)
    if stock and stock in compact:
        return "target"
    prefix = re.split(r"[:：]", compact, maxsplit=1)[0]
    foreign = re.match(r"^.{1,24}[（(]\d{6}[）)]", compact) or ((":" in compact or "：" in compact) and prefix.endswith(_COMPANY_SUFFIXES))
    return "foreign_company" if foreign else "ambiguous"


def _topic_family(topic: str) -> str:
    text = _clean(topic).lower()
    if text in _TOPIC_ALIASES:
        return _TOPIC_ALIASES[text]
    return next((family for family, terms in _TOPIC_RULES if any(term.lower() in text for term in terms)), "other")


def _anchors_supported(claim: str, evidence: str) -> bool:
    lower = evidence.lower()
    anchors = [*_NUMBER_RE.findall(claim), *_MODEL_RE.findall(claim)]
    return all(anchor.lower() in lower for anchor in anchors) and all(term not in claim or term in evidence for term in _STRONG_TERMS)


def _bounded_claim(claim: str, limit: int = 96) -> str:
    if len(claim) <= limit:
        return claim
    bounded = ""
    for piece in re.findall(r"[^。！？；]+[。！？；]", claim):
        if len(bounded) + len(piece) > limit:
            break
        bounded += piece
    return bounded.strip()


def _argument_key(topic: str, entity_scope: str, claim: str) -> str:
    normalized = re.sub(r"[\s，,。！？；;：:]", "", claim).lower()
    normalized = re.sub(r"^(?:外部材料|外部观点|外部文章)(?:称|认为|提示|指出)?", "", normalized)
    return f"{topic}:{entity_scope}:{_hash(normalized)[:20]}"


def _card_quality(card: dict) -> tuple[int, int, int]:
    units = card["evidence_units"]
    return int(any(unit["evidence_status"] == "source_quote_verified" for unit in units)), sum(len(unit["text"]) for unit in units), len(card["claim"])


def _mentioned_entities(text: str) -> list[str]:
    entities = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,16}(?:股份|科技|电子|微电|智能|集团)", text)
    return list(dict.fromkeys(entities))


def _lexical_overlap(claim: str, evidence: str) -> int:
    tokens = lambda text: set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9.]+", text.lower()))
    return len(tokens(claim) & tokens(evidence))


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


def _bump(counts: dict, key: str) -> None:
    counts[key] = counts.get(key, 0) + 1
