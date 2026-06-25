"""Cross-source dedupe for display-only synthesis material.

This helper is intentionally conservative: it only removes exact URL matches
after normalization or near-identical text fingerprints. It does not rewrite
content and does not affect canonical synthesis unless the caller explicitly
uses the returned list.
"""

from __future__ import annotations

import hashlib
import re
import urllib.parse
from typing import Any, Dict, List, Tuple

if __name__.startswith("utils."):
    from .source_adapter import SynthesisItem
else:
    from source_adapter import SynthesisItem


def dedupe_synthesis_display_items(items: List[SynthesisItem]) -> Tuple[List[SynthesisItem], List[Dict[str, Any]]]:
    """Return display items with cross-platform duplicates removed.

    Higher-credit items win.  When credit ties, the first item wins so existing
    source ordering remains stable.
    """
    kept_items: List[SynthesisItem] = []
    seen: Dict[str, int] = {}
    records: List[Dict[str, Any]] = []

    for item in items:
        keys = _item_keys(item)
        duplicate_key = next((key for key in keys if key in seen), "")
        if not duplicate_key:
            kept_items.append(item)
            for key in keys:
                seen[key] = len(kept_items) - 1
            continue

        kept_index = seen[duplicate_key]
        kept = kept_items[kept_index]
        reason = "normalized_url" if duplicate_key.startswith("url:") else "content_fingerprint"
        if _item_rank(item) > _item_rank(kept):
            kept_items[kept_index] = item
            for key in _item_keys(kept):
                seen.pop(key, None)
            for key in keys:
                seen[key] = kept_index
            records.append(
                {
                    "reason": reason,
                    "kept": _item_ref(item),
                    "duplicate": _item_ref(kept),
                }
            )
        else:
            records.append(
                {
                    "reason": reason,
                    "kept": _item_ref(kept),
                    "duplicate": _item_ref(item),
                }
            )

    return kept_items, records


def _item_keys(item: SynthesisItem) -> List[str]:
    keys: List[str] = []
    url_key = _normalized_url_key(item.url)
    if url_key:
        keys.append(f"url:{url_key}")
    content_key = _content_fingerprint(item.content)
    if content_key:
        keys.append(f"content:{content_key}")
    return keys


def _item_rank(item: SynthesisItem) -> int:
    extra = item.extra or {}
    credit = _as_int(extra.get("source_credit"), _inferred_credit(item.source_platform))
    return credit


def _inferred_credit(source_platform: str) -> int:
    platform = str(source_platform or "")
    if "公告" in platform:
        return 95
    if "定期报告" in platform:
        return 75
    if "券商研报" in platform:
        return 72
    if "行业研报" in platform:
        return 70
    if "新闻" in platform:
        return 65
    return 50


def _item_ref(item: SynthesisItem) -> Dict[str, Any]:
    extra = item.extra or {}
    return {
        "title": item.title,
        "source_platform": item.source_platform,
        "source_type": extra.get("source_type", ""),
        "source_credit": _as_int(extra.get("source_credit"), _inferred_credit(item.source_platform)),
        "url": item.url,
    }


def _normalized_url_key(url: str) -> str:
    parsed = urllib.parse.urlparse((url or "").strip())
    if not parsed.netloc:
        return ""
    host = re.sub(r"^(?:www|m)\.", "", parsed.netloc.lower())
    path = urllib.parse.unquote(parsed.path or "/").rstrip("/") or "/"
    noise_params = {"spm", "from", "source", "share", "share_source", "sharefrom", "hmsr", "hmpl", "hmcu", "hmkw", "hmci"}
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
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
    if len(normalized) < 16:
        return ""
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
