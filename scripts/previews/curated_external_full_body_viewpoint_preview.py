#!/usr/bin/env python3
"""Preview the canonical v3 external evidence pack outside the repository."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR / "utils"))

from curated_external_full_body_viewpoint_claims import (  # noqa: E402
    build_curated_external_argument_pack,
    build_source_packets,
    llm_topic_narrative_composer_factory,
    llm_unit_selector_factory,
    write_curated_external_argument_pack,
)


DEFAULT_PACK_OUTPUT = Path("/tmp/{stock}-curated-external-argument-pack-v3.json")


def _validate_output_path(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if path.is_relative_to(REPO_ROOT) or not any(path.parent.is_relative_to(root) for root in (Path("/tmp"), Path("/private/tmp"))):
        raise ValueError("pack output must resolve under /tmp or /private/tmp, outside the repository")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-jsonl", required=True)
    parser.add_argument("--baseline-synthesis-file", required=True)
    parser.add_argument("--stock", required=True)
    parser.add_argument("--pack-output", default="")
    parser.add_argument("--llm-model", required=True)
    parser.add_argument("--llm-base-url", required=True)
    parser.add_argument("--llm-api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--max-sources", type=int, default=10)
    parser.add_argument("--max-api-retries", type=int, default=2)
    args = parser.parse_args(argv)

    baseline_path = Path(args.baseline_synthesis_file)
    if not baseline_path.exists() or any(marker in baseline_path.read_text(encoding="utf-8") for marker in ("## 四、深度分析", "### 4.4", "## 引用来源")):
        print("[Error] baseline input must be existing canonical synthesis text", file=sys.stderr)
        return 1
    try:
        output = _validate_output_path(args.pack_output or str(DEFAULT_PACK_OUTPUT).replace("{stock}", args.stock))
    except ValueError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        return 1
    if not (api_key := os.environ.get(args.llm_api_key_env, "")):
        print(f"[Error] {args.llm_api_key_env} is required", file=sys.stderr)
        return 1
    packets = build_source_packets(args.source_jsonl, stock_name=args.stock, max_sources=args.max_sources)
    if not packets:
        print("[Error] no source packets found", file=sys.stderr)
        return 1
    selector = llm_unit_selector_factory(
        args.llm_model, args.llm_base_url, api_key, stock_name=args.stock,
        max_api_retries=args.max_api_retries,
    )
    topic_composer = llm_topic_narrative_composer_factory(
        args.llm_model, args.llm_base_url, api_key,
    )
    pack = build_curated_external_argument_pack(
        packets, baseline_path.read_text(encoding="utf-8"), selector=selector,
        stock_name=args.stock, topic_narrative_composer=topic_composer,
    )
    write_curated_external_argument_pack(pack, output)
    print(json.dumps({
        "schema_version": pack.get("schema_version"), "status": pack.get("status"),
        "stock_name": pack.get("stock_name"), "cards_count": len(pack.get("cards") or []),
        "topic_narrative_status": (pack.get("topic_narratives") or {}).get("status", "missing"),
        "topic_narrative_group_count": len((pack.get("topic_narratives") or {}).get("groups") or []),
        "pack_output_path": str(output), "wrote_repo_path": False, "wrote_knowledge": False,
        "connected_synthesis": False,
    }, ensure_ascii=False, indent=2))
    return 0 if pack.get("status") == "ready" and pack.get("cards") else 1


if __name__ == "__main__":
    raise SystemExit(main())
