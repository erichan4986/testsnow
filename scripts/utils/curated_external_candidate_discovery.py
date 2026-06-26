"""Preview-only candidate discovery for curated external materials.

This module is a local pre-ingestion layer: it normalizes existing candidate
lists and downloaded/exported materials, dedupes them across sources, and writes
review previews. It deliberately does not fetch webpages, write Knowledge, or
connect candidates to canonical synthesis, scoring, or risk.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

if __name__.startswith("utils."):
    from .curated_external_analysis_pack import DEFAULT_MAX_ITEM_CHARS, load_url_list, read_local_materials
else:
    from curated_external_analysis_pack import DEFAULT_MAX_ITEM_CHARS, load_url_list, read_local_materials


DEFAULT_DISCOVERY_PREVIEW_PATH = Path("/tmp/curated_external_candidate_discovery_preview.md")
DEFAULT_DISCOVERY_JSONL_PATH = Path("/tmp/curated_external_candidate_discovery_candidates.jsonl")

_SAFE_ACTIONS = {"keep", "product_signal"}
_SAFE_WECHAT_CLASSIFICATIONS = {
    "high_quality_analysis",
    "customer_order_or_design_win",
    "capacity_supply_chain_signal",
    "industry_cycle_price_signal",
    "certification_policy_standard",
    "earnings_financial_context",
    "product_or_event_signal",
    "product_signal",
    "capital_market_context",
    "analysis",
}
_UNSAFE_ELIGIBILITY_FIELDS = (
    "knowledge_eligible",
    "synthesis_eligible",
    "scoring_eligible",
    "risk_score_eligible",
)
_PRESERVED_CURATED_SOURCE_KINDS = {"video_subtitle"}


def build_curated_external_candidate_discovery(
    *,
    url_list_path: str | Path | None = None,
    materials_dir: str | Path | None = None,
    wechat_selector_file: str | Path | None = None,
    curated_preview_file: str | Path | None = None,
    since_date: str | None = None,
    theme_keywords: str | Iterable[str] | None = None,
    min_theme_score: int = 0,
    max_item_chars: int = DEFAULT_MAX_ITEM_CHARS,
) -> Dict[str, Any]:
    """Build a local preview-only candidate pool from existing inputs."""
    candidates: List[Dict[str, Any]] = []

    candidates.extend(_url_candidates(url_list_path))
    candidates.extend(_curated_preview_candidates(curated_preview_file, max_item_chars=max_item_chars))
    candidates.extend(_local_material_candidates(materials_dir, max_item_chars=max_item_chars))
    candidates.extend(_wechat_selector_candidates(wechat_selector_file, max_item_chars=max_item_chars))

    theme_terms = _normalize_theme_keywords(theme_keywords)
    candidates = _filter_since_date(candidates, since_date)
    candidates = [_annotate_candidate_rank(item, theme_keywords=theme_terms) for item in candidates]
    candidates = _filter_theme_score(candidates, min_theme_score)
    items, deduped_sources = _dedupe_candidates(candidates)
    items = sorted(items, key=_candidate_sort_key, reverse=True)
    counts = dict(Counter(item.get("source_kind", "") for item in items))
    return {
        "status": "ok" if items else "empty",
        "items": items,
        "counts": counts,
        "deduped_sources": deduped_sources,
        "wrote_knowledge": False,
        "connected_synthesis": False,
    }


def build_curated_external_candidate_discovery_markdown(summary: Dict[str, Any]) -> str:
    """Render candidate discovery summary as Markdown."""
    items = summary.get("items", []) or []
    lines = [
        "# Curated External Candidate Discovery Preview",
        "",
        "> Preview-only：候选发现和二层去重预览；不写 Knowledge，不接 synthesis，不进入评分或风险评分。",
        "",
        "## Summary",
        "",
        f"- status: `{summary.get('status', '')}`",
        f"- items: `{len(items)}`",
    ]
    for source_kind, count in sorted((summary.get("counts") or {}).items()):
        lines.append(f"- {source_kind}: `{count}`")
    lines.append("")

    if items:
        lines.extend(["## Candidates", ""])
        for index, item in enumerate(items, start=1):
            lines.extend(_render_candidate_lines(index, item))

    deduped_sources = summary.get("deduped_sources", []) or []
    if deduped_sources:
        lines.extend(["## Deduped Sources", ""])
        for record in deduped_sources:
            lines.append(
                "- reason: `{reason}` | kept: {kept} | duplicate: {duplicate}".format(
                    reason=record.get("reason", ""),
                    kept=_source_label(record.get("kept") or {}),
                    duplicate=_source_label(record.get("duplicate") or {}),
                )
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_curated_external_candidate_discovery_preview(
    *,
    url_list_path: str | Path | None = None,
    materials_dir: str | Path | None = None,
    wechat_selector_file: str | Path | None = None,
    curated_preview_file: str | Path | None = None,
    since_date: str | None = None,
    theme_keywords: str | Iterable[str] | None = None,
    min_theme_score: int = 0,
    output_path: str | Path = DEFAULT_DISCOVERY_PREVIEW_PATH,
    jsonl_output_path: str | Path = DEFAULT_DISCOVERY_JSONL_PATH,
    max_item_chars: int = DEFAULT_MAX_ITEM_CHARS,
) -> Dict[str, Any]:
    """Write Markdown and JSONL previews for local candidate discovery."""
    summary = build_curated_external_candidate_discovery(
        url_list_path=url_list_path,
        materials_dir=materials_dir,
        wechat_selector_file=wechat_selector_file,
        curated_preview_file=curated_preview_file,
        since_date=since_date,
        theme_keywords=theme_keywords,
        min_theme_score=min_theme_score,
        max_item_chars=max_item_chars,
    )
    markdown_path = Path(output_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(build_curated_external_candidate_discovery_markdown(summary), encoding="utf-8")

    jsonl_path = Path(jsonl_output_path)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in summary.get("items", []) or [])
        + ("\n" if summary.get("items") else ""),
        encoding="utf-8",
    )
    return {**summary, "preview_path": str(markdown_path), "jsonl_path": str(jsonl_path)}


def _url_candidates(path: str | Path | None) -> List[Dict[str, Any]]:
    return [
        _build_candidate(
            source_kind="url_candidate",
            title=entry.get("title") or entry.get("url") or "url-candidate",
            url=entry.get("url", ""),
            content_preview="",
        )
        for entry in load_url_list(path)
    ]


def _local_material_candidates(path: str | Path | None, *, max_item_chars: int) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for item in read_local_materials(path, max_chars=max_item_chars):
        items.append(
            _build_candidate(
                source_kind="local_file",
                title=str(item.get("title") or item.get("path") or "local-file"),
                url=str(item.get("url") or ""),
                path=str(item.get("path") or ""),
                content_preview=str(item.get("content") or ""),
            )
        )
    return items


def _curated_preview_candidates(path: str | Path | None, *, max_item_chars: int) -> List[Dict[str, Any]]:
    if not path:
        return []
    payload = _read_json_or_jsonl(path)
    raw_items = payload.get("items", []) if isinstance(payload, dict) else payload
    items: List[Dict[str, Any]] = []
    for raw in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(raw, dict) or _has_unsafe_eligibility(raw):
            continue
        quality_action = str(raw.get("quality_action") or "preview_only")
        if quality_action != "preview_only":
            continue
        raw_source_kind = str(raw.get("source_kind") or "")
        source_kind = raw_source_kind if raw_source_kind in _PRESERVED_CURATED_SOURCE_KINDS else "curated_preview"
        content_preview = _truncate(str(raw.get("content") or raw.get("content_preview") or ""), max_item_chars)
        if _looks_like_fetch_error(content_preview):
            continue
        items.append(
            _build_candidate(
                source_kind=source_kind,
                title=str(raw.get("title") or raw.get("url") or raw.get("path") or "curated-preview"),
                url=str(raw.get("url") or ""),
                path=str(raw.get("path") or ""),
                content_preview=content_preview,
                source_type=str(raw.get("source_type") or raw.get("source_kind") or ""),
            )
        )
    return items


def _wechat_selector_candidates(path: str | Path | None, *, max_item_chars: int) -> List[Dict[str, Any]]:
    if not path:
        return []
    payload = _read_json_or_jsonl(path)
    raw_items = payload.get("items", []) if isinstance(payload, dict) else payload
    items: List[Dict[str, Any]] = []
    for raw in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(raw, dict) or _has_unsafe_eligibility(raw):
            continue
        action = str(raw.get("action") or raw.get("wechat_action") or "")
        classification = _normalize_wechat_classification(raw.get("classification") or raw.get("category") or action)
        if action not in _SAFE_ACTIONS and classification not in _SAFE_WECHAT_CLASSIFICATIONS:
            continue
        if classification not in _SAFE_WECHAT_CLASSIFICATIONS:
            continue
        candidate = raw.get("candidate") if isinstance(raw.get("candidate"), dict) else raw
        source_kind = _wechat_source_kind(classification)
        items.append(
            _build_candidate(
                source_kind=source_kind,
                title=str(candidate.get("title") or candidate.get("url") or "wechat-candidate"),
                url=str(candidate.get("url") or ""),
                content_preview=_truncate(
                    str(candidate.get("digest") or candidate.get("summary") or candidate.get("content") or ""),
                    max_item_chars,
                ),
                account=str(candidate.get("account") or ""),
                publish_time=str(candidate.get("publish_time") or candidate.get("publish_date") or candidate.get("date") or ""),
                matched_terms=list(raw.get("matched_terms") or []),
                source_type=source_kind,
                wechat_action=action or classification,
                wechat_signal_category=classification,
                quality_score=_as_int(raw.get("quality_score"), 0),
            )
        )
    return items


def _build_candidate(
    *,
    source_kind: str,
    title: str,
    url: str = "",
    path: str = "",
    content_preview: str = "",
    account: str = "",
    publish_time: str = "",
    matched_terms: Optional[List[str]] = None,
    source_type: str = "",
    wechat_action: str = "",
    wechat_signal_category: str = "",
    quality_score: int = 0,
) -> Dict[str, Any]:
    return {
        "source_kind": source_kind,
        "source_type": source_type or source_kind,
        "title": _clean_text(title),
        "url": str(url or "").strip(),
        "path": str(path or "").strip(),
        "account": _clean_text(account),
        "publish_time": str(publish_time or "").strip(),
        "content_preview": _clean_text(content_preview),
        "matched_terms": matched_terms or [],
        "wechat_action": wechat_action,
        "wechat_signal_category": wechat_signal_category,
        "quality_score": quality_score,
        "quality_action": "preview_only",
        "knowledge_eligible": False,
        "synthesis_eligible": False,
        "scoring_eligible": False,
        "risk_score_eligible": False,
    }


def _dedupe_candidates(items: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    kept_items: List[Dict[str, Any]] = []
    seen: Dict[str, int] = {}
    deduped_sources: List[Dict[str, Any]] = []

    for item in items:
        keys = _candidate_dedupe_keys(item)
        duplicate_key = next((key for key in keys if key in seen), "")
        if not duplicate_key:
            kept_items.append(item)
            for key in keys:
                seen[key] = len(kept_items) - 1
            continue

        duplicate_index = seen[duplicate_key]
        kept = kept_items[duplicate_index]
        reason = _dedupe_reason(duplicate_key)
        if _candidate_priority(item) > _candidate_priority(kept):
            kept_items[duplicate_index] = item
            for key in _candidate_dedupe_keys(kept):
                seen.pop(key, None)
            for key in keys:
                seen[key] = duplicate_index
            deduped_sources.append({"reason": reason, "kept": _source_ref(item), "duplicate": _source_ref(kept)})
            continue

        deduped_sources.append({"reason": reason, "kept": _source_ref(kept), "duplicate": _source_ref(item)})

    return kept_items, deduped_sources


def _filter_since_date(items: List[Dict[str, Any]], since_date: str | None) -> List[Dict[str, Any]]:
    threshold = _date_key(since_date or "")
    if not threshold:
        return items
    filtered: List[Dict[str, Any]] = []
    for item in items:
        item_date = _date_key(str(item.get("publish_time") or ""))
        if item_date and item_date < threshold:
            continue
        filtered.append(item)
    return filtered


def _candidate_dedupe_keys(item: Dict[str, Any]) -> List[str]:
    keys: List[str] = []
    url_key = _normalized_url_key(str(item.get("url") or ""))
    if url_key:
        keys.append(f"url:{url_key}")
    fingerprint = _content_fingerprint(str(item.get("content_preview") or ""))
    if fingerprint:
        keys.append(f"content:{fingerprint}")
    title_fingerprint = _title_fingerprint(str(item.get("title") or ""))
    if title_fingerprint:
        keys.append(f"title:{title_fingerprint}")
    return keys


def _dedupe_reason(duplicate_key: str) -> str:
    if duplicate_key.startswith("url:"):
        return "normalized_url"
    if duplicate_key.startswith("title:"):
        return "title_fingerprint"
    return "content_fingerprint"


def _candidate_priority(item: Dict[str, Any]) -> tuple[int, str, int]:
    return (
        _as_int(item.get("discovery_score"), 0),
        _date_key(str(item.get("publish_time") or "")),
        len(str(item.get("content_preview") or "")),
    )


def _candidate_sort_key(item: Dict[str, Any]) -> tuple[int, str, int]:
    return _candidate_priority(item)


def _annotate_candidate_rank(item: Dict[str, Any], *, theme_keywords: List[str]) -> Dict[str, Any]:
    ranked = dict(item)
    theme_score, matched_theme_terms = _candidate_theme_match(ranked, theme_keywords)
    ranked["theme_score"] = theme_score
    ranked["matched_theme_terms"] = matched_theme_terms
    score, reasons = _candidate_rank(ranked)
    ranked["discovery_score"] = score
    ranked["ranking_reasons"] = reasons
    return ranked


def _candidate_rank(item: Dict[str, Any]) -> tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []
    source_kind = str(item.get("source_kind") or "")

    source_score = {
        "local_file": 80,
        "curated_preview": 68,
        "video_subtitle": 64,
        "wechat_high_quality_analysis": 66,
        "wechat_customer_order_or_design_win": 65,
        "wechat_capacity_supply_chain_signal": 64,
        "wechat_industry_cycle_price_signal": 63,
        "wechat_earnings_financial_context": 62,
        "wechat_product_signal": 62,
        "wechat_certification_policy_standard": 62,
        "wechat_capital_market_context": 55,
        "wechat_analysis_candidate": 60,
        "url_candidate": 25,
    }.get(source_kind, 20)
    score += source_score
    reasons.append(
        {
            "local_file": "human_curated_local_file",
            "curated_preview": "curated_preview_item",
            "video_subtitle": "explicit_video_subtitle",
            "wechat_high_quality_analysis": "wechat_high_quality_analysis",
            "wechat_customer_order_or_design_win": "wechat_commercial_event",
            "wechat_capacity_supply_chain_signal": "wechat_capacity_supply_chain_signal",
            "wechat_industry_cycle_price_signal": "wechat_industry_cycle_price_signal",
            "wechat_earnings_financial_context": "wechat_earnings_financial_context",
            "wechat_product_signal": "wechat_product_signal",
            "wechat_certification_policy_standard": "wechat_certification_policy_standard",
            "wechat_capital_market_context": "wechat_capital_market_context",
            "wechat_analysis_candidate": "wechat_analysis_candidate",
            "url_candidate": "explicit_url_candidate",
        }.get(source_kind, "source_kind")
    )

    quality_score = max(0, min(_as_int(item.get("quality_score"), 0), 100))
    if quality_score:
        score += quality_score // 5
        reasons.append("selector_quality_score")

    matched_terms = item.get("matched_terms") or []
    if matched_terms:
        score += min(len(matched_terms), 5) * 2
        reasons.append("matched_terms")

    theme_score = _as_int(item.get("theme_score"), 0)
    if theme_score:
        score += min(theme_score * 4, 40)
        reasons.append("theme_match")

    if _date_key(str(item.get("publish_time") or "")):
        score += 5
        reasons.append("dated_candidate")

    content_length = len(str(item.get("content_preview") or ""))
    if content_length >= 1200:
        score += 8
        reasons.append("substantive_content")
    elif content_length >= 240:
        score += 4
        reasons.append("content_preview")

    if item.get("url"):
        score += 2
        reasons.append("traceable_url")
    if item.get("path"):
        score += 2
        reasons.append("traceable_local_path")

    return score, reasons


def _render_candidate_lines(index: int, item: Dict[str, Any]) -> List[str]:
    lines = [
        f"### {index}. {item.get('title') or item.get('url') or item.get('path') or 'candidate'}",
        "",
        f"- source_kind: `{item.get('source_kind', '')}`",
        f"- quality_action: `{item.get('quality_action', '')}`",
        f"- knowledge_eligible: `{str(bool(item.get('knowledge_eligible'))).lower()}`",
        f"- synthesis_eligible: `{str(bool(item.get('synthesis_eligible'))).lower()}`",
        f"- scoring_eligible: `{str(bool(item.get('scoring_eligible'))).lower()}`",
        f"- risk_score_eligible: `{str(bool(item.get('risk_score_eligible'))).lower()}`",
    ]
    if item.get("discovery_score") is not None:
        lines.append(f"- discovery_score: `{item.get('discovery_score')}`")
    if item.get("ranking_reasons"):
        lines.append(f"- ranking_reasons: `{', '.join(item.get('ranking_reasons') or [])}`")
    if item.get("url"):
        lines.append(f"- url: {item.get('url')}")
    if item.get("path"):
        lines.append(f"- path: `{item.get('path')}`")
    if item.get("account"):
        lines.append(f"- account: `{item.get('account')}`")
    if item.get("publish_time"):
        lines.append(f"- publish_time: `{item.get('publish_time')}`")
    if item.get("matched_terms"):
        lines.append(f"- matched_terms: `{', '.join(item.get('matched_terms') or [])}`")
    if item.get("wechat_signal_category"):
        lines.append(f"- wechat_signal_category: `{item.get('wechat_signal_category')}`")
    if item.get("theme_score") is not None:
        lines.append(f"- theme_score: `{item.get('theme_score')}`")
    if item.get("matched_theme_terms"):
        lines.append(f"- matched_theme_terms: `{', '.join(item.get('matched_theme_terms') or [])}`")
    if item.get("content_preview"):
        lines.extend(["", str(item.get("content_preview") or ""), ""])
    else:
        lines.append("")
    return lines


def _read_json_or_jsonl(path: str | Path) -> Any:
    candidate_path = Path(path)
    text = candidate_path.read_text(encoding="utf-8")
    if candidate_path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if isinstance(payload, dict) and "items" in payload:
        return payload
    return payload


def _has_unsafe_eligibility(item: Dict[str, Any]) -> bool:
    return any(bool(item.get(field)) for field in _UNSAFE_ELIGIBILITY_FIELDS)


def _filter_theme_score(items: List[Dict[str, Any]], min_theme_score: int) -> List[Dict[str, Any]]:
    if min_theme_score <= 0:
        return items
    return [item for item in items if _as_int(item.get("theme_score"), 0) >= min_theme_score]


def _normalize_theme_keywords(value: str | Iterable[str] | None) -> List[str]:
    if value is None:
        return []

    raw_terms: List[str] = []
    if isinstance(value, str):
        raw_terms.extend(re.split(r"[,，;；\n]+", value))
    else:
        for item in value:
            raw_terms.extend(re.split(r"[,，;；\n]+", str(item or "")))

    terms: List[str] = []
    seen = set()
    for raw in raw_terms:
        term = _clean_text(raw)
        if not term:
            continue
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        terms.append(term)
    return terms


def _candidate_theme_match(item: Dict[str, Any], keywords: List[str]) -> tuple[int, List[str]]:
    if not keywords:
        return 0, []

    title_text = str(item.get("title") or "").lower()
    body_text = " ".join(
        [
            str(item.get("content_preview") or ""),
            str(item.get("account") or ""),
            str(item.get("source_type") or ""),
            " ".join(str(term) for term in item.get("matched_terms") or []),
        ]
    ).lower()

    score = 0
    matched: List[str] = []
    for term in keywords:
        key = term.lower()
        if not key:
            continue
        title_hit = key in title_text
        body_hit = key in body_text
        if not title_hit and not body_hit:
            continue
        matched.append(term)
        if title_hit:
            score += 3
        if body_hit:
            score += 2
    return score, matched


def _looks_like_fetch_error(content: str) -> bool:
    text = _clean_text(content).lower()
    if not text:
        return False
    error_markers = (
        "warning: target url returned error",
        "404: not found",
        "403: forbidden",
        "502: bad gateway",
        "503: service unavailable",
        "429: too many requests",
    )
    return any(marker in text for marker in error_markers)


def _normalize_wechat_classification(value: Any) -> str:
    classification = str(value or "").strip()
    if classification == "analysis":
        return "high_quality_analysis"
    if classification == "product_signal":
        return "product_or_event_signal"
    if classification == "keep":
        return "high_quality_analysis"
    return classification


def _wechat_source_kind(classification: str) -> str:
    if classification == "product_or_event_signal":
        return "wechat_product_signal"
    if classification == "high_quality_analysis":
        return "wechat_high_quality_analysis"
    return f"wechat_{classification}"


def _normalized_url_key(url: str) -> str:
    parsed = urllib.parse.urlparse((url or "").split("#", 1)[0].strip())
    if not parsed.netloc:
        return ""
    host = re.sub(r"^(?:www|m)\.", "", parsed.netloc.lower())
    path = urllib.parse.unquote(parsed.path or "/").rstrip("/") or "/"
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
    noise_params = {"spm", "from", "source", "share", "share_source", "sharefrom", "hmsr", "hmpl", "hmcu", "hmkw", "hmci"}
    filtered_query = [
        (key, value)
        for key, value in query_pairs
        if not key.lower().startswith("utm_") and key.lower() not in noise_params
    ]
    query = urllib.parse.urlencode(filtered_query)
    return f"{host}{path}" + (f"?{query}" if query else "")


def _content_fingerprint(content: str) -> str:
    normalized = re.sub(r"https?://\S+", " ", content or "")
    normalized = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", normalized)
    normalized = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", normalized)
    normalized = re.sub(r"[`*_#>\-|:：，,。.!！?？、；;（）()\[\]{}\"'“”‘’]", " ", normalized)
    normalized = re.sub(r"\s+", "", normalized).lower()
    if len(normalized) < 24:
        return ""
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _title_fingerprint(title: str) -> str:
    normalized = re.sub(r"\.(?:md|txt|html?|jsonl?|json)$", "", title or "", flags=re.IGNORECASE)
    normalized = re.sub(r"[`*_#>\-|:：，,。.!！?？、；;（）()\[\]{}\"'“”‘’\s]", "", normalized).lower()
    if len(normalized) < 14:
        return ""
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _source_ref(item: Dict[str, Any]) -> Dict[str, str]:
    return {
        "source_kind": str(item.get("source_kind") or ""),
        "title": str(item.get("title") or ""),
        "url": str(item.get("url") or ""),
        "path": str(item.get("path") or ""),
        "discovery_score": str(item.get("discovery_score") or ""),
    }


def _source_label(item: Dict[str, Any]) -> str:
    title = str(item.get("title") or item.get("url") or item.get("path") or item.get("source_kind") or "unknown")
    source_kind = str(item.get("source_kind") or "unknown")
    location = str(item.get("url") or item.get("path") or "")
    if location:
        return f"{title} ({source_kind}: {location})"
    return f"{title} ({source_kind})"


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _date_key(text: str) -> str:
    match = re.search(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})", str(text or ""))
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
