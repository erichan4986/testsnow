"""Download explicit WeChat article URLs through wechat-article-exporter.

This script is preview-only. It writes local export files and a review Markdown
preview; it does not write Knowledge, connect synthesis, scoring, or risk.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WECHAT_EXPORT_OUTPUT_DIR = Path("/tmp/wechat_exports")
sys.path.insert(0, str(Path(__file__).parent / "utils"))

from curated_external_analysis_pack import load_url_list  # noqa: E402
from wechat_export_reader import (  # noqa: E402
    DEFAULT_WECHAT_EXPORT_PREVIEW_PATH,
    write_wechat_export_preview,
)
from wechat_exporter_client import (  # noqa: E402
    DEFAULT_WECHAT_EXPORTER_BASE_URL,
    DownloadedWechatArticle,
    WechatExporterClient,
    WechatExporterError,
)


def main(argv: List[str] | None = None) -> int:
    _load_dotenv_if_available()
    args = _parse_args(argv)

    output_dir = Path(args.output_dir)
    if args.stock:
        output_dir = output_dir / _safe_segment(args.stock)
    exports_dir = Path(args.exports_dir) if args.exports_dir else output_dir

    downloaded_count = 0
    download_errors = []
    if args.url_list:
        auth_key = args.auth_key or os.environ.get("WECHAT_EXPORTER_AUTH_KEY", "")
        base_url = args.base_url or os.environ.get("WECHAT_EXPORTER_BASE_URL", DEFAULT_WECHAT_EXPORTER_BASE_URL)
        client = WechatExporterClient(base_url=base_url, auth_key=auth_key)
        output_dir.mkdir(parents=True, exist_ok=True)
        url_entries = load_url_list(args.url_list)[: max(0, int(args.max_downloads))]
        for index, entry in enumerate(url_entries):
            url = entry.get("url", "")
            try:
                article = client.download_article(url, fmt=args.format, timeout=args.timeout)
            except WechatExporterError as exc:
                download_errors.append({"url": url, "error": str(exc)[:200]})
                if args.stop_on_error:
                    break
                continue
            _write_downloaded_article(article, output_dir=output_dir, fallback_title=entry.get("title", ""))
            downloaded_count += 1
            if args.delay_seconds > 0 and index < len(url_entries) - 1:
                time.sleep(float(args.delay_seconds))
        exports_dir = output_dir

    summary = write_wechat_export_preview(
        exports_dir=exports_dir,
        output_path=args.preview_output,
        max_item_chars=args.max_item_chars,
    )
    payload = {
        "status": summary.get("status"),
        "preview_path": summary.get("preview_path"),
        "exports_dir": str(exports_dir),
        "downloaded_count": downloaded_count,
        "max_downloads": args.max_downloads,
        "delay_seconds": args.delay_seconds,
        "download_errors_count": len(download_errors),
        "items_count": len(summary.get("items", []) or []),
        "counts": summary.get("counts", {}),
        "deduped_count": len(summary.get("deduped_sources", []) or []),
        "wrote_knowledge": False,
        "connected_synthesis": False,
    }
    if download_errors:
        payload["download_errors"] = download_errors
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not download_errors else 1


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url-list", default="", help="Text/Markdown file containing explicit mp.weixin.qq.com article URLs.")
    parser.add_argument("--exports-dir", default="", help="Existing local export directory to preview without API download.")
    parser.add_argument("--output-dir", default=str(DEFAULT_WECHAT_EXPORT_OUTPUT_DIR), help="Directory for downloaded exports. Defaults to /tmp to avoid accidental commits.")
    parser.add_argument("--stock", default="", help="Optional stock subdirectory under output-dir.")
    parser.add_argument("--preview-output", default=str(DEFAULT_WECHAT_EXPORT_PREVIEW_PATH), help="Markdown preview output path.")
    parser.add_argument("--base-url", default="", help="Wechat exporter base URL. Defaults to WECHAT_EXPORTER_BASE_URL or public site.")
    parser.add_argument("--auth-key", default="", help="Wechat exporter auth key. Prefer WECHAT_EXPORTER_AUTH_KEY in .env.")
    parser.add_argument("--format", default="markdown", choices=["markdown", "json", "text", "html"], help="Exporter download format.")
    parser.add_argument("--timeout", type=int, default=20, help="Per-request timeout seconds.")
    parser.add_argument("--max-downloads", type=int, default=5, help="Maximum article downloads per run. Default: 5.")
    parser.add_argument("--delay-seconds", type=float, default=3.0, help="Delay between article downloads. Default: 3 seconds.")
    parser.add_argument("--max-item-chars", type=int, default=6000, help="Maximum preview characters per item.")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop after the first download error.")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.url_list and not args.exports_dir:
        parser.error("one of --url-list or --exports-dir is required")
    return args


def _write_downloaded_article(
    article: DownloadedWechatArticle,
    *,
    output_dir: Path,
    fallback_title: str = "",
) -> Path:
    title = article.title or fallback_title or _url_tail(article.url) or "wechat-article"
    metadata = dict(article.metadata or {})
    metadata.setdefault("title", title)
    metadata.setdefault("url", article.url)
    metadata.setdefault("exported_at", datetime.now().isoformat(timespec="seconds"))
    metadata.setdefault("source", "wechat_article_exporter")

    suffix = {
        "markdown": ".md",
        "json": ".json",
        "text": ".txt",
        "html": ".html",
    }.get(article.fmt, ".md")
    filename = f"{_safe_segment(title)[:64]}-{hashlib.sha1(article.url.encode('utf-8')).hexdigest()[:10]}{suffix}"
    path = output_dir / filename
    if article.fmt == "json":
        payload = {**metadata, "content": article.content}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return path

    frontmatter = "\n".join(f"{key}: {str(value).replace(chr(10), ' ')}" for key, value in metadata.items() if value)
    path.write_text(f"---\n{frontmatter}\n---\n\n{article.content.strip()}\n", encoding="utf-8")
    return path


def _safe_segment(value: str) -> str:
    segment = re.sub(r"[\\/:*?\"<>|\s]+", "_", str(value or "").strip()).strip("_")
    return segment or "wechat"


def _url_tail(url: str) -> str:
    return Path(str(url).rstrip("/")).name


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(PROJECT_ROOT / ".env")


if __name__ == "__main__":
    raise SystemExit(main())
