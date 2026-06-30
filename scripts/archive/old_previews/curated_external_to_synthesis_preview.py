"""CLI preview adapter: curated external candidates → synthesis display-only items."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "utils"))

from curated_external_to_synthesis_items import (  # noqa: E402
    build_curated_external_synthesis_items,
    build_curated_external_synthesis_markdown,
)


DEFAULT_CANDIDATE_JSONL = Path("/tmp/curated_external_candidate_discovery_candidates.jsonl")
DEFAULT_OUTPUT = Path("/tmp/curated_external_to_synthesis_preview.md")
DEFAULT_JSONL_OUTPUT = Path("/tmp/curated_external_to_synthesis_items.jsonl")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert curated external candidate JSONL into preview-only synthesis display items."
    )
    parser.add_argument(
        "--candidate-jsonl",
        default=str(DEFAULT_CANDIDATE_JSONL),
        help="Input JSON/JSONL file from curated external candidate discovery.",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Markdown preview output path.")
    parser.add_argument("--jsonl-output", default=str(DEFAULT_JSONL_OUTPUT), help="JSONL item output path.")
    parser.add_argument("--stock", default="", help="Stock name for the preview heading.")
    parser.add_argument(
        "--max-items",
        type=int,
        default=0,
        help="Maximum display items to emit (0 = unlimited).",
    )
    args = parser.parse_args(argv)

    summary = build_curated_external_synthesis_items(
        candidate_jsonl_path=args.candidate_jsonl,
        stock_name=args.stock,
        max_items=args.max_items,
    )

    markdown_path = Path(args.output)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(build_curated_external_synthesis_markdown(summary), encoding="utf-8")

    jsonl_path = Path(args.jsonl_output)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in summary.get("items", []) or [])
        + ("\n" if summary.get("items") else ""),
        encoding="utf-8",
    )

    payload = {
        "status": summary.get("status"),
        "preview_path": str(markdown_path),
        "jsonl_path": str(jsonl_path),
        "counts": summary.get("counts", {}),
        "items_count": len(summary.get("items", []) or []),
        "wrote_knowledge": False,
        "connected_synthesis": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
