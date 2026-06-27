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
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


CARDS_SCHEMA_VERSION = "curated_external_evidence_cards.v1"
CARD_SCHEMA_VERSION = "periodic_report_narrative_evidence_card.v1"
SOURCE_TYPE = "curated_external_analysis_evidence"
DEFAULT_MAX_EXCERPT_CHARS = 1200
_EXCERPT_JOINER = "\n...\n"
_MIN_SNIPPET_CHARS = 24
_MAX_SNIPPETS_PER_CARD = 5

_REPORT_METADATA_TERMS = (
    "文中报告节选",
    "证券研究报告",
    "报告发布机构",
    "本报告分析师",
    "执业证书编号",
)

_BODY_SIGNAL_TERMS = (
    "800G",
    "1.6T",
    "AI算力",
    "CapEx",
    "硅光",
    "投资要点",
    "核心观点",
    "业绩",
    "毛利率",
    "客户订单",
    "产能扩张",
    "规模交付",
    "需求共振",
    "盈利能力",
)

_AGGREGATOR_TABLE_MARKERS = (
    "日期 机构 研报标题 核心观点",
    "以下是中际旭创（300308）近期的主要市场文章和研报汇总",
    "分析师评级与目标价",
    "机构 评级 目标价 日期",
)

_EXCERPT_SELECTION_RULES: Dict[str, Any] = {
    "common_signal_terms": (
        "营收",
        "收入",
        "净利润",
        "亏损",
        "毛利",
        "毛利率",
        "现金流",
        "研发",
        "费用",
        "三费",
        "占营收",
        "同比",
        "环比",
        "订单",
        "客户",
        "定点",
        "量产",
        "交付",
        "商业化",
        "合作",
        "认证",
        "审查",
        "产能",
        "供给",
        "涨价",
        "价格",
        "上调",
        "周期",
        "景气",
        "募资",
        "招股",
        "上市",
        "递表",
        "资本开支",
        "市占率",
        "份额",
        "国产替代",
        "供应链",
    ),
    "topic_signal_terms": {
        "commercialization": ("订单", "客户", "定点", "量产", "交付", "商业化", "合作", "导入", "车型"),
        "earnings_context": ("财报", "业绩", "营收", "收入", "净利润", "亏损", "毛利", "费用", "现金流", "同比"),
        "cycle_price": ("涨价", "价格", "上调", "周期", "景气", "库存", "供给", "产能", "需求"),
        "industry_logic": ("行业", "竞争", "格局", "国产替代", "市场", "份额", "产业链", "供应链"),
        "certification_policy": ("认证", "审查", "标准", "政策", "ASIL", "ISO", "通过"),
        "capital_market_context": ("募资", "招股", "上市", "递表", "发行", "聆讯", "港交所"),
    },
    "noise_terms": (
        "免责声明",
        "风险提示",
        "点击上方",
        "关注公众号",
        "设为星标",
        "扫码",
        "原文链接",
        "阅读原文",
        "广告",
    ),
    "tail_markers": (
        "往期热文推荐",
        "相关推荐",
        "联系我们",
        "报告询价",
        "商务合作",
        "进群交流",
        "阅读原文",
        "_**END**_",
        "**END**",
        "免责声明",
    ),
    "title_ignore_terms": {"深度分析", "财报", "观察", "文章", "报告", "公司", "股份", "智能", "电子"},
}


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
    source_content = _clean_source_content(item.get("content") or title)
    selected_excerpts = _deterministic_excerpts(
        source_content,
        item=item,
        stock_name=stock_name,
        max_excerpt_chars=max_excerpt_chars,
    )
    source_excerpt = _EXCERPT_JOINER.join(selected_excerpts)
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
    excerpts = [
        _excerpt_record(
            card_id=card_id,
            excerpt_index=excerpt_index,
            excerpt=excerpt,
            source_content=source_content,
            item=item,
            stock_name=stock_name,
        )
        for excerpt_index, excerpt in enumerate(selected_excerpts)
    ]
    pack = {
        "pack_id": f"{card_id}:pack",
        "card_id": card_id,
        "source_ref": source_ref,
        "source_refs": source_refs,
        "source_content_hash": source_block_hash,
        "source_content_chars": len(source_content),
        "combined_source_excerpt_hash": source_excerpt_hash,
        "excerpts": excerpts,
    }
    return card, pack


