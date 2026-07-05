"""Read local wechat-article-exporter outputs as preview-only materials."""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SUPPORTED_WECHAT_EXPORT_EXTENSIONS = {".md", ".markdown", ".txt", ".html", ".htm", ".json"}
DEFAULT_WECHAT_EXPORT_PREVIEW_PATH = Path("/tmp/wechat_export_preview.md")
DEFAULT_MAX_ITEM_CHARS = 6000


def read_wechat_exports(
    exports_dir: str | Path | None,
    *,
    max_chars: int = DEFAULT_MAX_ITEM_CHARS,
) -> List[Dict[str, Any]]:
    """Read supported files exported from wechat-article-exporter."""
    if not exports_dir:
        return []
    root = Path(exports_dir)
    if not root.exists() or not root.is_dir():
        return []

    items: List[Dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=_export_sort_key):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_WECHAT_EXPORT_EXTENSIONS:
            continue
        item = _read_one_export(path, max_chars=max_chars)
        if item:
            items.append(item)
    return items


def build_wechat_export_preview(
    exports_dir: str | Path | None,
    *,
    max_item_chars: int = DEFAULT_MAX_ITEM_CHARS,
) -> Dict[str, Any]:
    items = read_wechat_exports(exports_dir, max_chars=max_item_chars)
    items, deduped_sources = _dedupe_items(items)
    return {
        "status": "ok" if items else "empty",
        "items": items,
        "counts": _counts_by_source_kind(items),
        "deduped_sources": deduped_sources,
        "errors": [],
    }


def build_wechat_export_preview_markdown(summary: Dict[str, Any]) -> str:
    items = summary.get("items", []) or []
    lines = [
        "# WeChat Export Preview",
        "",
        "> Preview-only：不写 Knowledge，不接 canonical synthesis，不进入评分或风险评分。",
        "> 公众号文章只作为精选外部分析材料，后续需经人工确认再决定是否进入报告 display 层。",
        "",
        "## Summary",
        "",
        f"- status: `{summary.get('status', '')}`",
        f"- items: `{len(items)}`",
    ]
    for source_kind, count in sorted((summary.get("counts") or {}).items()):
        lines.append(f"- {source_kind}: `{count}`")
    lines.append("")

    deduped_sources = summary.get("deduped_sources", []) or []
    if deduped_sources:
        lines.extend(["## Deduped Sources", ""])
        for record in deduped_sources:
            lines.append(
                f"- reason: `{record.get('reason', '')}` | kept: {_source_label(record.get('kept') or {})} | duplicate: {_source_label(record.get('duplicate') or {})}"
            )
        lines.append("")

    lines.extend(["## Items", ""])
    for index, item in enumerate(items, start=1):
        title = item.get("title") or item.get("path") or f"wechat-export-{index}"
        lines.extend(
            [
                f"### {index}. {title}",
                "",
                f"- source_kind: `{item.get('source_kind', '')}`",
                f"- quality_action: `{item.get('quality_action', '')}`",
                f"- author: `{item.get('author', '')}`",
                f"- publish_time: `{item.get('publish_time', '')}`",
                f"- knowledge_eligible: `{str(bool(item.get('knowledge_eligible'))).lower()}`",
                f"- synthesis_eligible: `{str(bool(item.get('synthesis_eligible'))).lower()}`",
                f"- scoring_eligible: `{str(bool(item.get('scoring_eligible'))).lower()}`",
                f"- risk_score_eligible: `{str(bool(item.get('risk_score_eligible'))).lower()}`",
            ]
        )
        if item.get("url"):
            lines.append(f"- url: {item.get('url')}")
        if item.get("path"):
            lines.append(f"- path: `{item.get('path')}`")
        lines.extend(["", _truncate(str(item.get("content", "")).strip(), DEFAULT_MAX_ITEM_CHARS), ""])

    return "\n".join(lines).rstrip() + "\n"


def write_wechat_export_preview(
    *,
    exports_dir: str | Path | None,
    output_path: str | Path = DEFAULT_WECHAT_EXPORT_PREVIEW_PATH,
    max_item_chars: int = DEFAULT_MAX_ITEM_CHARS,
) -> Dict[str, Any]:
    summary = build_wechat_export_preview(exports_dir, max_item_chars=max_item_chars)
    markdown = build_wechat_export_preview_markdown(summary)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return {**summary, "preview_path": str(path)}


def _read_one_export(path: Path, *, max_chars: int) -> Optional[Dict[str, Any]]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    suffix = path.suffix.lower()
    metadata: Dict[str, Any] = {}
    content = raw
    if suffix == ".json":
        metadata, content = _parse_json_export(raw)
    elif suffix in {".md", ".markdown"}:
        metadata, content = _parse_markdown_export(raw)
    elif suffix in {".html", ".htm"}:
        content = _html_to_text(raw)

    content = _clean_content(content)
    if not content:
        return None

    title = str(metadata.get("title") or path.name).strip()
    author = str(metadata.get("author") or metadata.get("account") or metadata.get("source_account") or "").strip()
    publish_time = str(metadata.get("publish_time") or metadata.get("date") or metadata.get("created_at") or "").strip()
    url = str(metadata.get("url") or metadata.get("original_url") or metadata.get("link") or "").strip()
    return _build_item(
        title=title,
        content=_truncate(content, max_chars),
        path=str(path),
        author=author,
        publish_time=publish_time,
        url=url,
    )


