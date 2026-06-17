#!/usr/bin/env python3
"""Lightweight Agent-Reach -> evidence notes -> claim-risk bridge smoke.

Runs only:
- agent_reach_query_skill
- agent_reach_fetch_skill
- agent_reach_quality_skill
- optional evidence_note_writer_skill
- build_claim_verification_plan
- derive_structured_risk_signals_from_plan

Does NOT run full report generation, LLM synthesis, scoring, charts, PDF export,
Zhihu collection, Xueqiu detail-page fetches, or CDP/Chrome automation.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.claim_risk_signals import derive_structured_risk_signals_from_plan
from utils.claim_verification import build_claim_verification_plan
from utils.report_skills.agent_reach_query_skill import agent_reach_query_skill
from utils.report_skills.agent_reach_quality_skill import agent_reach_quality_skill
from utils.report_skills.agent_reach_skill import agent_reach_fetch_skill
from utils.report_skills.evidence_note_skill import evidence_note_writer_skill
from utils.skill_pipeline import SkillContext


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_stock_config(stock_name: str) -> dict:
    """Load a stock record and its Agent-Reach config from config/stocks.json."""
    config_path = Path(__file__).parent.parent / "config" / "stocks.json"
    try:
        stocks = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"读取 config/stocks.json 失败: {exc}")
        return {}

    for stock in stocks:
        if stock.get("name") == stock_name:
            cfg = dict(stock.get("agent_reach", {}) or {})
            cfg["_stock_code"] = stock.get("code", "")
            return cfg
    return {}


def build_context(
    stock_name: str,
    cfg: dict,
    date_str: str,
    output_dir: str,
    write_evidence_notes: bool,
    evidence_dry_run: bool,
) -> SkillContext:
    """Build the minimal context needed by the bridge smoke path."""
    input_data = {
        "stock_name": stock_name,
        "stock_codes": {stock_name: cfg.get("_stock_code", "")},
        "date_str": date_str,
        "output_dir": output_dir,
        "enable_agent_reach": bool(cfg.get("enabled", False)),
        "enable_evidence_notes": bool(write_evidence_notes),
        "evidence_notes_dry_run": bool(evidence_dry_run),
    }

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

    evidence_cfg = cfg.get("evidence_notes", {}) or {}
    if evidence_cfg.get("base_dir"):
        input_data["knowledge_base_dir"] = evidence_cfg["base_dir"]

    cv_cfg = cfg.get("claim_verification", {}) or {}
    if cv_cfg.get("base_dir"):
        input_data["claim_verification_base_dir"] = cv_cfg["base_dir"]

    return SkillContext(input=input_data)


def _default_knowledge_base(ctx: SkillContext) -> Path:
    base_dir = ctx.get("claim_verification_base_dir") or ctx.get("knowledge_base_dir")
    if not base_dir:
        base_dir = Path(__file__).parent.parent / "knowledge"
    return Path(base_dir)


def _claim_plan_counts(plan) -> dict:
    return {
        "high_credit_claims": len(getattr(plan, "high_credit_claims", []) or []),
        "low_credit_claims": len(getattr(plan, "low_credit_claims", []) or []),
        "verifications": len(getattr(plan, "verifications", []) or []),
        "skipped_files": len(getattr(plan, "skipped_files", []) or []),
    }


def write_audit_summary(output_dir: str, date_str: str, summary: dict) -> str:
    """Write compact bridge smoke audit JSON."""
    stock_name = summary.get("stock_name", "")
    if not stock_name:
        return ""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    audit_path = out / f"{stock_name}_{date_str}_agent_reach_claim_bridge_smoke.json"
    audit_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.info(f"Agent-Reach claim bridge smoke audit persisted: {audit_path}")
    return str(audit_path)


def run_bridge_smoke(
    stock_name: str,
    output_dir: str = "reports",
    date_str: str = None,
    write_evidence_notes: bool = False,
    evidence_dry_run: bool = False,
    write_audit: bool = False,
) -> dict:
    """Run the narrow bridge path and return a compact, content-free summary."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    cfg = load_stock_config(stock_name)
    ctx = build_context(
        stock_name=stock_name,
        cfg=cfg,
        date_str=date_str,
        output_dir=output_dir,
        write_evidence_notes=write_evidence_notes,
        evidence_dry_run=evidence_dry_run,
    )

    ctx = agent_reach_query_skill(ctx)
    ctx = agent_reach_fetch_skill(ctx)
    ctx = agent_reach_quality_skill(ctx)

    if write_evidence_notes:
        ctx = evidence_note_writer_skill(ctx)
    else:
        ctx.set("evidence_note_status", "disabled")
        ctx.set("evidence_note_summary", {
            "written_count": 0,
            "skipped_existing_count": 0,
            "filtered_count": 0,
            "dry_run": True,
        })

    base_dir = _default_knowledge_base(ctx)
    try:
        plan = build_claim_verification_plan(stock_name, base_dir, dry_run=True)
        claim_plan = _claim_plan_counts(plan)
        signals = derive_structured_risk_signals_from_plan(plan)
        claim_error = ""
    except Exception as exc:  # noqa: BLE001
        logger.exception("claim bridge smoke failed")
        claim_plan = {"high_credit_claims": 0, "low_credit_claims": 0, "verifications": 0, "skipped_files": 0}
        signals = []
        claim_error = str(exc)

    quality_summary = ctx.get("agent_reach_quality_summary", {}) or {}
    run_summary = ctx.get("agent_reach_run_summary", {}) or {}
    summary = {
        "stock_name": stock_name,
        "date_str": date_str,
        "enabled": ctx.get("agent_reach_enabled", False),
        "query_count": len(ctx.get("search_queries", []) or []),
        "fetch_status": ctx.get("agent_reach_status", ""),
        "quality_status": ctx.get("agent_reach_quality_status", ""),
        "counts": quality_summary,
        "warnings": ctx.get("agent_reach_warnings", []) or [],
        "evidence_note_status": ctx.get("evidence_note_status", ""),
        "evidence_note_summary": ctx.get("evidence_note_summary", {}) or {},
        "claim_plan": claim_plan,
        "claim_error": claim_error,
        "structured_risk_signals": signals,
        "agent_reach_results": run_summary.get("results", []),
    }

    if write_audit:
        summary["audit_path"] = write_audit_summary(output_dir, date_str, summary)

    return summary


def print_summary(summary: dict) -> None:
    """Print a concise human-readable summary."""
    counts = summary.get("counts", {}) or {}
    evidence = summary.get("evidence_note_summary", {}) or {}
    plan = summary.get("claim_plan", {}) or {}

    print("=" * 64)
    print(f"Agent-Reach Claim Bridge Smoke: {summary.get('stock_name', '')}")
    print("=" * 64)
    print(f"  enabled:              {summary.get('enabled', False)}")
    print(f"  query count:          {summary.get('query_count', 0)}")
    print(f"  fetch status:         {summary.get('fetch_status', '')}")
    print(f"  quality status:       {summary.get('quality_status', '')}")
    print(f"  keep/demote/discard:  {counts.get('keep', 0)}/{counts.get('demote', 0)}/{counts.get('discard', 0)}")
    print(f"  evidence status:      {summary.get('evidence_note_status', '')}")
    print(f"  evidence written:     {evidence.get('written_count', 0)}")
    print(f"  evidence skipped:     {evidence.get('skipped_existing_count', 0)}")
    print(f"  claim high/low/verif: {plan.get('high_credit_claims', 0)}/{plan.get('low_credit_claims', 0)}/{plan.get('verifications', 0)}")
    print(f"  risk signals:         {len(summary.get('structured_risk_signals', []) or [])}")
    if summary.get("claim_error"):
        print(f"  claim error:          {summary['claim_error']}")
    if summary.get("audit_path"):
        print(f"  audit path:           {summary['audit_path']}")
    print("=" * 64)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="单股 Agent-Reach claim bridge smoke 验证")
    parser.add_argument("--stock", required=True, help="目标股票名称，如 '黑芝麻智能'")
    parser.add_argument("--output-dir", default="reports", help="audit JSON 输出目录")
    parser.add_argument("--date", default=None, help="日期字符串，如 20260614")
    parser.add_argument("--write-evidence-notes", action="store_true", help="写入 Agent-Reach evidence notes")
    parser.add_argument("--evidence-dry-run", action="store_true", help="运行 evidence writer 但不写入 knowledge")
    parser.add_argument("--write-audit", action="store_true", help="写入 compact audit JSON")
    parser.add_argument("--json", action="store_true", help="输出 compact JSON")
    return parser.parse_args([] if argv is None else argv)


def main(argv=None):
    args = _parse_args(argv)
    summary = run_bridge_smoke(
        stock_name=args.stock,
        output_dir=args.output_dir,
        date_str=args.date,
        write_evidence_notes=args.write_evidence_notes,
        evidence_dry_run=args.evidence_dry_run,
        write_audit=args.write_audit,
    )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    else:
        print_summary(summary)
    return summary


if __name__ == "__main__":
    main(sys.argv[1:])
