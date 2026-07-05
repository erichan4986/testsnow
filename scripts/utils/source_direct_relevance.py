"""Direct-only canonical relevance helper for deep-analysis synthesis.

This module is intentionally deterministic.  It decides whether a source item
has a direct company/product/peer relationship that may enter canonical 4.1-4.3
synthesis.  Multi-hop industry chains stay out of canonical synthesis until a
separate chain validator can prove every hop.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

try:
    from .source_adapter import SynthesisItem
except ImportError:
    from source_adapter import SynthesisItem


GENERIC_EXPOSURE_TERMS = {
    "半导体",
    "芯片",
    "国产替代",
    "AI",
    "汽车电子",
    "集成电路",
    "行业",
    "产业链",
    "电子",
}

COMPANY_DIRECT_PLATFORMS = {
    "公告",
    "定期报告全文",
    "定期报告叙事卡片",
}

OPERATING_VARIABLE_TERMS = (
    "供应商",
    "客户",
    "产能",
    "供需",
    "库存",
    "存货",
    "订单",
    "价格",
    "交期",
    "采购",
    "备货",
    "交付",
    "产量",
)


def classify_direct_relevance(
    item: SynthesisItem,
    stock_name: str,
    stock_config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Classify a synthesis item for direct-only canonical visibility."""
    stock_config = stock_config or {}
    text = _item_text(item)
    normalized_text = _normalize(text)

    if item.source_platform in COMPANY_DIRECT_PLATFORMS:
        return _result("company_direct", ["4.1", "4.2", "4.3"], [])

    if _has_explicit_unrelated_theme(normalized_text):
        return _result(
            "sector_background",
            [],
            [],
            blocked_reason="sector_background_no_direct_exposure",
        )

    product_terms = _direct_product_terms(stock_config)
    matched_products = _matched_terms(product_terms, text)
    if matched_products:
        return _result("direct_product", ["4.1", "4.2"], matched_products)

    peer_terms = _list_values(stock_config.get("competitors"))
    matched_peers = _matched_terms(peer_terms, text)
    if matched_peers:
        return _result("direct_peer", ["4.1", "4.2"], matched_peers)

    if stock_name and _normalize(stock_name) in normalized_text and not _has_negated_direct_relation(normalized_text):
        return _result("company_direct", ["4.1", "4.2", "4.3"], [stock_name])

    return _result(
        "sector_background",
        [],
        [],
        blocked_reason="sector_background_no_direct_exposure",
    )


def filter_items_for_canonical_theme(
    theme_key: str,
    items: Iterable[SynthesisItem],
    stock_name: str,
    stock_config: Dict[str, Any] | None = None,
) -> List[SynthesisItem]:
    """Filter items for a deep-analysis theme using direct-only rules."""
    section = _theme_section(theme_key)
    if section is None:
        return list(items)

    filtered: List[SynthesisItem] = []
    for item in items:
        classification = classify_direct_relevance(item, stock_name, stock_config)
        allowed = set(classification.get("allowed_canonical_sections") or [])
        if section in allowed:
            _attach_relevance(item, classification)
            filtered.append(item)
    return filtered


def _theme_section(theme_key: str) -> str | None:
    if theme_key == "industry_logic":
        return "4.1"
    if theme_key in {"fundamentals", "valuation_debate"}:
        return "4.2"
    if theme_key in {"funding_sentiment", "events_catalysts"}:
        return "4.3"
    return None


def _result(
    relevance_class: str,
    allowed_sections: List[str],
    matched_terms: List[str],
    blocked_reason: str = "",
) -> Dict[str, Any]:
    return {
        "canonical_relevance_class": relevance_class,
        "allowed_canonical_sections": allowed_sections,
        "matched_terms": matched_terms,
        "blocked_reason": blocked_reason,
    }


def _attach_relevance(item: SynthesisItem, classification: Dict[str, Any]) -> None:
    extra = item.extra or {}
    extra.setdefault("canonical_relevance_class", classification["canonical_relevance_class"])
    extra.setdefault("allowed_canonical_sections", classification["allowed_canonical_sections"])
    if classification.get("matched_terms"):
        extra.setdefault("direct_relevance_terms", classification["matched_terms"])
    item.extra = extra


def _direct_product_terms(stock_config: Dict[str, Any]) -> List[str]:
    configured = _list_values(stock_config.get("product_exposure_terms"))
    if configured:
        return _strip_generic_terms(configured)
    return _strip_generic_terms(_list_values(stock_config.get("keywords")))


def _strip_generic_terms(terms: Iterable[str]) -> List[str]:
    return [
        term for term in terms
        if term and _normalize(term) not in {_normalize(generic) for generic in GENERIC_EXPOSURE_TERMS}
    ]


def _matched_terms(terms: Iterable[str], text: str) -> List[str]:
    normalized_text = _normalize(text)
    matched = []
    for term in terms:
        if _normalize(term) and _normalize(term) in normalized_text:
            matched.append(term)
    return matched


def _has_negated_direct_relation(normalized_text: str) -> bool:
    return any(
        phrase in normalized_text
        for phrase in ("不直接涉及", "无直接关系", "不属于", "不同于", "并非")
    )


def _has_explicit_unrelated_theme(normalized_text: str) -> bool:
    return "mlcc" in normalized_text and _has_negated_direct_relation(normalized_text)


def _list_values(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _item_text(item: SynthesisItem) -> str:
    return " ".join([
        str(item.title or ""),
        str(item.content or ""),
        str(item.author or ""),
    ])


def _normalize(text: str) -> str:
    return str(text or "").replace(" ", "").replace("\u3000", "").lower()