def _excerpt_record(
    *,
    card_id: str,
    excerpt_index: int,
    excerpt: str,
    source_content: str,
    item: Dict[str, Any],
    stock_name: str,
) -> Dict[str, Any]:
    matched_terms = _matched_selection_terms(excerpt, item=item, stock_name=stock_name)
    return {
            "excerpt_id": f"{card_id}:excerpt:{excerpt_index}",
            "text": excerpt,
            "source_excerpt_hash": normalized_hash(excerpt),
            "char_count": len(excerpt),
            "normalized_substring_verified": _normalize_text(excerpt) in _normalize_text(source_content),
            "matched_terms": matched_terms,
            "selection_reason": _selection_reason(excerpt, matched_terms),
    }


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


def _deterministic_excerpts(
    text: str,
    *,
    item: Dict[str, Any],
    stock_name: str,
    max_excerpt_chars: int,
) -> List[str]:
    source = _clean_text(text)
    if max_excerpt_chars <= 0:
        return []

    scored: List[Tuple[int, int, str]] = []
    for position, snippet in enumerate(_split_snippets(source)):
        score = _score_excerpt_snippet(snippet, item=item, stock_name=stock_name)
        if score <= 0:
            continue
        scored.append((score, position, snippet))

    if not scored:
        fallback = _deterministic_excerpt(source, max_excerpt_chars=max_excerpt_chars)
        return [fallback] if fallback else []

    selected: List[Tuple[int, str]] = []
    used_normalized = set()
    used_chars = 0
    max_single_excerpt_chars = max_excerpt_chars if len(scored) == 1 else max(_MIN_SNIPPET_CHARS, max_excerpt_chars // 2)
    for _score, position, snippet in sorted(scored, key=lambda row: (-row[0], row[1])):
        if len(selected) >= _MAX_SNIPPETS_PER_CARD:
            break
        remaining = max_excerpt_chars - used_chars
        if selected:
            remaining -= len(_EXCERPT_JOINER)
        if remaining < _MIN_SNIPPET_CHARS:
            break
        excerpt = _truncate_snippet(snippet, min(remaining, max_single_excerpt_chars))
        normalized = _normalize_text(excerpt)
        if not normalized or normalized in used_normalized:
            continue
        selected.append((position, excerpt))
        used_normalized.add(normalized)
        used_chars += len(excerpt) + (len(_EXCERPT_JOINER) if len(selected) > 1 else 0)

    if not selected:
        fallback = _deterministic_excerpt(source, max_excerpt_chars=max_excerpt_chars)
        return [fallback] if fallback else []
    return [excerpt for _position, excerpt in sorted(selected, key=lambda row: row[0])]


def _split_snippets(text: str) -> List[str]:
    normalized = _clean_text(text)
    pieces = re.split(r"(?<=[。！？；;])\s*|\n+", normalized)
    snippets = [piece.strip(" 　：:，,") for piece in pieces if len(piece.strip()) >= _MIN_SNIPPET_CHARS]
    if snippets:
        return snippets
    return [normalized[i : i + 260].strip() for i in range(0, len(normalized), 260) if normalized[i : i + 260].strip()]


def _score_excerpt_snippet(snippet: str, *, item: Dict[str, Any], stock_name: str) -> int:
    score = 0
    topic = str(item.get("topic") or "")
    title = str(item.get("title") or "")
    source_kind = str(item.get("source_kind") or "")

    if stock_name and stock_name in snippet:
        score += 8
    for term in _title_terms(title):
        if term and term in snippet:
            score += 3
    topic_terms = _EXCERPT_SELECTION_RULES["topic_signal_terms"].get(topic, ())
    score += sum(4 for term in topic_terms if term in snippet)
    score += sum(2 for term in _EXCERPT_SELECTION_RULES["common_signal_terms"] if term in snippet)
    score += sum(5 for term in _BODY_SIGNAL_TERMS if term in snippet)
    if re.search(r"\d+(?:\.\d+)?\s*(?:亿元|万元|%|TOPS|G|T|万片|颗|倍)", snippet):
        score += 7
    elif re.search(r"\d+(?:\.\d+)?", snippet):
        score += 2
    if source_kind.startswith("wechat_") and any(term in snippet for term in ("公众号", "扫码", "星标", "点击", "关注我们")):
        score -= 8
    if _looks_like_navigation_or_disclaimer(snippet):
        score -= 12

    metadata_hits = sum(1 for term in _REPORT_METADATA_TERMS if term in snippet)
    if metadata_hits >= 2:
        score -= 100
    if any(marker in snippet for marker in _AGGREGATOR_TABLE_MARKERS):
        score -= 100

    return score


def _title_terms(title: str) -> List[str]:
    raw_terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9\.\-]{1,}|[\u4e00-\u9fff]{2,}", title)
    ignored = _EXCERPT_SELECTION_RULES["title_ignore_terms"]
    return [term for term in raw_terms if term not in ignored and len(term) <= 20][:8]


