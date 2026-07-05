#!/usr/bin/env python3
"""Preview-only composer for 4.4 curated external narrative paragraphs."""

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

from curated_external_viewpoint_narrative import (  # noqa: E402
    build_viewpoint_narrative,
    heuristic_narrative_composer,
    llm_narrative_composer_factory,
)


DEFAULT_OUTPUT = Path("/tmp/{stock}_viewpoint_narrative_preview.md")
DEFAULT_JSON_OUTPUT = Path("/tmp/{stock}_viewpoint_narrative.json")


def _is_rendered_markdown_baseline(text: str) -> bool:
    return any(marker in text for marker in ("## 四、深度分析", "### 4.4", "## 引用来源"))


def _validate_output_path(path_str: str, repo_root: Path) -> Path:
    path = Path(path_str).expanduser().resolve()
    if path.is_relative_to(repo_root):
        raise ValueError("output path must not resolve under the repository")
    tmp_roots = (Path("/tmp").resolve(), Path("/private/tmp").resolve())
    if not any(path.parent == root or path.parent.is_relative_to(root) for root in tmp_roots):
        raise ValueError("output path must resolve under /tmp or /private/tmp")
    return path


def _build_composer(args: argparse.Namespace):
    if args.composer == "heuristic":
        return heuristic_narrative_composer

    api_key = os.environ.get(args.llm_api_key_env, "")
    if not api_key:
        raise ValueError(
            f"--composer llm requires an LLM API key in the "
            f"{args.llm_api_key_env} environment variable"
        )
    if not args.llm_model or not args.llm_base_url:
        raise ValueError("--composer llm requires --llm-model and --llm-base-url")

    return llm_narrative_composer_factory(
        model=args.llm_model,
        base_url=args.llm_base_url,
        api_key=api_key,
        prompt_path=args.prompt,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--digest-json", required=True, help="Validated viewpoint digest JSON.")
    parser.add_argument("--baseline-synthesis-file", required=True, help="Canonical baseline synthesis text.")
    parser.add_argument("--stock", required=True, help="Stock name.")
    parser.add_argument("--output", default="", help="Markdown output path, default /tmp/<stock>...")
    parser.add_argument("--json-output", default="", help="JSON output path, default /tmp/<stock>...")
    parser.add_argument("--composer", choices=["heuristic", "llm"], default="llm")
    parser.add_argument("--llm-model", default="", help="OpenAI-compatible model name.")
    parser.add_argument("--llm-base-url", default="", help="OpenAI-compatible base URL.")
    parser.add_argument("--llm-api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--prompt", default="", help="Optional prompt template path.")
    args = parser.parse_args(argv)

    baseline_path = Path(args.baseline_synthesis_file)
    if not baseline_path.exists():
        print(f"[Error] baseline file not found: {baseline_path}", file=sys.stderr)
        return 1
    baseline_text = baseline_path.read_text(encoding="utf-8")
    if _is_rendered_markdown_baseline(baseline_text):
        print("[Error] baseline input looks like a rendered report; use canonical synthesis text", file=sys.stderr)
        return 1

    digest_path = Path(args.digest_json)
    if not digest_path.exists():
        print(f"[Error] digest file not found: {digest_path}", file=sys.stderr)
        return 1
    digest = json.loads(digest_path.read_text(encoding="utf-8"))

    output = Path(args.output) if args.output else Path(str(DEFAULT_OUTPUT).replace("{stock}", args.stock))
    json_output = (
        Path(args.json_output)
        if args.json_output
        else Path(str(DEFAULT_JSON_OUTPUT).replace("{stock}", args.stock))
    )
    try:
        output = _validate_output_path(str(output), REPO_ROOT)
        json_output = _validate_output_path(str(json_output), REPO_ROOT)
        composer = _build_composer(args)
    except ValueError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        return 1

    result = build_viewpoint_narrative(
        digest,
        baseline_text,
        composer=composer,
        stock_name=args.stock,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result.get("preview_markdown") or "", encoding="utf-8")
    json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "schema_version": result.get("schema_version"),
        "status": result.get("status"),
        "stock_name": result.get("stock_name"),
        "paragraphs_count": result.get("paragraphs_count"),
        "stats": result.get("stats"),
        "json_output_path": str(json_output),
        "markdown_output_path": str(output),
        "wrote_repo_path": False,
        "wrote_knowledge": False,
        "connected_synthesis": False,
        "connected_scoring": False,
        "connected_risk": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
