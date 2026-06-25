"""Build a preview-only curated external analysis pack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "utils"))

from curated_external_analysis_pack import (  # noqa: E402
    DEFAULT_OUTPUT_PATH,
    write_curated_external_analysis_preview,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a preview-only pack from explicit URLs and local long-form materials."
    )
    parser.add_argument("--url-list", default="", help="Text/Markdown file containing explicit URLs.")
    parser.add_argument("--materials-dir", default="", help="Directory containing .md/.txt/.html curated materials.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Markdown preview output path.")
    parser.add_argument("--max-item-chars", type=int, default=6000, help="Maximum preview characters per item.")
    args = parser.parse_args(argv)

    summary = write_curated_external_analysis_preview(
        url_list_path=args.url_list or None,
        materials_dir=args.materials_dir or None,
        output_path=args.output,
        max_item_chars=args.max_item_chars,
    )

    payload = {
        "status": summary.get("status"),
        "preview_path": summary.get("preview_path"),
        "counts": summary.get("counts", {}),
        "errors_count": len(summary.get("errors", []) or []),
        "items_count": len(summary.get("items", []) or []),
        "wrote_knowledge": False,
        "connected_synthesis": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
