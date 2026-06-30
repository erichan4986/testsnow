#!/usr/bin/env python3
"""Render a curated external analysis report section from candidate JSONL.

This is a preview-only local helper. It does not write Knowledge, does not
connect to canonical synthesis, and does not affect scoring or risk pipelines.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "utils"))

from reporter.sections.curated_external_analysis_renderer import (  # noqa: E402
    CuratedExternalAnalysisRenderer,
)


DEFAULT_OUTPUT_PATH = Path("/tmp/curated_external_report_section_preview.md")


def _read_json_or_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    text = source.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("{") or text.startswith("["):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if payload is not None:
            raw_items = payload.get("items", []) if isinstance(payload, dict) else payload
            return [item for item in raw_items if isinstance(item, dict)]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-jsonl", required=True, help="Candidate discovery JSON/JSONL input path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Markdown section output path.")
    parser.add_argument("--stock", default="", help="Optional stock name for summary metadata.")
    parser.add_argument("--max-display-items", type=int, default=6, help="Display cap for lower-priority items.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    items = _read_json_or_jsonl(args.candidate_jsonl)
    ctx = {
        "curated_external_analysis_items": items,
        "curated_external_analysis_max_display_items": args.max_display_items,
    }
    markdown = CuratedExternalAnalysisRenderer().render(ctx)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    counts = dict(Counter(str(item.get("source_kind") or "") for item in items))
    payload = {
        "stock": args.stock,
        "status": "ok" if items else "empty",
        "rendered": bool(markdown.strip()),
        "items_count": len(items),
        "counts": counts,
        "output_path": str(output_path),
        "wrote_knowledge": False,
        "connected_synthesis": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
