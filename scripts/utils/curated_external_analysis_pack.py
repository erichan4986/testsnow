"""Preview-only curated external analysis pack helpers.

The pack is intentionally detached from Knowledge, synthesis, scoring, and risk
logic. It reads user-curated long-form materials and renders a local preview so
the material quality can be inspected before any future integration.
"""

from __future__ import annotations

import html
import hashlib
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional


SUPPORTED_LOCAL_EXTENSIONS = {".md", ".txt", ".html", ".htm"}
DEFAULT_OUTPUT_PATH = Path("/tmp/curated_external_analysis_preview.md")
DEFAULT_MAX_ITEM_CHARS = 6000


def load_url_list(path: str | Path | None) -> List[Dict[str, str]]:
    """Load explicit URLs from a plain text or Markdown list.

    Each non-empty, non-heading line may be either a bare URL or a labeled line
    such as `title | https://example.com/article`.
    """
    if not path:
        return []
    list_path = Path(path)
    if not list_path.exists():
        return []

    urls: List[Dict[str, str]] = []
    for raw_line in list_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^\s*[-*]\s+", "", line).strip()
        match = re.search(r"https?://\S+", line)
        if not match:
            continue
        url = match.group(0).rstrip("，,。)")
        title = line[: match.start()].strip(" |:-")
        urls.append({"title": title, "url": url})
    return urls


