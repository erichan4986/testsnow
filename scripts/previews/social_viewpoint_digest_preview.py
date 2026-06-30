#!/usr/bin/env python3
"""Preview-only CLI for cached Xueqiu/Zhihu viewpoints into 4.4 digest."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR / "utils"))

from curated_external_full_body_viewpoint_claims import (  # noqa: E402
    THEME_PROFILES,
    build_viewpoint_digest,
    heuristic_extractor,
    llm_extractor_factory,
    multipass_llm_extractor_factory,
)
from social_viewpoint_source_packets import build_social_source_packets  # noqa: E402


DEFAULT_OUTPUT = Path("/tmp/{stock}_social_viewpoint_digest_preview.md")
DEFAULT_JSON_OUTPUT = Path("/tmp/{stock}_social_viewpoint_claims.json")


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


def _build_extractor(args: argparse.Namespace) -> Any:
    if args.extractor == "heuristic":
        return heuristic_extractor

    api_key = os.environ.get(args.llm_api_key_env, "")
    if not api_key:
        raise ValueError(
            f"--extractor {args.extractor} requires an LLM API key in the "
            f"{args.llm_api_key_env} environment variable"
        )
    if not args.llm_model or not args.llm_base_url:
        raise ValueError(f"--extractor {args.extractor} requires --llm-model and --llm-base-url")

    if args.extractor == "llm-multipass":
        return multipass_llm_extractor_factory(
            model=args.llm_model,
            base_url=args.llm_base_url,
            api_key=api_key,
            stock_name=args.stock,
            max_source_chars=args.max_source_chars,
            max_sources=args.max_sources,
            prompt_path=args.prompt,
            max_api_retries=args.max_api_retries,
        )

    return llm_extractor_factory(
        model=args.llm_model,
        base_url=args.llm_base_url,
        api_key=api_key,
        stock_name=args.stock,
        max_source_chars=args.max_source_chars,
        max_sources=args.max_sources,
        prompt_path=args.prompt,
        max_api_retries=args.max_api_retries,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-input-json", required=True, help="Cached data/raw/report_input_*.json file.")
    parser.add_argument("--baseline-synthesis-file", required=True, help="Canonical baseline synthesis text file.")
    parser.add_argument("--stock", required=True, help="Stock name.")
    parser.add_argument("--output", default="", help="Markdown output path (default /tmp/<stock>_...).")
    parser.add_argument("--json-output", default="", help="JSON output path (default /tmp/<stock>_...).")
    parser.add_argument(
        "--extractor",
        choices=["heuristic", "llm", "llm-multipass"],
        default="llm-multipass",
        help="Extractor to use (default: llm-multipass).",
    )
    parser.add_argument("--llm-model", default="", help="LLM model name.")
    parser.add_argument("--llm-base-url", default="", help="LLM API base URL.")
    parser.add_argument("--llm-api-key-env", default="DEEPSEEK_API_KEY", help="Environment variable holding key.")
    parser.add_argument("--prompt", default="", help="Optional custom prompt template.")
    parser.add_argument("--min-display-claims", type=int, default=2)
    parser.add_argument("--max-sources", type=int, default=8)
    parser.add_argument("--max-source-chars", type=int, default=12000)
    parser.add_argument("--min-source-chars", type=int, default=180)
    parser.add_argument("--max-api-retries", type=int, default=2)
    parser.add_argument("--theme-profile", default="", help="Optional THEME_PROFILES key.")
    parser.add_argument("--min-theme-coverage", type=float, default=None)
    args = parser.parse_args(argv)

    baseline_path = Path(args.baseline_synthesis_file)
    if not baseline_path.exists():
        print(f"[Error] baseline file not found: {baseline_path}", file=sys.stderr)
        return 1
    baseline_text = baseline_path.read_text(encoding="utf-8")
    if _is_rendered_markdown_baseline(baseline_text):
        print("[Error] baseline input looks like a rendered report; use canonical synthesis text", file=sys.stderr)
        return 1

    output = Path(args.output) if args.output else Path(str(DEFAULT_OUTPUT).replace("{stock}", args.stock))
    json_output = (
        Path(args.json_output)
        if args.json_output
        else Path(str(DEFAULT_JSON_OUTPUT).replace("{stock}", args.stock))
    )
    try:
        output = _validate_output_path(str(output), REPO_ROOT)
        json_output = _validate_output_path(str(json_output), REPO_ROOT)
        extractor = _build_extractor(args)
    except ValueError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        return 1

    source_packets = build_social_source_packets(
        args.report_input_json,
        stock_name=args.stock,
        max_sources=args.max_sources,
        max_source_chars=None,
        min_content_chars=args.min_source_chars,
    )
    if not source_packets:
        print("[Error] no usable social source packets found", file=sys.stderr)
        return 1

    theme_profile = None
    if args.theme_profile:
        theme_profile = THEME_PROFILES.get(args.theme_profile)
        if not theme_profile:
            print(f"[Error] unknown theme profile: {args.theme_profile}", file=sys.stderr)
            return 1
    if args.min_theme_coverage is not None and not args.theme_profile:
        print("[Error] --min-theme-coverage requires --theme-profile", file=sys.stderr)
        return 1

    digest = build_viewpoint_digest(
        source_packets,
        baseline_text,
        extractor=extractor,
        min_display_claims=args.min_display_claims,
        stock_name=args.stock,
        theme_profile=theme_profile,
        min_theme_coverage=args.min_theme_coverage,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(digest.get("preview_markdown") or "", encoding="utf-8")
    json_output.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "schema_version": digest.get("schema_version"),
        "status": digest.get("status"),
        "stock_name": digest.get("stock_name"),
        "claims_count": digest.get("claims_count"),
        "source_packets_count": len(source_packets),
        "min_display_claims": digest.get("min_display_claims"),
        "stats": digest.get("stats"),
        "json_output_path": str(json_output),
        "markdown_output_path": str(output),
        "wrote_repo_path": False,
        "wrote_knowledge": False,
        "connected_synthesis": False,
        "connected_scoring": False,
        "connected_risk": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if digest.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
