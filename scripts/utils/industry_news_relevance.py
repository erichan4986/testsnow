"""Deterministic relevance classification for industry news.

The helper is intentionally small and pure.  It decides which report sections
may see an industry-news item before LLM synthesis, so generic sector headlines
cannot be promoted into company catalysts by prompt wording alone.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


HIGH_CONFIDENCE_THRESHOLD = 0.70
CAUTIOUS_CONFIDENCE_THRESHOLD = 0.40


def classify_industry_news_relevance(
    *,
    stock_name: str,
    title: str,
    content: str = "",
    stock_config: Dict[str, Any] | None = None,
    matched_keywords: Iterable[str] | None = None,
) -> Dict[str, Any]:
    """Classify whether industry news can enter 4.3 events/catalysts.

    Return shape is JSON-serializable and can be stored on ``SynthesisItem.extra``.
    """
    stock_config = stock_config or {}
    matched_keywords = [str(keyword) for keyword in (matched_keywords or []) if str(keyword).strip()]
    text = _normalize_text(f"{title} {content}")
    stock_name_text = _normalize_text(stock_name)

    if stock_name_text and stock_name_text in text:
        return _result(
            relevance_class="company_event",
            confidence=0.95,
            allowed_sections=["4.1", "4.2", "4.3"],
            chain={
                "chain_id": "company_direct",
                "confidence": 0.95,
                "hops": [
                    {
                        "id": "company_mention",
                        "canonical_statement": f"新闻直接提及{stock_name}",
                        "evidence": stock_name,
                        "evidence_type": "news_text",
                    }
                ],
            },
        )

    best_chain = _best_relevance_chain(text, stock_config)
    if best_chain:
        confidence = float(best_chain.get("confidence", 0.0))
        if confidence >= HIGH_CONFIDENCE_THRESHOLD:
            return _result(
                relevance_class="industry_chain_relevant",
                confidence=confidence,
                allowed_sections=["4.1", "4.3"],
                chain=best_chain,
                rendering_guardrails=_guardrails_for_confidence(confidence),
            )
        if confidence >= CAUTIOUS_CONFIDENCE_THRESHOLD:
            return _result(
                relevance_class="industry_chain_relevant",
                confidence=confidence,
                allowed_sections=["4.1"],
                chain=best_chain,
                rendering_guardrails=_guardrails_for_confidence(confidence),
            )

    if _looks_like_sector_background(text, matched_keywords):
        return _result(
            relevance_class="sector_background",
            confidence=0.25,
            allowed_sections=["4.1"],
            chain={
                "chain_id": "sector_background",
                "confidence": 0.25,
                "hops": [],
            },
        )

    return _result(
        relevance_class="noise",
        confidence=0.0,
        allowed_sections=[],
        chain={"chain_id": "noise", "confidence": 0.0, "hops": []},
    )


def build_industry_relevance_manifest(items: Iterable[Any]) -> Dict[str, Any]:
    """Build a sidecar manifest for post-render chain validation."""
    chains: List[Dict[str, Any]] = []
    seen_chain_ids = set()

    for item in items:
        extra = getattr(item, "extra", {}) or {}
        allowed_sections = extra.get("allowed_sections") or []
        if "4.3" not in {str(section) for section in allowed_sections}:
            continue
        chain = extra.get("relevance_chain") or {}
        chain_id = str(chain.get("chain_id") or "").strip()
        if not chain_id or chain_id in seen_chain_ids:
            continue
        hops = chain.get("hops") or []
        allowed_terms = [
            str(hop.get("canonical_statement") or "").strip()
            for hop in hops
            if str(hop.get("canonical_statement") or "").strip()
        ]
        chains.append(
            {
                "chain_id": chain_id,
                "confidence": chain.get("confidence", extra.get("confidence", 0.0)),
                "canonical_text": " -> ".join(allowed_terms),
                "allowed_terms": allowed_terms,
                "source_title": getattr(item, "title", ""),
                "source_url": getattr(item, "url", ""),
            }
        )
        seen_chain_ids.add(chain_id)

    return {
        "schema": "industry_relevance_manifest.v1",
        "events_catalysts_chains": chains,
    }


def _best_relevance_chain(text: str, stock_config: Dict[str, Any]) -> Dict[str, Any] | None:
    relevance_config = stock_config.get("industry_relevance", stock_config) or {}
    rules = relevance_config.get("chain_rules") or []
    if not isinstance(rules, list):
        return None

    best: Dict[str, Any] | None = None
    for rule in rules:
        chain = _build_chain_from_rule(text, rule, relevance_config)
        if not chain:
            continue
        if not best or float(chain["confidence"]) > float(best["confidence"]):
            best = chain
    return best


def _build_chain_from_rule(text: str, rule: Dict[str, Any], relevance_config: Dict[str, Any]) -> Dict[str, Any] | None:
    hops = rule.get("hops") or []
    if not hops:
        return None

    products = _normalize_list(relevance_config.get("products"))
    target_product = _normalize_text(rule.get("target_product", ""))
    rendered_hops: List[Dict[str, Any]] = []
    required_news_hops = 0
    supported_required_news_hops = 0
    news_supported_hops = 0

    for hop in hops:
        keywords = _normalize_list(hop.get("keywords"))
        statement = str(hop.get("statement") or hop.get("canonical_statement") or hop.get("id") or "").strip()
        evidence = _first_text_match(text, keywords)
        evidence_type = "news_text" if evidence else ""

        if not evidence and _hop_supported_by_config(hop, products, target_product):
            evidence = str(hop.get("target_product") or rule.get("target_product") or statement)
            evidence_type = "stock_config"

        if hop.get("requires_news_support"):
            required_news_hops += 1
            if evidence_type == "news_text":
                supported_required_news_hops += 1

        if evidence_type == "news_text":
            news_supported_hops += 1

        rendered_hops.append(
            {
                "id": str(hop.get("id") or f"hop_{len(rendered_hops) + 1}"),
                "canonical_statement": statement,
                "evidence": evidence or "",
                "evidence_type": evidence_type or "missing",
                "aliases": keywords,
            }
        )

    if required_news_hops and supported_required_news_hops < required_news_hops:
        return {
            "chain_id": str(rule.get("chain_id") or "industry_chain"),
            "confidence": 0.35,
            "hops": rendered_hops,
        }

    product_supported = bool(target_product and target_product in products)
    confidence = 0.25
    if required_news_hops:
        confidence += 0.35 * (supported_required_news_hops / required_news_hops)
    if news_supported_hops >= 2:
        confidence += 0.20
    elif news_supported_hops == 1:
        confidence += 0.08
    if product_supported:
        confidence += 0.15

    confidence = min(round(confidence, 2), 0.95)
    return {
        "chain_id": str(rule.get("chain_id") or "industry_chain"),
        "confidence": confidence,
        "hops": rendered_hops,
    }


def _guardrails_for_confidence(confidence: float) -> Dict[str, Any]:
    if confidence >= HIGH_CONFIDENCE_THRESHOLD:
        return {
            "requires_chain_match": True,
            "required_tone": "cautious",
            "forbidden_tone": ["确认受益", "确定催化", "已经传导"],
        }
    return {
        "requires_chain_match": True,
        "required_tone": "watch_variable_only",
        "forbidden_tone": ["确认受益", "确定催化", "已经传导", "直接受益"],
    }


def _result(
    *,
    relevance_class: str,
    confidence: float,
    allowed_sections: List[str],
    chain: Dict[str, Any],
    rendering_guardrails: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "relevance_class": relevance_class,
        "confidence": round(float(confidence), 2),
        "allowed_sections": allowed_sections,
        "relevance_chain": chain,
        "rendering_guardrails": rendering_guardrails or {},
    }


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "")


def _normalize_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        values = [values] if values else []
    return [_normalize_text(value) for value in values if str(value or "").strip()]


def _first_text_match(text: str, keywords: List[str]) -> str:
    for keyword in keywords:
        if keyword and keyword in text:
            return keyword
    return ""


def _hop_supported_by_config(hop: Dict[str, Any], products: List[str], target_product: str) -> bool:
    keywords = _normalize_list(hop.get("keywords"))
    if target_product and target_product in keywords and target_product in products:
        return True
    return any(keyword in products for keyword in keywords)


def _looks_like_sector_background(text: str, matched_keywords: List[str]) -> bool:
    sector_terms = [
        "半导体",
        "芯片",
        "存储",
        "晶圆",
        "设备",
        "光模块",
        "ai",
        "机器人",
        "板块",
        "行业",
        "产业",
    ]
    normalized_keywords = [_normalize_text(keyword) for keyword in matched_keywords]
    return any(term in text for term in sector_terms) or bool(normalized_keywords)