def _looks_like_navigation_or_disclaimer(snippet: str) -> bool:
    return any(term in snippet for term in _EXCERPT_SELECTION_RULES["noise_terms"])


def _matched_selection_terms(snippet: str, *, item: Dict[str, Any], stock_name: str) -> List[str]:
    topic = str(item.get("topic") or "")
    title = str(item.get("title") or "")
    terms: List[str] = []
    if stock_name and stock_name in snippet:
        terms.append(stock_name)
    terms.extend(term for term in _title_terms(title) if term in snippet)
    terms.extend(term for term in _EXCERPT_SELECTION_RULES["topic_signal_terms"].get(topic, ()) if term in snippet)
    terms.extend(term for term in _EXCERPT_SELECTION_RULES["common_signal_terms"] if term in snippet)
    if re.search(r"\d+(?:\.\d+)?\s*(?:亿元|万元|%|TOPS|G|T|万片|颗|倍)", snippet):
        terms.append("numeric_metric")
    return _dedupe_preserve_order(terms)


def _selection_reason(snippet: str, matched_terms: List[str]) -> str:
    if matched_terms:
        return "matched_terms:" + ",".join(matched_terms[:8])
    if re.search(r"\d+(?:\.\d+)?", snippet):
        return "numeric_signal"
    return "fallback_context"


def _truncate_snippet(snippet: str, max_chars: int) -> str:
    if len(snippet) <= max_chars:
        return snippet
    window = snippet[:max_chars].rstrip()
    cut = max(window.rfind(mark) for mark in ("。", "；", ";", "！", "？"))
    if cut >= _MIN_SNIPPET_CHARS:
        return window[: cut + 1].rstrip()
    return window


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
        all_verified = all(bool(excerpt.get("normalized_substring_verified")) for excerpt in excerpts if isinstance(excerpt, dict))
        lines.append(f"- normalized_substring_verified: `{str(all_verified).lower()}`")
        lines.extend(["", "> " + str(card.get("source_excerpt", "")).replace("\n", "\n> "), ""])
    else:
        lines.append("")
    return lines


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _clean_text(text: Any) -> str:
    return _normalize_text(str(text or ""))


def _clean_source_content(text: Any) -> str:
    source = _clean_text(text)
    cut_positions = [
        source.find(marker)
        for marker in _EXCERPT_SELECTION_RULES["tail_markers"]
        if source.find(marker) > 0
    ]
    if cut_positions:
        source = source[: min(cut_positions)]
    source = _strip_markdown_noise(source)
    return _clean_text(source)


def _strip_markdown_noise(text: str) -> str:
    """Remove markdown images/links and stray HTML/JS fragments from WeChat exports.

    Keeps the underlying text; the cleaned result is what excerpt selection runs
    against, so source_excerpt remains a deterministic substring of the cleaned
    source content and hash fidelity still holds.
    """
    source = str(text or "")
    # Markdown images: ![alt](url)
    source = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", source)
    # Markdown links: [text](url), including javascript:void(...) navigation
    source = re.sub(r"\[[^\]]*\]\([^)]*\)", " ", source)
    # HTML image tags and other raw tags
    source = re.sub(r"<img[^>]*>", " ", source, flags=re.IGNORECASE)
    source = re.sub(r"<[^>]+>", " ", source)
    # Stray leading punctuation left by removed markup
    source = re.sub(r"^[}\]\)\>\|]+\s*", "", source)
    return _normalize_text(source)


def _sorted_unique(values: List[str]) -> List[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result
