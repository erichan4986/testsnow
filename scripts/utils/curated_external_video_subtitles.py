"""Preview-only video subtitle reader for curated external materials.

Only explicit video URLs are processed. The module writes local previews and
never connects video subtitles to Knowledge, canonical synthesis, scoring, or
risk logic.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List

if __name__.startswith("utils."):
    from .curated_external_analysis_pack import DEFAULT_MAX_ITEM_CHARS, load_url_list
else:
    from curated_external_analysis_pack import DEFAULT_MAX_ITEM_CHARS, load_url_list


DEFAULT_VIDEO_SUBTITLE_PREVIEW_PATH = Path("/tmp/curated_external_video_subtitle_preview.md")
DEFAULT_VIDEO_SUBTITLE_JSON_PATH = Path("/tmp/curated_external_video_subtitle_items.json")
DEFAULT_SUBTITLE_LANGS = ("zh-Hans", "zh-CN", "zh", "en")


def build_video_subtitle_preview(
    *,
    url_list_path: str | Path | None,
    fetch_subtitle: Callable[..., Dict[str, Any]] = None,
    max_item_chars: int = DEFAULT_MAX_ITEM_CHARS,
    timeout: int = 90,
) -> Dict[str, Any]:
    """Build a preview summary from explicit YouTube/Bilibili video URLs."""
    fetcher = fetch_subtitle or fetch_video_subtitle_with_ytdlp
    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    for entry in load_url_list(url_list_path):
        url = str(entry.get("url") or "")
        if not _is_supported_video_url(url):
            errors.append({"url": url, "error": "unsupported_video_url"})
            continue
        try:
            fetched = fetcher(url, timeout=timeout)
        except Exception as exc:
            errors.append({"url": url, "error": str(exc)[:200]})
            continue
        content = clean_subtitle_text(str(fetched.get("content") or ""))
        if not content:
            errors.append({"url": url, "error": "empty_subtitle"})
            continue
        items.append(
            _build_video_item(
                title=str(entry.get("title") or fetched.get("title") or _url_title(url)),
                url=url,
                content=_truncate(content, max_item_chars),
                platform=_video_platform(url),
                author=str(fetched.get("author") or fetched.get("channel") or ""),
                publish_time=str(fetched.get("publish_time") or fetched.get("upload_date") or ""),
                language=str(fetched.get("language") or ""),
            )
        )

    return {
        "status": "ok" if items else "empty",
        "items": items,
        "counts": dict(Counter(item.get("source_kind", "") for item in items)),
        "errors": errors,
        "wrote_knowledge": False,
        "connected_synthesis": False,
    }


def build_video_subtitle_preview_markdown(summary: Dict[str, Any]) -> str:
    """Render a video subtitle preview as Markdown."""
    items = summary.get("items", []) or []
    lines = [
        "# Video Subtitle Preview",
        "",
        "> Preview-only：仅处理明确给定的视频 URL；不写 Knowledge，不接 synthesis，不进入评分或风险评分。",
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
        lines.extend(["## Errors", ""])
        for error in errors:
            lines.append(f"- {error.get('url', '')}: {error.get('error', '')}")
        lines.append("")

    if items:
        lines.extend(["## Items", ""])
        for index, item in enumerate(items, start=1):
            lines.extend(_render_item_lines(index, item))

    return "\n".join(lines).rstrip() + "\n"


def write_video_subtitle_preview(
    *,
    url_list_path: str | Path | None,
    output_path: str | Path = DEFAULT_VIDEO_SUBTITLE_PREVIEW_PATH,
    json_output_path: str | Path = DEFAULT_VIDEO_SUBTITLE_JSON_PATH,
    fetch_subtitle: Callable[..., Dict[str, Any]] = None,
    max_item_chars: int = DEFAULT_MAX_ITEM_CHARS,
    timeout: int = 90,
) -> Dict[str, Any]:
    """Write Markdown and JSON previews for explicit video subtitle URLs."""
    summary = build_video_subtitle_preview(
        url_list_path=url_list_path,
        fetch_subtitle=fetch_subtitle,
        max_item_chars=max_item_chars,
        timeout=timeout,
    )
    markdown_path = Path(output_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(build_video_subtitle_preview_markdown(summary), encoding="utf-8")

    json_path = Path(json_output_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(
            {
                "status": summary.get("status"),
                "counts": summary.get("counts", {}),
                "items": summary.get("items", []) or [],
                "errors": summary.get("errors", []) or [],
                "wrote_knowledge": False,
                "connected_synthesis": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return {**summary, "preview_path": str(markdown_path), "json_output_path": str(json_path)}


def fetch_video_subtitle_with_ytdlp(url: str, timeout: int = 90) -> Dict[str, Any]:
    """Fetch subtitles for one explicit video URL via yt-dlp.

    This is intentionally URL-driven and performs no search.
    """
    with tempfile.TemporaryDirectory(prefix="video-subtitles-") as tmp:
        output_template = str(Path(tmp) / "%(id)s.%(ext)s")
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--no-simulate",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            ",".join(DEFAULT_SUBTITLE_LANGS),
            "--sub-format",
            "vtt",
            "--dump-json",
            "-o",
            output_template,
            url,
        ]
        try:
            result = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
        except FileNotFoundError as exc:
            raise RuntimeError("yt-dlp not found") from exc
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "yt-dlp failed").strip()[:200])

        metadata = _load_ytdlp_metadata(result.stdout)
        subtitle_files = sorted(Path(tmp).glob("*.vtt"), key=lambda path: _subtitle_file_rank(path.name))
        if not subtitle_files:
            raise RuntimeError("no usable subtitles")
        subtitle_path = subtitle_files[0]
        return {
            "title": metadata.get("title", ""),
            "author": metadata.get("channel") or metadata.get("uploader") or "",
            "publish_time": metadata.get("upload_date", ""),
            "language": _subtitle_language(subtitle_path.name),
            "content": subtitle_path.read_text(encoding="utf-8", errors="replace"),
        }


def clean_subtitle_text(text: str) -> str:
    """Strip VTT/SRT timing and repeated caption lines."""
    lines: List[str] = []
    previous = ""
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.upper().startswith("WEBVTT") or line.upper().startswith("NOTE"):
            continue
        if "-->" in line:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\{\\[^}]+\}", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line == previous:
            continue
        lines.append(line)
        previous = line
    return "\n".join(lines).strip()


def _build_video_item(
    *,
    title: str,
    url: str,
    content: str,
    platform: str,
    author: str = "",
    publish_time: str = "",
    language: str = "",
) -> Dict[str, Any]:
    return {
        "source_kind": "video_subtitle",
        "source_type": "video_subtitle",
        "title": title,
        "url": url,
        "content": content,
        "content_preview": content,
        "platform": platform,
        "author": author,
        "publish_time": publish_time,
        "language": language,
        "quality_action": "preview_only",
        "knowledge_eligible": False,
        "synthesis_eligible": False,
        "scoring_eligible": False,
        "risk_score_eligible": False,
    }


def _render_item_lines(index: int, item: Dict[str, Any]) -> List[str]:
    lines = [
        f"### {index}. {item.get('title') or item.get('url') or 'video'}",
        "",
        f"- source_kind: `{item.get('source_kind', '')}`",
        f"- quality_action: `{item.get('quality_action', '')}`",
        f"- knowledge_eligible: `{str(bool(item.get('knowledge_eligible'))).lower()}`",
        f"- synthesis_eligible: `{str(bool(item.get('synthesis_eligible'))).lower()}`",
        f"- scoring_eligible: `{str(bool(item.get('scoring_eligible'))).lower()}`",
        f"- risk_score_eligible: `{str(bool(item.get('risk_score_eligible'))).lower()}`",
    ]
    for key in ("platform", "author", "publish_time", "language"):
        if item.get(key):
            lines.append(f"- {key}: `{item.get(key)}`")
    if item.get("url"):
        lines.append(f"- url: {item.get('url')}")
    lines.extend(["", str(item.get("content") or "").strip(), ""])
    return lines


def _is_supported_video_url(url: str) -> bool:
    return _video_platform(url) in {"youtube", "bilibili"}


def _video_platform(url: str) -> str:
    lower = str(url or "").lower()
    if "youtube.com" in lower or "youtu.be" in lower:
        return "youtube"
    if "bilibili.com" in lower:
        return "bilibili"
    return "unknown"


def _load_ytdlp_metadata(stdout: str) -> Dict[str, Any]:
    for line in reversed(str(stdout or "").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _subtitle_file_rank(name: str) -> tuple[int, str]:
    lower = name.lower()
    for rank, language in enumerate(DEFAULT_SUBTITLE_LANGS):
        if f".{language.lower()}." in lower:
            return (rank, name)
    return (len(DEFAULT_SUBTITLE_LANGS), name)


def _subtitle_language(name: str) -> str:
    match = re.search(r"\.([A-Za-z-]+)\.vtt$", name)
    return match.group(1) if match else ""


def _url_title(url: str) -> str:
    digest = hashlib.sha1(str(url or "").encode("utf-8")).hexdigest()[:8]
    return f"video-{digest}"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."
