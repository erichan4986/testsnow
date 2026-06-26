#!/usr/bin/env python3
"""Build preview-only evidence cards for curated external synthesis items."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent / "utils"))

from curated_external_evidence_cards import (  # noqa: E402
    DEFAULT_MAX_EXCERPT_CHARS,
    build_curated_external_evidence_cards,
    build_curated_external_evidence_cards_markdown,
)


DEFAULT_INPUT = Path("/tmp/curated_external_to_synthesis_items.jsonl")
DEFAULT_OUTPUT = Path("/tmp/curated_external_evidence_cards_preview.md")
DEFAULT_CARDS_JSON = Path("/tmp/curated_external_evidence_cards.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthesis-items-jsonl", default=str(DEFAULT_INPUT), help="Input synthesis display-only JSON/JSONL.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Markdown preview output path.")
    parser.add_argument("--cards-json", default=str(DEFAULT_CARDS_JSON), help="Structured cards JSON output path.")
    parser.add_argument("--stock", default="", help="Stock name for preview metadata.")
    parser.add_argument("--max-excerpt-chars", type=int, default=DEFAULT_MAX_EXCERPT_CHARS, help="Maximum chars per excerpt.")
    args = parser.parse_args(argv)

    summary = build_curated_external_evidence_cards(
        args.synthesis_items_jsonl,
        stock_name=args.stock,
        max_excerpt_chars=args.max_excerpt_chars,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_curated_external_evidence_cards_markdown(summary), encoding="utf-8")

    cards_path = Path(args.cards_json)
    cards_path.parent.mkdir(parents=True, exist_ok=True)
    cards_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    payload = {
        "status": summary.get("status"),
        "preview_path": str(output_path),
        "cards_json_path": str(cards_path),
        "cards_count": len(summary.get("cards", []) or []),
        "excerpt_packs_count": len(summary.get("excerpt_packs", []) or []),
        "deduped_count": len(summary.get("deduped_sources", []) or []),
        "excerpt_budget": summary.get("excerpt_budget", {}),
        "wrote_knowledge": False,
        "connected_synthesis": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
