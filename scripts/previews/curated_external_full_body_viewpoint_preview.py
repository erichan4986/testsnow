#!/usr/bin/env python3
"""Preview the canonical v4 external evidence pack outside the repository."""

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
    build_external_argument_pack_from_sources,
    build_source_documents,
    llm_unit_selector_factory,
    write_external_argument_pack_v4,
)


DEFAULT_PACK_OUTPUT = Path("/tmp/{stock}-curated-external-argument-pack-v4.json")


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
    parser.add_argument("--max-sources", type=int, default=0)
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
    documents = build_source_documents(
        args.source_jsonl,
        stock_name=args.stock,
        max_sources=args.max_sources or None,
    )
    if not documents:
        print("[Error] no source documents found", file=sys.stderr)
        return 1
    selector = llm_unit_selector_factory(
        args.llm_model, args.llm_base_url, api_key, stock_name=args.stock,
    )
    pack = build_external_argument_pack_from_sources(
        documents,
        baseline_path.read_text(encoding="utf-8"),
        selector=selector,
        stock_name=args.stock,
    )
    write_external_argument_pack_v4(pack, output)
    print(json.dumps({
        "schema_version": pack.get("schema_version"), "status": pack.get("status"),
        "stock_name": pack.get("stock_name"), "cards_count": len(pack.get("cards") or []),
        "narrative_plan_status": "ready" if pack.get("narrative_plan") else "missing",
        "narrative_plan_group_count": len((pack.get("narrative_plan") or {}).get("groups") or []),
        "pack_output_path": str(output), "wrote_repo_path": False, "wrote_knowledge": False,
        "connected_synthesis": False,
    }, ensure_ascii=False, indent=2))
    return 0 if pack.get("status") == "ready" and pack.get("cards") else 1


if __name__ == "__main__":
    raise SystemExit(main())
