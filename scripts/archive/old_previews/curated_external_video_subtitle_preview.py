"""Build a preview-only pack from explicit video subtitle URLs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "utils"))

from curated_external_video_subtitles import (  # noqa: E402
    DEFAULT_VIDEO_SUBTITLE_JSON_PATH,
    DEFAULT_VIDEO_SUBTITLE_PREVIEW_PATH,
    write_video_subtitle_preview,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a preview-only subtitle pack from explicit YouTube/Bilibili URLs."
    )
    parser.add_argument("--url-list", required=True, help="Text/Markdown file containing explicit video URLs.")
    parser.add_argument("--output", default=str(DEFAULT_VIDEO_SUBTITLE_PREVIEW_PATH), help="Markdown preview output path.")
    parser.add_argument("--json-output", default=str(DEFAULT_VIDEO_SUBTITLE_JSON_PATH), help="Structured JSON output path.")
    parser.add_argument("--max-item-chars", type=int, default=6000, help="Maximum subtitle preview characters per item.")
    parser.add_argument("--timeout", type=int, default=90, help="yt-dlp timeout per video in seconds.")
    args = parser.parse_args(argv)

    summary = write_video_subtitle_preview(
        url_list_path=args.url_list,
        output_path=args.output,
        json_output_path=args.json_output,
        max_item_chars=args.max_item_chars,
        timeout=args.timeout,
    )

    payload = {
        "status": summary.get("status"),
        "preview_path": summary.get("preview_path"),
        "json_output_path": summary.get("json_output_path"),
        "counts": summary.get("counts", {}),
        "items_count": len(summary.get("items", []) or []),
        "errors_count": len(summary.get("errors", []) or []),
        "wrote_knowledge": False,
        "connected_synthesis": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
