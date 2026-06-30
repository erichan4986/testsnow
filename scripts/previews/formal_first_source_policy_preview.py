#!/usr/bin/env python3
"""Preview formal-first canonical source coverage from cached report input."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR / "utils"))

from report_skills.synthesis_skills import SynthesisSkill  # noqa: E402
from skill_pipeline import SkillContext  # noqa: E402


DEFAULT_OUTPUT = Path("/tmp/{stock}_formal_first_source_policy_preview.json")


def _validate_output_path(path_str: str, repo_root: Path) -> Path:
    path = Path(path_str).expanduser().resolve()
    if path.is_relative_to(repo_root):
        raise ValueError("output path must not resolve under the repository; write under /tmp")
    tmp_roots = (Path("/tmp").resolve(), Path("/private/tmp").resolve())
    if not any(path.parent == root or path.parent.is_relative_to(root) for root in tmp_roots):
        raise ValueError("output path must resolve under /tmp or /private/tmp")
    return path


def _load_report_input(path: str, stock_name: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_data = payload.get("raw_data") if isinstance(payload, dict) else {}
    stock_raw = {}
    if isinstance(raw_data, dict):
        candidate = raw_data.get(stock_name)
        if isinstance(candidate, dict):
            stock_raw = candidate
        elif all(k in raw_data for k in ("reports", "announcements", "zhihu")):
            stock_raw = raw_data

    stocks_data = payload.get("stocks_data") if isinstance(payload, dict) else {}
    posts = []
    if isinstance(stocks_data, dict):
        candidate = stocks_data.get(stock_name)
        if isinstance(candidate, list):
            posts = candidate
    return stock_raw, posts


def _platform_counts(items: list[Any]) -> dict[str, int]:
    counter = Counter()
    for item in items:
        platform = str(getattr(item, "source_platform", "") or "unknown").strip() or "unknown"
        counter[platform] += 1
    return dict(sorted(counter.items()))


def _audit(report_input_json: str, stock_name: str, min_formal_items: int) -> dict[str, Any]:
    stock_raw, keep_posts = _load_report_input(report_input_json, stock_name)
    formal_skill = SynthesisSkill(canonical_synthesis_source_policy="formal_first")
    legacy_skill = SynthesisSkill(canonical_synthesis_source_policy="legacy_mixed")
    formal_ctx = SkillContext(input={"canonical_synthesis_source_policy": "formal_first"})
    legacy_ctx = SkillContext(input={"canonical_synthesis_source_policy": "legacy_mixed"})

    formal_items = formal_skill._build_synthesis_items(stock_raw, keep_posts, ctx=formal_ctx)
    legacy_items = legacy_skill._build_synthesis_items(stock_raw, keep_posts, ctx=legacy_ctx)
    zhihu_items = stock_raw.get("zhihu", {}).get("report_items", []) if isinstance(stock_raw, dict) else []
    excluded_social_counts = {
        "xueqiu": len(keep_posts),
        "zhihu": len(zhihu_items) if isinstance(zhihu_items, list) else 0,
    }
    status = "ok" if len(formal_items) >= min_formal_items else "formal_sources_insufficient"
    return {
        "schema_version": "formal_first_source_policy_preview.v1",
        "stock_name": stock_name,
        "status": status,
        "min_formal_items": min_formal_items,
        "formal_items_count": len(formal_items),
        "legacy_items_count": len(legacy_items),
        "excluded_social_counts": excluded_social_counts,
        "formal_source_platform_counts": _platform_counts(formal_items),
        "legacy_source_platform_counts": _platform_counts(legacy_items),
        "wrote_repo_path": False,
        "connected_synthesis": False,
        "connected_scoring": False,
        "connected_risk": False,
        "called_llm": False,
        "accessed_network": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-input-json", required=True, help="Cached data/raw/report_input_*.json file.")
    parser.add_argument("--stock", required=True, help="Stock name.")
    parser.add_argument("--output", default="", help="JSON output path (default /tmp/<stock>_...).")
    parser.add_argument("--min-formal-items", type=int, default=3)
    args = parser.parse_args(argv)

    output = Path(args.output) if args.output else Path(str(DEFAULT_OUTPUT).replace("{stock}", args.stock))
    try:
        output = _validate_output_path(str(output), REPO_ROOT)
        payload = _audit(args.report_input_json, args.stock, args.min_formal_items)
    except Exception as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        return 2

    output.parent.mkdir(parents=True, exist_ok=True)
    payload["output_path"] = str(output)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
