#!/usr/bin/env python3
"""Preview-only CLI for WeChat targeted article discovery.

Searches public WeChat accounts and articles for a configured stock, classifies
candidates, deduplicates, and writes a preview Markdown + JSONL.  All output is
preview-only and is explicitly excluded from Knowledge, canonical synthesis,
scoring, and risk pipelines.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "utils"))

from wechat_exporter_client import WechatExporterClient
from wechat_targeted_discovery import (
    DEFAULT_ENV_PATH,
    add_preview_fields,
    build_markdown,
    build_search_keywords,
    deduplicate,
    discover_articles,
    download_articles,
    load_auth_key,
    load_stock_config,
)

# Expose under a short name so tests can monkeypatch the env path.
ENV_PATH = DEFAULT_ENV_PATH


def parse_since_date(value: str | None) -> date:
    if value:
        return date.fromisoformat(value)
    return date.today() - timedelta(days=180)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", required=True, help="Stock name or code (e.g., 圣邦股份).")
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "config" / "stocks.json"),
        help="Path to stocks.json config file.",
    )
    parser.add_argument("--keyword", action="append", default=[], help="Additional search keyword (repeatable).")
    parser.add_argument("--account", action="append", default=[], help="Additional target account keyword (repeatable).")
    parser.add_argument("--since-date", default="", help="ISO date cutoff; defaults to 180 days ago.")
    parser.add_argument("--max-accounts", type=int, default=80, help="Maximum accounts to query.")
    parser.add_argument("--max-pages-per-account", type=int, default=3, help="Max pages per account.")
    parser.add_argument("--download-top", type=int, default=0, help="Download top N article bodies (0 = disabled).")
    parser.add_argument(
        "--download-dir",
        default="",
        help="Directory for downloaded article bodies; defaults to /tmp/wechat_targeted_discovery_exports/<stock>.",
    )
    parser.add_argument("--output", default="", help="Markdown output path.")
    parser.add_argument("--jsonl-output", default="", help="JSONL output path.")
    parser.add_argument("--base-url", default="", help="WeChat exporter base URL.")
    parser.add_argument("--auth-key", default="", help="WeChat exporter auth key; falls back to .env.")
    parser.add_argument("--delay-seconds", type=float, default=1.2, help="Delay between search/list calls.")
    parser.add_argument("--download-delay-seconds", type=float, default=3.2, help="Delay between article downloads.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    since_date = parse_since_date(args.since_date or None)
    to_date = date.today()

    stock_config = load_stock_config(args.stock, args.config)
    if not stock_config:
        print(json.dumps({"error": f"Stock '{args.stock}' not found in {args.config}"}, ensure_ascii=False), file=sys.stderr)
        return 1

    stock_name = str(stock_config.get("name") or args.stock)
    keywords = build_search_keywords(stock_config, extra_keywords=args.keyword)
    target_accounts = list(args.account) if args.account else []

    # Auth key handling: CLI arg > .env; never logged.
    auth_key = args.auth_key or load_auth_key(ENV_PATH)

    client_kwargs: dict[str, str] = {"auth_key": auth_key}
    if args.base_url:
        client_kwargs["base_url"] = args.base_url
    client = WechatExporterClient(**client_kwargs)

    errors: list[str] = []

    raw_articles = discover_articles(
        client,
        stock_config,
        since_date,
        max_accounts=args.max_accounts,
        max_pages_per_account=args.max_pages_per_account,
        extra_keywords=args.keyword,
        extra_accounts=target_accounts,
        delay_seconds=args.delay_seconds,
        errors=errors,
    )

    summary = deduplicate(raw_articles, stock_config=stock_config)
    summary["raw_count"] = len(raw_articles)
    total_seen = summary["unique_count"] + summary["duplicate_count"]
    summary["duplicate_rate"] = summary["duplicate_count"] / total_seen if total_seen else 0.0

    # Apply preview-only isolation flags to all retained items.
    for item in summary["items"]:
        add_preview_fields(item)

    download_dir = args.download_dir or f"/tmp/wechat_targeted_discovery_exports/{stock_name}"
    downloaded: list[dict[str, str]] = []
    if args.download_top > 0:
        downloaded = download_articles(
            client,
            summary["items"],
            download_top=args.download_top,
            download_dir=download_dir,
            download_delay_seconds=args.download_delay_seconds,
            errors=errors,
        )

    output_path = args.output or f"/tmp/{stock_name}_wechat_targeted_discovery_preview.md"
    jsonl_path = args.jsonl_output or f"/tmp/{stock_name}_wechat_targeted_discovery_candidates.jsonl"

    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)

    md = build_markdown(
        summary,
        stock_name=stock_name,
        keywords=keywords,
        accounts=list({a.get("account", "") for a in raw_articles}),
        errors=errors,
        downloaded=downloaded,
        since_date=since_date,
        to_date=to_date,
    )
    output_path_obj.write_text(md, encoding="utf-8")

    jsonl_path_obj = Path(jsonl_path)
    jsonl_path_obj.parent.mkdir(parents=True, exist_ok=True)
    # Main JSONL only writes retained (non-drop, non-duplicate) candidates.
    retained = [it for it in summary["items"] if it.get("classification") != "drop"]
    jsonl_path_obj.write_text(
        "\n".join(json.dumps(it, ensure_ascii=False) for it in retained) + ("\n" if retained else ""),
        encoding="utf-8",
    )

    payload = {
        "stock": stock_name,
        "status": "ok",
        "preview_path": str(output_path_obj),
        "jsonl_path": str(jsonl_path_obj),
        "raw_count": len(raw_articles),
        "unique_count": summary["unique_count"],
        "duplicate_count": summary["duplicate_count"],
        "duplicate_rate": summary["duplicate_rate"],
        "counts": summary["counts"],
        "download_count": len(downloaded),
        "errors": len(errors),
        "wrote_knowledge": False,
        "connected_synthesis": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
