"""Build a preview-only curated external candidate discovery report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "utils"))

from curated_external_candidate_discovery import (  # noqa: E402
    DEFAULT_DISCOVERY_JSONL_PATH,
    DEFAULT_DISCOVERY_PREVIEW_PATH,
    write_curated_external_candidate_discovery_preview,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a preview-only candidate pool from existing external material inputs."
    )
    parser.add_argument("--url-list", default="", help="Text/Markdown file containing explicit candidate URLs.")
    parser.add_argument("--materials-dir", default="", help="Directory containing local .md/.txt/.html materials.")
    parser.add_argument("--wechat-selector-file", default="", help="JSON/JSONL output from the WeChat selector.")
    parser.add_argument("--curated-preview-file", default="", help="JSON/JSONL curated preview summary/items.")
    parser.add_argument("--since-date", default="", help="Keep dated candidates on or after YYYY-MM-DD.")
    parser.add_argument(
        "--theme-keywords",
        default="",
        help="Comma/newline separated stock theme keywords used for relevance scoring/filtering.",
    )
    parser.add_argument(
        "--min-theme-score",
        type=int,
        default=0,
        help="Drop candidates whose theme relevance score is below this threshold.",
    )
    parser.add_argument("--output", default=str(DEFAULT_DISCOVERY_PREVIEW_PATH), help="Markdown preview output path.")
    parser.add_argument("--jsonl-output", default=str(DEFAULT_DISCOVERY_JSONL_PATH), help="JSONL candidate output path.")
    parser.add_argument("--max-item-chars", type=int, default=6000, help="Maximum preview characters per item.")
    args = parser.parse_args(argv)

    summary = write_curated_external_candidate_discovery_preview(
        url_list_path=args.url_list or None,
        materials_dir=args.materials_dir or None,
        wechat_selector_file=args.wechat_selector_file or None,
        curated_preview_file=args.curated_preview_file or None,
        since_date=args.since_date or None,
        theme_keywords=args.theme_keywords or None,
        min_theme_score=args.min_theme_score,
        output_path=args.output,
        jsonl_output_path=args.jsonl_output,
        max_item_chars=args.max_item_chars,
    )

    payload = {
        "status": summary.get("status"),
        "preview_path": summary.get("preview_path"),
        "jsonl_path": summary.get("jsonl_path"),
        "counts": summary.get("counts", {}),
        "items_count": len(summary.get("items", []) or []),
        "deduped_count": len(summary.get("deduped_sources", []) or []),
        "wrote_knowledge": False,
        "connected_synthesis": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
