"""Preview-only curated external analysis pack helpers.

The pack is intentionally detached from Knowledge, synthesis, scoring, and risk
logic. It reads user-curated long-form materials and renders a local preview so
the material quality can be inspected before any future integration.
"""

from __future__ import annotations

import html
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
    fetch_text: Callable[..., str] = fetch_jina_text,
    max_item_chars: int = DEFAULT_MAX_ITEM_CHARS,
    timeout: int = 20,
) -> Dict[str, Any]:
    """Build a preview summary from explicit URLs and local files."""
    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    for entry in load_url_list(url_list_path):
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
    return {
        "status": "ok" if items else "empty",
        "items": items,
        "counts": _counts_by_source_kind(items),
        "errors": errors,
    }


def build_curated_external_analysis_preview_markdown(summary: Dict[str, Any]) -> str:
    """Render preview Markdown."""
    items = summary.get("items", []) or []
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

    lines.extend(["## Items", ""])
    for index, item in enumerate(items, start=1):
        title = item.get("title") or item.get("url") or item.get("path") or f"item-{index}"
        lines.extend(
            [
                f"### {index}. {title}",
                "",
                f"- source_kind: `{item.get('source_kind', '')}`",
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
        lines.extend(["", _truncate(str(item.get("content", "")).strip(), DEFAULT_MAX_ITEM_CHARS), ""])

    return "\n".join(lines).rstrip() + "\n"


def write_curated_external_analysis_preview(
    *,
    url_list_path: str | Path | None = None,
    materials_dir: str | Path | None = None,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    fetch_text: Callable[..., str] = fetch_jina_text,
    max_item_chars: int = DEFAULT_MAX_ITEM_CHARS,
) -> Dict[str, Any]:
    summary = build_curated_external_analysis_preview(
        url_list_path=url_list_path,
        materials_dir=materials_dir,
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
