"""Load enriched curated external evidence cards as display-only SynthesisItems."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

if __name__.startswith("utils."):
    from .source_adapter import SynthesisItem
else:
    from source_adapter import SynthesisItem


SOURCE_PLATFORM = "微信公众号精选观察"
SOURCE_TYPE = "curated_external_analysis_evidence"
EXPECTED_SUMMARY_SCHEMA = "curated_external_evidence_cards.v1"
EXPECTED_CARD_SCHEMA = "periodic_report_narrative_evidence_card.v1"

TOPIC_PRIORITY = {
    "industry_logic": 0,
    "commercialization": 1,
    "earnings_context": 2,
    "cycle_price": 3,
    "certification_policy": 4,
    "capital_market_context": 5,
}

ELIGIBLE_TOPICS = set(TOPIC_PRIORITY.keys())

_SUBSTANCE_TERMS = [
    "财报",
    "业绩",
    "盈利",
    "亏损",
    "毛利率",
    "现金流",
    "募资用途",
    "研发投入",
    "产能建设",
    "资本开支",
    "上市进展",
    "递表",
    "聆讯",
    "发行",
    "招股书",
    "行业影响",
    "产业链",
    "客户",
    "订单",
    "量产",
]

_NOISY_TITLE_TERMS = [
    "近期的主要市场文章",
    "研报汇总",
    "文章和研报汇总",
    "一周热点",
    "开盘暴涨",
    "盘中暴涨",
    "涨停",
]

_REPORT_METADATA_TERMS = [
    "文中报告节选",
    "具体报告内容及相关风险提示",
    "证券研究报告",
    "报告发布机构",
    "本报告分析师",
    "执业证书编号",
]

_SUBSTANTIVE_VIEW_TERMS = [
    "核心观点",
    "投资要点",
    "预计",
    "同比",
    "收入",
    "营收",
    "利润",
    "毛利",
    "订单",
    "客户",
    "产能",
    "需求",
    "价格",
    "量产",
    "认证",
    "份额",
    "盈利",
    "现金流",
]

_MIN_EXCERPT_LEN = 300
_MIN_CHINESE_CHARS = 80
_MIN_CHINESE_DENSITY = 0.05
_MAX_SOURCE_CREDIT = 65


def load_curated_external_evidence_card_synthesis_items(
    cards_json_path: str | Path,
    *,
    max_items: int = 8,
    min_cards: int = 3,
    min_total_excerpt_chars: int = 1200,
) -> tuple[list[SynthesisItem], dict]:
    """Read enriched curated external evidence cards and convert eligible cards to SynthesisItems.

    Returns a tuple of (items, stats). The returned items are display-only and
    must not enter canonical synthesis, scoring, risk, or Knowledge.
    """
    stats: Dict[str, Any] = {
        "status": "ok",
        "cards_seen": 0,
        "cards_eligible": 0,
        "cards_rejected": 0,
        "total_excerpt_chars": 0,
        "rejection_reasons": [],
    }

    path = Path(cards_json_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        stats["status"] = "read_error"
        stats["rejection_reasons"].append(f"failed to read {path}: {exc}")
        return [], stats

    # Summary-level gate
    summary_errors = _validate_summary(data)
    if summary_errors:
        stats["status"] = "summary_gate_failed"
        stats["rejection_reasons"].extend(summary_errors)
        return [], stats

    cards = data.get("cards") or []
    excerpt_packs_by_card_id = _excerpt_packs_by_card_id(data.get("excerpt_packs") or [])
    stats["cards_seen"] = len(cards)

    eligible_items: List[SynthesisItem] = []
    for card in cards:
        if not isinstance(card, dict):
            stats["cards_rejected"] += 1
            stats["rejection_reasons"].append("non-dict card")
            continue

        card_id = str(card.get("card_id") or "unknown")
        errors = _validate_card(card, excerpt_packs_by_card_id)
        if errors:
            stats["cards_rejected"] += 1
            stats["rejection_reasons"].extend(f"{card_id}: {e}" for e in errors)
            continue

        item = _card_to_synthesis_item(card)
        eligible_items.append(item)

    # Apply max_items before stock-level gate so stats reflect eligibility.
    if len(eligible_items) > max_items:
        dropped = len(eligible_items) - max_items
        eligible_items = eligible_items[:max_items]
        stats["rejection_reasons"].append(f"truncated {dropped} items by max_items={max_items}")

    stats["cards_eligible"] = len(eligible_items)
    stats["total_excerpt_chars"] = _total_source_excerpt_chars(eligible_items)

    # Stock-level gate
    stock_errors = _validate_stock_level(eligible_items, min_cards, min_total_excerpt_chars)
    if stock_errors:
        stats["status"] = "stock_gate_failed"
        stats["rejection_reasons"].extend(stock_errors)
        return [], stats

    _sort_items(eligible_items)
    return eligible_items, stats


def _validate_summary(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if data.get("schema_version") != EXPECTED_SUMMARY_SCHEMA:
        errors.append(f"schema_version != {EXPECTED_SUMMARY_SCHEMA}")
    if data.get("wrote_knowledge") is not False:
        errors.append("wrote_knowledge is not false")
    if data.get("connected_synthesis") is not False:
        errors.append("connected_synthesis is not false")
    if not isinstance(data.get("cards"), list):
        errors.append("cards is not a list")
    if not isinstance(data.get("excerpt_packs"), list):
        errors.append("excerpt_packs is not a list")
    return errors


def _validate_card(card: Dict[str, Any], excerpt_packs_by_card_id: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    errors: List[str] = []

    if card.get("schema_version") != EXPECTED_CARD_SCHEMA:
        errors.append("schema_version mismatch")
    if card.get("source_type") != SOURCE_TYPE:
        errors.append("source_type mismatch")
    if card.get("quality_action") != "preview_only":
        errors.append("quality_action != preview_only")
    if card.get("knowledge_eligible") is not False:
        errors.append("knowledge_eligible is not false")
    if card.get("synthesis_eligible") is not True:
        errors.append("synthesis_eligible is not true")
    if card.get("synthesis_display_only") is not True:
        errors.append("synthesis_display_only is not true")
    if card.get("scoring_eligible") is not False:
        errors.append("scoring_eligible is not false")
    if card.get("risk_score_eligible") is not False:
        errors.append("risk_score_eligible is not false")
    if card.get("verification_status") != "professional_observation":
        errors.append("verification_status mismatch")

    source_credit = card.get("source_credit")
    try:
        if source_credit is None or int(source_credit) > _MAX_SOURCE_CREDIT:
            errors.append(f"source_credit {_safe_int(source_credit)} > {_MAX_SOURCE_CREDIT}")
    except (TypeError, ValueError):
        errors.append("source_credit not numeric")

    source_ref = str(card.get("source_ref") or "")
    if not _is_valid_source_ref(source_ref):
        errors.append("source_ref is not a URL or local path")

    if not _normalized_substring_verified(card, excerpt_packs_by_card_id):
        errors.append("normalized_substring_verified is not true")

    if not _source_excerpt_hash_matches(card):
        errors.append("source_excerpt_hash mismatch")

    topic = str(card.get("topic") or "")
    if topic not in ELIGIBLE_TOPICS:
        if topic == "product_roadmap":
            errors.append("product_roadmap excluded")
        else:
            errors.append(f"topic {topic!r} not eligible")

    excerpt = _normalize_text(str(card.get("source_excerpt") or ""))
    if len(excerpt) < _MIN_EXCERPT_LEN:
        errors.append(f"excerpt length {len(excerpt)} < {_MIN_EXCERPT_LEN}")
    else:
        chinese_count = _count_chinese_chars(excerpt)
        density = chinese_count / len(excerpt) if excerpt else 0.0
        if chinese_count < _MIN_CHINESE_CHARS:
            errors.append(f"chinese chars {chinese_count} < {_MIN_CHINESE_CHARS}")
        elif density < _MIN_CHINESE_DENSITY:
            errors.append(f"chinese density {density:.3f} < {_MIN_CHINESE_DENSITY}")

    if topic == "capital_market_context" and not _has_capital_market_substance(card, excerpt):
        errors.append("capital_market_context lacks substance")

    errors.extend(_validate_content_quality(card, excerpt))

    return errors


def _source_excerpt_hash_matches(card: Dict[str, Any]) -> bool:
    """Return True iff source_excerpt_hash matches the normalized source_excerpt.

    This guards against post-hoc rewriting of the excerpt while leaving the
    original hash in place.
    """
    expected = str(card.get("source_excerpt_hash") or "")
    if not expected:
        return False
    actual = _normalized_hash(str(card.get("source_excerpt") or ""))
    return actual == expected


def _normalized_hash(text: str) -> str:
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()


def _excerpt_packs_by_card_id(excerpt_packs: List[Any]) -> Dict[str, List[Dict[str, Any]]]:
    by_card: Dict[str, List[Dict[str, Any]]] = {}
    for pack in excerpt_packs:
        if not isinstance(pack, dict):
            continue
        card_id = str(pack.get("card_id") or "")
        if not card_id:
            continue
        by_card.setdefault(card_id, []).append(pack)
    return by_card


def _normalized_substring_verified(
    card: Dict[str, Any],
    excerpt_packs_by_card_id: Dict[str, List[Dict[str, Any]]],
) -> bool:
    if card.get("normalized_substring_verified") is True:
        return True

    card_id = str(card.get("card_id") or "")
    expected_hash = str(card.get("source_excerpt_hash") or "")
    for pack in excerpt_packs_by_card_id.get(card_id, []):
        excerpts = pack.get("excerpts") or []
        if not isinstance(excerpts, list):
            continue
        if expected_hash and str(pack.get("combined_source_excerpt_hash") or "") == expected_hash:
            verified_excerpts = [
                excerpt
                for excerpt in excerpts
                if isinstance(excerpt, dict) and excerpt.get("normalized_substring_verified") is True
            ]
            if verified_excerpts and len(verified_excerpts) == len(excerpts):
                return True
        for excerpt in excerpts:
            if not isinstance(excerpt, dict):
                continue
            if expected_hash and str(excerpt.get("source_excerpt_hash") or "") != expected_hash:
                continue
            if excerpt.get("normalized_substring_verified") is True:
                return True
    return False


def _validate_stock_level(
    items: List[SynthesisItem], min_cards: int, min_total_excerpt_chars: int
) -> List[str]:
    errors: List[str] = []
    if len(items) < min_cards:
        errors.append(f"eligible cards {len(items)} < min_cards {min_cards}")
    total = _total_source_excerpt_chars(items)
    if total < min_total_excerpt_chars:
        errors.append(f"total excerpt chars {total} < min_total_excerpt_chars {min_total_excerpt_chars}")
    return errors


def _total_source_excerpt_chars(items: List[SynthesisItem]) -> int:
    total = 0
    for item in items:
        extra = item.extra or {}
        try:
            total += int(extra.get("source_excerpt_chars") or 0)
        except (TypeError, ValueError):
            total += 0
    return total


def _card_to_synthesis_item(card: Dict[str, Any]) -> SynthesisItem:
    topic = str(card.get("topic") or "")
    source_kind = str(card.get("source_kind") or "")
    title = str(card.get("title") or "")
    source_excerpt = _normalize_text(str(card.get("source_excerpt") or ""))
    display_excerpt = _clean_display_excerpt(source_excerpt, title=title)
    source_ref = str(card.get("source_ref") or "")

    content = f"【{topic} | {source_kind}】{title}\n\n{display_excerpt}"

    url = source_ref if _is_url(source_ref) else ""
    author = str(card.get("account") or "")
    publish_time = str(card.get("publish_time") or "")

    return SynthesisItem(
        title=title,
        content=content,
        author=author,
        source_platform=SOURCE_PLATFORM,
        url=url,
        publish_time=publish_time,
        interaction_score=0,
        extra={
            "source_type": SOURCE_TYPE,
            "source_credit": _safe_int(card.get("source_credit"), default=55),
            "verification_status": "professional_observation",
            "claim_status": "professional_observation",
            "quality_action": "preview_only",
            "knowledge_eligible": False,
            "synthesis_display_only": True,
            "scoring_eligible": False,
            "risk_score_eligible": False,
            "card_id": str(card.get("card_id") or ""),
            "source_ref": source_ref,
            "source_excerpt_hash": str(card.get("source_excerpt_hash") or ""),
            "source_excerpt_chars": len(source_excerpt),
            "display_excerpt_hash": _normalized_hash(display_excerpt),
            "display_excerpt_chars": len(display_excerpt),
            "source_block_hash": str(card.get("source_block_hash") or ""),
            "topic": topic,
        },
    )


def _clean_display_excerpt(excerpt: str, *, title: str = "") -> str:
    """Clean reader/navigation noise for report display only.

    The raw `source_excerpt` and its hash remain untouched for fidelity checks;
    this cleaned string is only what the report reader sees.
    """
    text = str(excerpt or "")
    text = re.sub(r"= {0,1}={2,}|={5,}", " ", text)
    for phrase in (
        "在小说阅读器读本章",
        "在小说阅读器中沉浸阅读",
        "去阅读",
    ):
        text = text.replace(phrase, " ")
    text = re.sub(r"[*_`]+", "", text)
    for media in (
        "ICC讯石融媒体",
        "ZIA研究",
        "水易",
    ):
        text = re.sub(rf"(?:{re.escape(media)}\s*){{2,}};?", " ", text)
        text = text.replace(media, " ")
    text = re.sub(r"(?<![A-Za-z])ICC讯(?![A-Za-z])", " ", text)
    text = re.sub(r"(?:\.\.\.|…)+", " ", text)
    text = re.sub(r"\s+[;；]\s+", " ", text)
    text = re.sub(r"(^|\s)[})）]+\s*", " ", text)

    clean_title = _normalize_text(title)
    if clean_title:
        text = re.sub(rf"^\s*{re.escape(clean_title)}\s*", "", text)

    return _dedupe_display_sentences(_normalize_text(text))


def _dedupe_display_sentences(text: str) -> str:
    sentences = re.split(r"(?:(?<=[。！？；;])\s*|(?<=%)\s+(?=[一-龥]))", str(text or ""))
    if len(sentences) <= 1:
        return _normalize_text(text)

    seen: set[str] = set()
    kept: List[str] = []
    for sentence in sentences:
        sentence = _normalize_text(sentence)
        if not sentence:
            continue
        fingerprint = re.sub(r"[^一-龥A-Za-z0-9%\.]+", "", sentence).lower()
        if len(fingerprint) >= 16 and fingerprint in seen:
            continue
        if len(fingerprint) >= 16:
            seen.add(fingerprint)
        kept.append(sentence)
    return _normalize_text(" ".join(kept))


def _sort_items(items: List[SynthesisItem]) -> None:
    # Stable sorts: least significant first.
    items.sort(key=lambda x: x.extra.get("card_id") or "")
    items.sort(
        key=lambda x: (bool(x.publish_time), x.publish_time or ""), reverse=True
    )
    items.sort(
        key=lambda x: _safe_int(
            (x.extra or {}).get("source_excerpt_chars"), default=len(x.content)
        ),
        reverse=True,
    )
    items.sort(key=lambda x: TOPIC_PRIORITY.get(x.extra.get("topic") or "", 99))


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _count_chinese_chars(text: str) -> int:
    return len(re.findall(r"[一-鿿]", text))


def _is_url(ref: str) -> bool:
    return ref.startswith("http://") or ref.startswith("https://")


def _is_valid_source_ref(ref: str) -> bool:
    if not ref:
        return False
    if _is_url(ref):
        return True
    if "/" in ref or "\\" in ref or Path(ref).exists():
        return True
    return False


def _has_capital_market_substance(card: Dict[str, Any], excerpt: str) -> bool:
    title = str(card.get("title") or "")
    combined = title + " " + excerpt
    return any(term in combined for term in _SUBSTANCE_TERMS)


def _validate_content_quality(card: Dict[str, Any], excerpt: str) -> List[str]:
    errors: List[str] = []
    title = str(card.get("title") or "")
    if any(term in title for term in _NOISY_TITLE_TERMS):
        errors.append("title quality: aggregate or sentiment-driven title")

    if _looks_like_numbered_news_digest(excerpt):
        errors.append("news digest excerpt lacks single-company focus")

    metadata_hits = sum(1 for term in _REPORT_METADATA_TERMS if term in excerpt)
    if metadata_hits >= 3 and not _has_substantive_view(excerpt):
        errors.append("report metadata excerpt lacks substantive view")

    return errors


def _looks_like_numbered_news_digest(excerpt: str) -> bool:
    head = excerpt[:260]
    return len(re.findall(r"(?:^|[；;。\s])\d{1,2}[\.．、]", head)) >= 3


def _has_substantive_view(excerpt: str) -> bool:
    return any(term in excerpt for term in _SUBSTANTIVE_VIEW_TERMS)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
