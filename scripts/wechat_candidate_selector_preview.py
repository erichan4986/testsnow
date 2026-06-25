"""Build a preview-only selection report for WeChat article candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent / "utils"))

from wechat_candidate_selector import (  # noqa: E402
    DEFAULT_WECHAT_CANDIDATE_PREVIEW_PATH,
    load_stock_config,
    write_wechat_candidate_preview,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-file", required=True, help="JSON/JSONL/text file of WeChat candidate metadata.")
    parser.add_argument("--stock", default="", help="Stock name/code used to load dynamic theme terms from config.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "stocks.json"), help="stocks.json path.")
    parser.add_argument("--theme-term", action="append", default=[], help="Extra company/product/industry theme term.")
    parser.add_argument("--output", default=str(DEFAULT_WECHAT_CANDIDATE_PREVIEW_PATH), help="Markdown preview output path.")
    args = parser.parse_args(argv)

    stock_config = load_stock_config(args.stock, args.config)
    summary = write_wechat_candidate_preview(
        candidate_file=args.candidate_file,
        output_path=args.output,
        stock_config=stock_config,
        extra_theme_terms=args.theme_term,
    )
    payload = {
        "status": summary.get("status"),
        "preview_path": summary.get("preview_path"),
        "counts": summary.get("counts", {}),
        "items_count": len(summary.get("items", []) or []),
        "theme_terms_count": len(summary.get("theme_terms", []) or []),
        "wrote_knowledge": False,
        "connected_synthesis": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
