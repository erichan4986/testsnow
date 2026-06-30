#!/usr/bin/env python3
"""Build a display-only preview of iwencai industry research search results."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UTILS_DIR = PROJECT_ROOT / "scripts" / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from iwencai_industry_research import (  # noqa: E402
    DEFAULT_IWENCAI_BASE_URL,
    DEFAULT_IWENCAI_QUERIES,
    build_iwencai_industry_preview,
    build_iwencai_industry_preview_markdown,
)


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(PROJECT_ROOT / ".env")


def default_output_path() -> Path:
    return Path("/tmp") / "iwencai_industry_research_preview.md"


def write_iwencai_industry_preview(
    *,
    output_path: str | Path,
    api_key: str,
    queries: Iterable[str] = DEFAULT_IWENCAI_QUERIES,
    base_url: str = DEFAULT_IWENCAI_BASE_URL,
    size: int = 50,
    today: Optional[date] = None,
    recent_days: int = 90,
    fallback_days: int = 180,
    min_recent_items: int = 3,
    max_items_per_query: int = 5,
    post: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """Fetch iwencai metadata, write Markdown preview, and return a compact summary."""
    summary = build_iwencai_industry_preview(
        queries=queries,
        api_key=api_key,
        base_url=base_url,
        size=size,
        today=today,
        recent_days=recent_days,
        fallback_days=fallback_days,
        min_recent_items=min_recent_items,
        max_items_per_query=max_items_per_query,
        post=post,
    )
    markdown = build_iwencai_industry_preview_markdown(summary)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")

    selected_count = sum(len(item.get("selected", []) or []) for item in summary.get("queries", []))
    dropped_count = sum(len(item.get("dropped", []) or []) for item in summary.get("queries", []))
    return {
        "preview_path": str(path),
        "query_count": len(summary.get("queries", []) or []),
        "selected_count": selected_count,
        "dropped_count": dropped_count,
        "source_type": "industry_research",
        "knowledge_eligible": False,
        "report_eligible": True,
    }


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", action="append", help="iwencai report-search query. Repeat to pass multiple.")
    parser.add_argument("--output", default=str(default_output_path()), help="Markdown preview output path.")
    parser.add_argument("--api-key", default="", help="Override IWENCAI_API_KEY. Prefer env/.env.")
    parser.add_argument("--base-url", default=DEFAULT_IWENCAI_BASE_URL, help="iwencai base URL.")
    parser.add_argument("--size", type=int, default=50, help="Rows to request per query.")
    parser.add_argument("--recent-days", type=int, default=90, help="Preferred recency window.")
    parser.add_argument("--fallback-days", type=int, default=180, help="Fallback recency window when recent results are sparse.")
    parser.add_argument("--min-recent-items", type=int, default=3, help="Minimum selected items before using fallback window.")
    parser.add_argument("--max-items-per-query", type=int, default=5, help="Maximum selected reports per query.")
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parse_args(argv)
    _load_dotenv_if_available()
    api_key = args.api_key or os.environ.get("IWENCAI_API_KEY", "")
    if not api_key:
        print("IWENCAI_API_KEY is required; set it in the environment or .env", file=sys.stderr)
        return 2

    summary = write_iwencai_industry_preview(
        output_path=args.output,
        api_key=api_key,
        queries=args.query or DEFAULT_IWENCAI_QUERIES,
        base_url=args.base_url,
        size=args.size,
        recent_days=args.recent_days,
        fallback_days=args.fallback_days,
        min_recent_items=args.min_recent_items,
        max_items_per_query=args.max_items_per_query,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
