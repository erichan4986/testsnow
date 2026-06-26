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
from typing import Any, Dict, List, Optional

if __name__.startswith("utils."):
    from .curated_external_analysis_pack import DEFAULT_MAX_ITEM_CHARS, load_url_list, read_local_materials
else:
    from curated_external_analysis_pack import DEFAULT_MAX_ITEM_CHARS, load_url_list, read_local_materials


DEFAULT_DISCOVERY_PREVIEW_PATH = Path("/tmp/curated_external_candidate_discovery_preview.md")
DEFAULT_DISCOVERY_JSONL_PATH = Path("/tmp/curated_external_candidate_discovery_candidates.jsonl")

_SAFE_ACTIONS = {"keep", "product_signal"}
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
    max_item_chars: int = DEFAULT_MAX_ITEM_CHARS,
) -> Dict[str, Any]:
    """Build a local preview-only candidate pool from existing inputs."""
    candidates: List[Dict[str, Any]] = []

    candidates.extend(_url_candidates(url_list_path))
    candidates.extend(_curated_preview_candidates(curated_preview_file, max_item_chars=max_item_chars))
    candidates.extend(_local_material_candidates(materials_dir, max_item_chars=max_item_chars))
    candidates.extend(_wechat_selector_candidates(wechat_selector_file, max_item_chars=max_item_chars))

    candidates = _filter_since_date(candidates, since_date)
    items, deduped_sources = _dedupe_candidates(candidates)
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
        items.append(
            _build_candidate(
                source_kind=source_kind,
                title=str(raw.get("title") or raw.get("url") or raw.get("path") or "curated-preview"),
                url=str(raw.get("url") or ""),
                path=str(raw.get("path") or ""),
                content_preview=_truncate(str(raw.get("content") or raw.get("content_preview") or ""), max_item_chars),
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
        if action not in _SAFE_ACTIONS:
            continue
        candidate = raw.get("candidate") if isinstance(raw.get("candidate"), dict) else raw
        source_kind = "wechat_product_signal" if action == "product_signal" else "wechat_analysis_candidate"
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
                publish_time=str(candidate.get("publish_time") or candidate.get("date") or ""),
                matched_terms=list(raw.get("matched_terms") or []),
                source_type="wechat_product_signal" if source_kind == "wechat_product_signal" else "wechat_analysis_candidate",
                wechat_action=action,
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
        duplicate_index = next((seen[key] for key in keys if key in seen), None)
        if duplicate_index is None:
            kept_items.append(item)
            for key in keys:
                seen[key] = len(kept_items) - 1
            continue

        kept = kept_items[duplicate_index]
        reason = _dedupe_reason(kept, item)
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
    return keys


def _dedupe_reason(kept: Dict[str, Any], duplicate: Dict[str, Any]) -> str:
    kept_url = _normalized_url_key(str(kept.get("url") or ""))
    duplicate_url = _normalized_url_key(str(duplicate.get("url") or ""))
    if kept_url and kept_url == duplicate_url:
        return "normalized_url"
    return "content_fingerprint"


def _candidate_priority(item: Dict[str, Any]) -> int:
    return {
        "local_file": 50,
        "wechat_product_signal": 40,
        "wechat_analysis_candidate": 38,
        "curated_preview": 30,
        "url_candidate": 20,
    }.get(str(item.get("source_kind") or ""), 0)


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


def _source_ref(item: Dict[str, Any]) -> Dict[str, str]:
    return {
        "source_kind": str(item.get("source_kind") or ""),
        "title": str(item.get("title") or ""),
        "url": str(item.get("url") or ""),
        "path": str(item.get("path") or ""),
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