def _export_sort_key(path: Path) -> tuple[int, str]:
    suffix_order = {
        ".md": 0,
        ".markdown": 0,
        ".json": 1,
        ".txt": 2,
        ".html": 3,
        ".htm": 3,
    }
    return (suffix_order.get(path.suffix.lower(), 99), path.name)


def _build_item(
    *,
    title: str,
    content: str,
    path: str,
    author: str = "",
    publish_time: str = "",
    url: str = "",
) -> Dict[str, Any]:
    return {
        "source_kind": "wechat_export",
        "title": title,
        "author": author,
        "publish_time": publish_time,
        "url": url,
        "path": path,
        "content": content,
        "quality_action": "preview_only",
        "display_only": True,
        "knowledge_eligible": False,
        "synthesis_eligible": False,
        "scoring_eligible": False,
        "risk_score_eligible": False,
    }


def _parse_markdown_export(text: str) -> Tuple[Dict[str, Any], str]:
    metadata: Dict[str, Any] = {}
    match = re.match(r"\A---\n(.*?)\n---\n?", text, flags=re.DOTALL)
    if not match:
        return metadata, text
    for raw_line in match.group(1).splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            metadata[key] = value
    return metadata, text[match.end() :]


def _parse_json_export(text: str) -> Tuple[Dict[str, Any], str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}, text
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]
    if not isinstance(data, dict):
        return {}, text
    content = _first_text(data, ("markdown", "content", "text", "html", "article_content", "articleContent"))
    if "<" in content and ">" in content:
        content = _html_to_text(content)
    return dict(data), content


def _first_text(data: Dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _clean_content(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"\r\n?", "\n", text)
    drop_patterns = (
        r"^\s*微信扫一扫.*$",
        r"^\s*继续滑动看下一个.*$",
        r"^\s*在小说阅读器.*$",
        r"^\s*去阅读\s*$",
        r"^\s*公众号记得加星标.*$",
        r"^\s*阅读原文\s*$",
        r"^\s*相关推荐\s*$",
    )
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if any(re.search(pattern, stripped) for pattern in drop_patterns):
            continue
        if "javascript:void" in stripped:
            continue
        if "{" in stripped and "}" in stripped and re.search(r"\b(max-width|margin|display|height|width):", stripped):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _html_to_text(text: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(text or "")
    parser.close()
    return html.unescape(" ".join(parser.parts))


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        if tag.lower() in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.parts.append(data.strip())


def _dedupe_items(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    kept: List[Dict[str, Any]] = []
    seen: Dict[str, int] = {}
    records: List[Dict[str, Any]] = []
    for item in items:
        keys = _item_keys(item)
        duplicate_key = next((key for key in keys if key in seen), "")
        if not duplicate_key:
            kept.append(item)
            for key in keys:
                seen[key] = len(kept) - 1
            continue
        kept_item = kept[seen[duplicate_key]]
        records.append(
            {
                "reason": "normalized_url" if duplicate_key.startswith("url:") else "content_fingerprint",
                "kept": _source_ref(kept_item),
                "duplicate": _source_ref(item),
            }
        )
    return kept, records


def _item_keys(item: Dict[str, Any]) -> List[str]:
    keys: List[str] = []
    url_key = _normalized_url_key(str(item.get("url") or ""))
    if url_key:
        keys.append(f"url:{url_key}")
    fingerprint = _content_fingerprint(str(item.get("content") or ""))
    if fingerprint:
        keys.append(f"content:{fingerprint}")
    return keys


def _normalized_url_key(url: str) -> str:
    parsed = urllib.parse.urlparse((url or "").strip())
    if not parsed.netloc:
        return ""
    host = re.sub(r"^(?:www|m)\.", "", parsed.netloc.lower())
    path = urllib.parse.unquote(parsed.path or "/").rstrip("/") or "/"
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
    filtered_query = [
        (key, value)
        for key, value in query_pairs
        if not key.lower().startswith("utm_") and key.lower() not in {"from", "source", "share"}
    ]
    query = urllib.parse.urlencode(filtered_query)
    return f"{host}{path}" + (f"?{query}" if query else "")


def _content_fingerprint(content: str) -> str:
    normalized = re.sub(r"https?://\S+", " ", content or "")
    normalized = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", normalized)
    normalized = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", normalized)
    normalized = re.sub(r"[`*_#>\-|:：，,。.!！?？、；;（）()\[\]{}\"'“”‘’]", " ", normalized)
    normalized = re.sub(r"\s+", "", normalized).lower()
    if len(normalized) < 6:
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
    title = item.get("title") or item.get("url") or item.get("path") or item.get("source_kind") or "unknown"
    location = item.get("url") or item.get("path") or ""
    if location:
        return f"{title} ({location})"
    return str(title)


def _counts_by_source_kind(items: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        key = str(item.get("source_kind") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."
