#!/usr/bin/env python3
"""Lightweight single-stock Agent-Reach smoke validation.

Runs only:
- agent_reach_query_skill
- agent_reach_fetch_skill
- agent_reach_quality_skill

Does NOT run:
- Full stock report pipeline
- PerStockReporter
- ZhihuCollector
- KnowledgeSynthesizer / LLM synthesis
- PDF export
- Report assembly
- Xueqiu / CDP / Playwright detail pages

Usage:
    python3 scripts/smoke_agent_reach.py --stock 黑芝麻智能
    python3 scripts/smoke_agent_reach.py --stock 黑芝麻智能 --write-audit
    python3 scripts/smoke_agent_reach.py --stock 黑芝麻智能 --json
    python3 scripts/smoke_agent_reach.py --stock 黑芝麻智能 --dry-run
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Import only Agent-Reach skills and the pipeline context.
# Intentionally avoid PerStockReporter, ZhihuCollector, KnowledgeSynthesizer,
# PDF export, and report assembly to keep this a lightweight smoke test.
sys.path.insert(0, str(Path(__file__).parent))

from utils.skill_pipeline import SkillContext
from utils.report_skills.agent_reach_query_skill import agent_reach_query_skill
from utils.report_skills.agent_reach_skill import agent_reach_fetch_skill
from utils.report_skills.agent_reach_quality_skill import agent_reach_quality_skill


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_stock_config(stock_name: str) -> dict:
    """Load per-stock Agent-Reach config from config/stocks.json."""
    config_path = Path(__file__).parent.parent / "config" / "stocks.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            stocks = json.load(f)
    except Exception as e:
        logger.warning(f"读取 config/stocks.json 失败: {e}")
        return {}

    for stock in stocks:
        if stock.get("name") == stock_name:
            return stock.get("agent_reach", {}) or {}
    return {}


def build_context(stock_name: str, stock_code: str, cfg: dict, date_str: str) -> SkillContext:
    """Build a minimal SkillContext for Agent-Reach smoke run."""
    input_data = {
        "stock_name": stock_name,
        "stock_codes": {stock_name: stock_code},
        "date_str": date_str,
        "enable_agent_reach": cfg.get("enabled", False),
    }

    if cfg.get("enabled", False):
        web_urls = cfg.get("web_urls", []) or cfg.get("urls", [])
        if web_urls:
            input_data["agent_reach_urls"] = web_urls
        rss_feeds = cfg.get("rss_feeds", [])
        if rss_feeds:
            input_data["agent_reach_rss_feeds"] = rss_feeds
        rss_filter_terms = cfg.get("rss_filter_terms", [])
        if rss_filter_terms:
            input_data["agent_reach_rss_filter_terms"] = rss_filter_terms
        official_domains = cfg.get("official_domains", [])
        if official_domains:
            input_data["agent_reach_official_domains"] = official_domains

    return SkillContext(input=input_data)


def run_smoke(
    stock_name: str,
    output_dir: str = "reports",
    date_str: str = None,
    dry_run: bool = False,
    write_audit: bool = False,
) -> dict:
    """Run query/fetch/quality for a single stock and return a compact summary."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    cfg = load_stock_config(stock_name)
    # Derive stock code from config if possible, otherwise empty.
    config_path = Path(__file__).parent.parent / "config" / "stocks.json"
    stock_code = ""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            stocks = json.load(f)
        for stock in stocks:
            if stock.get("name") == stock_name:
                stock_code = stock.get("code", "")
                break
    except Exception:
        pass

    ctx = build_context(stock_name, stock_code, cfg, date_str)

    # Run only the three Agent-Reach skills.
    ctx = agent_reach_query_skill(ctx)
    ctx = agent_reach_fetch_skill(ctx)
    ctx = agent_reach_quality_skill(ctx)

    summary = ctx.get("agent_reach_run_summary", {}) or {}

    # Enrich summary with a few convenience fields for the CLI table.
    quality_summary = ctx.get("agent_reach_quality_summary", {}) or {}
    summary["stock_name"] = stock_name
    summary["date_str"] = date_str
    summary["enabled"] = ctx.get("agent_reach_enabled", False)
    summary["fetch_status"] = ctx.get("agent_reach_status", "")
    summary["quality_status"] = ctx.get("agent_reach_quality_status", "")
    summary["counts"] = quality_summary
    summary["warnings"] = ctx.get("agent_reach_warnings", []) or []

    if write_audit and not dry_run:
        audit_path = write_audit_summary(output_dir, date_str, summary)
        if audit_path:
            summary["audit_path"] = audit_path

    return summary


def write_audit_summary(output_dir: str, date_str: str, summary: dict) -> str:
    """Persist compact Agent-Reach audit summary to sidecar JSON."""
    stock_name = summary.get("stock_name", "")
    if not stock_name:
        return ""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    audit_path = out / f"{stock_name}_{date_str}_agent_reach_smoke.json"

    try:
        audit_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(f"Agent-Reach smoke audit persisted: {audit_path}")
        return str(audit_path)
    except Exception as e:
        logger.warning(f"Agent-Reach smoke audit persistence failed: {e}")
        return ""


def print_summary(summary: dict) -> None:
    """Print a compact status table to stdout."""
    stock = summary.get("stock_name", "")
    enabled = summary.get("enabled", False)
    fetch_status = summary.get("fetch_status", "")
    quality_status = summary.get("quality_status", "")
    counts = summary.get("counts", {})
    warnings = summary.get("warnings", [])
    audit_path = summary.get("audit_path", "")

    queries = summary.get("queries", [])
    query_count = len(queries)

    print("=" * 50)
    print(f"Agent-Reach Smoke: {stock}")
    print("=" * 50)
    print(f"  enabled:        {enabled}")
    print(f"  query count:    {query_count}")
    print(f"  fetch status:   {fetch_status}")
    print(f"  quality status: {quality_status}")
    print(f"  keep:           {counts.get('keep', 0)}")
    print(f"  demote:         {counts.get('demote', 0)}")
    print(f"  discard:        {counts.get('discard', 0)}")
    print(f"  total:          {counts.get('total', 0)}")
    print(f"  warnings:       {len(warnings)}")
    if warnings:
        for w in warnings[:5]:
            print(f"    - {w}")
        if len(warnings) > 5:
            print(f"    ... and {len(warnings) - 5} more")
    if audit_path:
        print(f"  audit path:     {audit_path}")
    print("=" * 50)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="单股票 Agent-Reach smoke 验证")
    parser.add_argument("--stock", required=True, help="目标股票名称，如 '黑芝麻智能'")
    parser.add_argument("--output-dir", default="reports", help="audit JSON 输出目录")
    parser.add_argument("--date", default=None, help="日期字符串，如 20260613")
    parser.add_argument("--write-audit", action="store_true", help="写入 smoke audit JSON")
    parser.add_argument("--dry-run", action="store_true", help="仅打印结果，不写入文件")
    parser.add_argument("--json", action="store_true", help="输出 compact JSON")
    return parser.parse_args([] if argv is None else argv)


def main(argv=None):
    args = _parse_args(argv)

    dry_run = args.dry_run

    summary = run_smoke(
        stock_name=args.stock,
        output_dir=args.output_dir,
        date_str=args.date,
        dry_run=dry_run,
        write_audit=args.write_audit,
    )

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    else:
        print_summary(summary)
    return summary


if __name__ == "__main__":
    main(sys.argv[1:])