def read_local_materials(materials_dir: str | Path | None, *, max_chars: int = DEFAULT_MAX_ITEM_CHARS) -> List[Dict[str, Any]]:
    """Read supported local long-form materials from a directory."""
    if not materials_dir:
        return []
    root = Path(materials_dir)
    if not root.exists() or not root.is_dir():
        return []

    items: List[Dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_LOCAL_EXTENSIONS:
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        content = _clean_local_content(raw, path.suffix.lower())
        if not content:
            continue
        items.append(
            _build_preview_item(
                source_kind="local_file",
                title=path.name,
                content=_truncate(content, max_chars),
                path=str(path),
            )
        )
    return items


def read_wechat_exports(
    wechat_export_dir: str | Path | None,
    *,
    max_items: Optional[int] = None,
    max_chars: int = DEFAULT_MAX_ITEM_CHARS,
) -> List[Dict[str, Any]]:
    """Read WeChat article exports from a directory.

    Each exported file is expected to have YAML-style frontmatter with at least
    ``title`` and ``url``. The returned items are always tagged as
    ``wechat_product_signal`` and preview-only.
    """
    if not wechat_export_dir:
        return []
    root = Path(wechat_export_dir)
    if not root.exists() or not root.is_dir():
        return []

    items: List[Dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_LOCAL_EXTENSIONS:
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        metadata, body = _parse_frontmatter(raw)
        title = metadata.get("title") or path.stem
        url = metadata.get("url") or ""
        if not url:
            # WeChat exports must have a URL to be useful for preview.
            continue

        suffix = path.suffix.lower()
        if suffix in {".html", ".htm"}:
            body = _html_to_text(body)
        content = _clean_wechat_content(body)
        if not content:
            continue

        item = _build_preview_item(
            source_kind="wechat_product_signal",
            title=title,
            content=_truncate(content, max_chars),
            url=url,
            path=str(path),
        )
        item["source_type"] = "wechat_product_signal"
        item["account"] = metadata.get("account", "")
        item["publish_time"] = metadata.get("publish_time", "")
        item["wechat_action"] = metadata.get("action", "")
        items.append(item)

        if max_items is not None and len(items) >= max_items:
            break
    return items


def _parse_frontmatter(text: str) -> tuple[Dict[str, str], str]:
    """Extract simple ``key: value`` frontmatter and the remaining body."""
    text = text or ""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    metadata: Dict[str, str] = {}
    for line in text[3:end].strip().splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata, text[end + 4 :].lstrip("\n")


def _clean_wechat_content(text: str) -> str:
    """Light cleaning for WeChat exported markdown/html."""
    # Drop CSS rule lines that often appear at the top of exports.
    lines: List[str] = []
    for line in (text or "").splitlines():
        if "{" in line and "}" in line and any(k in line for k in ("max-width", "display", "margin", "padding", "width", "height", "font-size", "color:")):
            continue
        clean_line = line.strip()
        if re.fullmatch(r"(.{2,20})\s+\1\s*(?:;\))?", clean_line):
            continue
        lines.append(line)
    text = "\n".join(lines)

    # Remove markdown images and javascript links.
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[\]\(\s*", "", text)
    text = re.sub(r"\[([^\]]+)\]\(\s*javascript:[^)]*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove HTML tags and standalone URLs.
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"https?://\S+", "", text)

    # Remove common WeChat boilerplate.
    for phrase in (
        "在小说阅读器读本章",
        "去阅读",
        "在小说阅读器中沉浸阅读",
        "点击下方阅读原文",
        "阅读原文",
        "原创",
        "关于圣邦微电子",
        "SG Micro Corp",
        ";)",
    ):
        text = text.replace(phrase, "")
    text = re.sub(r"(?m)^\s*(\S{2,20})[\s\u00a0]+\1\s*$", "", text)

    return _normalize_text(text)


def fetch_jina_text(url: str, timeout: int = 20) -> str:
    """Read one explicit URL through Jina Reader."""
    jina_url = "https://r.jina.ai/" + str(url).strip()
    request = urllib.request.Request(
        jina_url,
        headers={"User-Agent": "Mozilla/5.0 curated-external-analysis-preview"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def build_curated_external_analysis_preview(
    *,
    url_list_path: str | Path | None = None,
    materials_dir: str | Path | None = None,
    wechat_export_dir: str | Path | None = None,
    wechat_max_items: Optional[int] = None,
    fetch_text: Callable[..., str] = fetch_jina_text,
    max_item_chars: int = DEFAULT_MAX_ITEM_CHARS,
    timeout: int = 20,
) -> Dict[str, Any]:
    """Build a preview summary from explicit URLs, local files and WeChat exports."""
    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    deduped_sources: List[Dict[str, Any]] = []

    url_entries, url_deduped_sources = _dedupe_url_entries(load_url_list(url_list_path))
    deduped_sources.extend(url_deduped_sources)

    for entry in url_entries:
        url = entry["url"]
        if _is_video_url(url):
            items.append(
                _build_preview_item(
                    source_kind="video_subtitle_deferred",
                    title=entry.get("title") or _url_title(url),
                    content="视频字幕接口占位：本版本不调用 yt-dlp。",
                    url=url,
                )
            )
            continue
        try:
            content = _clean_jina_text(fetch_text(url, timeout=timeout))
        except Exception as exc:
            errors.append({"url": url, "error": str(exc)[:200]})
            continue
        if not content:
            errors.append({"url": url, "error": "empty_content"})
            continue
        items.append(
            _build_preview_item(
                source_kind="jina_url",
                title=entry.get("title") or _url_title(url),
                content=_truncate(content, max_item_chars),
                url=url,
            )
        )

    items.extend(read_local_materials(materials_dir, max_chars=max_item_chars))
    items.extend(
        read_wechat_exports(
            wechat_export_dir,
            max_items=wechat_max_items,
            max_chars=max_item_chars,
        )
    )
    items, item_deduped_sources = _dedupe_preview_items(items)
    deduped_sources.extend(item_deduped_sources)
    return {
        "status": "ok" if items else "empty",
        "items": items,
        "counts": _counts_by_source_kind(items),
        "errors": errors,
        "deduped_sources": deduped_sources,
    }


def build_curated_external_analysis_preview_markdown(summary: Dict[str, Any]) -> str:
    """Render preview Markdown."""
    items = summary.get("items", []) or []
    wechat_items = [item for item in items if item.get("source_kind") == "wechat_product_signal"]
    curated_items = [item for item in items if item.get("source_kind") != "wechat_product_signal"]

    lines = [
        "# Curated External Analysis Preview",
        "",
        "> Preview-only：不写 Knowledge，不接 synthesis，不进入评分或风险评分。",
        "> 用途是人工检查精选长内容质量，后续再决定是否接入微信导出、视频字幕或报告展示层。",
        "",
        "## Summary",
        "",
        f"- status: `{summary.get('status', '')}`",
        f"- items: `{len(items)}`",
    ]
    for source_kind, count in sorted((summary.get("counts") or {}).items()):
        lines.append(f"- {source_kind}: `{count}`")
    lines.append("")

    errors = summary.get("errors", []) or []
    if errors:
        lines.extend(["## Fetch Errors", ""])
        for error in errors:
            lines.append(f"- {error.get('url', '')}: {error.get('error', '')}")
        lines.append("")

    if curated_items:
        lines.extend(["## Items", ""])
        for index, item in enumerate(curated_items, start=1):
            lines.extend(_render_item_lines(index, item))

    if wechat_items:
        if curated_items:
            lines.append("")
        lines.extend(["## WeChat Product Signals", ""])
        lines.append("> WeChat 源仅用于产品路线观察 / 新品密度，不写 Knowledge，不接 synthesis，不进入评分或风险。")
        lines.append("")
        for index, item in enumerate(wechat_items, start=1):
            lines.extend(_render_item_lines(index, item, prefix="W"))

    deduped_sources = summary.get("deduped_sources", []) or []
    if deduped_sources:
        lines.extend(["", "## Deduped Sources", ""])
        for record in deduped_sources:
            kept = _source_label(record.get("kept") or {})
            duplicate = _source_label(record.get("duplicate") or {})
            lines.append(
                f"- reason: `{record.get('reason', '')}` | kept: {kept} | duplicate: {duplicate}"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_item_lines(index: int, item: Dict[str, Any], prefix: str = "") -> List[str]:
    title = item.get("title") or item.get("url") or item.get("path") or f"item-{index}"
    heading = f"{prefix}{index}. {title}" if prefix else f"{index}. {title}"
    lines: List[str] = [
        f"### {heading}",
        "",
        f"- source_kind: `{item.get('source_kind', '')}`",
    ]
    if "source_type" in item:
        lines.append(f"- source_type: `{item.get('source_type', '')}`")
    lines.extend(
        [
            f"- quality_action: `{item.get('quality_action', '')}`",
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
    if item.get("account"):
        lines.append(f"- account: `{item.get('account')}`")
    if item.get("publish_time"):
        lines.append(f"- publish_time: `{item.get('publish_time')}`")
    lines.extend(["", _truncate(str(item.get("content", "")).strip(), DEFAULT_MAX_ITEM_CHARS), ""])
    return lines


def write_curated_external_analysis_preview(
    *,
    url_list_path: str | Path | None = None,
    materials_dir: str | Path | None = None,
    wechat_export_dir: str | Path | None = None,
    wechat_max_items: Optional[int] = None,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    fetch_text: Callable[..., str] = fetch_jina_text,
    max_item_chars: int = DEFAULT_MAX_ITEM_CHARS,
) -> Dict[str, Any]:
    summary = build_curated_external_analysis_preview(
        url_list_path=url_list_path,
        materials_dir=materials_dir,
        wechat_export_dir=wechat_export_dir,
        wechat_max_items=wechat_max_items,
        fetch_text=fetch_text,
        max_item_chars=max_item_chars,
    )
    markdown = build_curated_external_analysis_preview_markdown(summary)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return {**summary, "preview_path": str(path)}


def _build_preview_item(
    *,
    source_kind: str,
    title: str,
    content: str,
    url: str = "",
    path: str = "",
) -> Dict[str, Any]:
    return {
        "source_kind": source_kind,
        "title": title,
        "url": url,
        "path": path,
        "content": content,
        "quality_action": "preview_only",
        "knowledge_eligible": False,
        "synthesis_eligible": False,
        "scoring_eligible": False,
        "risk_score_eligible": False,
    }


def _dedupe_url_entries(entries: List[Dict[str, str]]) -> tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    kept_entries: List[Dict[str, str]] = []
    seen: Dict[str, Dict[str, str]] = {}
    deduped_sources: List[Dict[str, Any]] = []

    for entry in entries:
        key = _normalized_url_key(entry.get("url", ""))
        if not key:
            kept_entries.append(entry)
            continue
        kept = seen.get(key)
        if kept:
            deduped_sources.append(
                {
                    "reason": "normalized_url",
                    "kept": _url_entry_ref(kept),
                    "duplicate": _url_entry_ref(entry),
                }
            )
            continue
        seen[key] = entry
        kept_entries.append(entry)

    return kept_entries, deduped_sources


def _dedupe_preview_items(items: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    kept_items: List[Dict[str, Any]] = []
    seen: Dict[str, int] = {}
    deduped_sources: List[Dict[str, Any]] = []

    for item in items:
        keys = _item_dedupe_keys(item)
        duplicate_index = next((seen[key] for key in keys if key in seen), None)
        if duplicate_index is None:
            kept_items.append(item)
            for key in keys:
                seen[key] = len(kept_items) - 1
            continue

        kept = kept_items[duplicate_index]
        if _item_priority(item) > _item_priority(kept):
            kept_items[duplicate_index] = item
            for key in _item_dedupe_keys(kept):
                seen.pop(key, None)
            for key in keys:
                seen[key] = duplicate_index
            deduped_sources.append(
                {
                    "reason": _dedupe_reason(item, kept),
                    "kept": _source_ref(item),
                    "duplicate": _source_ref(kept),
                }
            )
            continue

        deduped_sources.append(
            {
                "reason": _dedupe_reason(kept, item),
                "kept": _source_ref(kept),
                "duplicate": _source_ref(item),
            }
        )

    return kept_items, deduped_sources


def _item_dedupe_keys(item: Dict[str, Any]) -> List[str]:
    keys: List[str] = []
    if item.get("url"):
        key = _normalized_url_key(str(item.get("url", "")))
        if key:
            keys.append(f"url:{key}")
    fingerprint = _content_fingerprint(str(item.get("content", "")))
    if fingerprint:
        keys.append(f"content:{fingerprint}")
    return keys


def _dedupe_reason(kept: Dict[str, Any], duplicate: Dict[str, Any]) -> str:
    kept_url = _normalized_url_key(str(kept.get("url", "")))
    duplicate_url = _normalized_url_key(str(duplicate.get("url", "")))
    if kept_url and kept_url == duplicate_url:
        return "normalized_url"
    return "content_fingerprint"


def _item_priority(item: Dict[str, Any]) -> int:
    return {
        "local_file": 30,
        "wechat_product_signal": 25,
        "jina_url": 20,
        "video_subtitle_deferred": 10,
    }.get(str(item.get("source_kind") or ""), 0)


def _url_entry_ref(entry: Dict[str, str]) -> Dict[str, str]:
    return {
        "source_kind": "video_subtitle_deferred" if _is_video_url(entry.get("url", "")) else "jina_url",
        "title": entry.get("title", ""),
        "url": entry.get("url", ""),
        "path": "",
    }


def _source_ref(item: Dict[str, Any]) -> Dict[str, str]:
    return {
        "source_kind": str(item.get("source_kind") or ""),
        "title": str(item.get("title") or ""),
        "url": str(item.get("url") or ""),
        "path": str(item.get("path") or ""),
    }


def _source_label(item: Dict[str, Any]) -> str:
    title = item.get("title") or item.get("url") or item.get("path") or item.get("source_kind") or "unknown"
    source_kind = item.get("source_kind") or "unknown"
    location = item.get("url") or item.get("path") or ""
    if location:
        return f"{title} ({source_kind}: {location})"
    return f"{title} ({source_kind})"


def _normalized_url_key(url: str) -> str:
    parsed = urllib.parse.urlparse((url or "").strip())
    if not parsed.netloc:
        return ""
    host = parsed.netloc.lower()
    host = re.sub(r"^(?:www|m)\.", "", host)
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


def _clean_local_content(text: str, suffix: str) -> str:
    if suffix in {".html", ".htm"}:
        text = _html_to_text(text)
    return _normalize_text(text)


def _clean_jina_text(text: str) -> str:
    text = re.sub(r"(?im)^\s*URL Source:\s*[^\n]*(?:\n|$)", "\n", text or "")
    text = re.sub(r"(?im)^\s*Markdown Content:\s*(?:\n|$)", "\n", text)
    return _normalize_text(text)


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


def _normalize_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def _is_video_url(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return any(domain in host for domain in ("youtube.com", "youtu.be", "bilibili.com"))


def _url_title(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc + parsed.path


def _counts_by_source_kind(items: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        key = str(item.get("source_kind") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts
