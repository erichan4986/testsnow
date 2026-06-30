#!/usr/bin/env python3
"""Smoke test script for Source Intake v2.

Does not run a full report, call LLMs, start Chrome/CDP, or fetch Xueqiu/Zhihu.
Only exercises the structured A-share source intake helper and merge skill.
"""

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

scripts_dir = Path(__file__).resolve().parent.parent
project_root = scripts_dir.parent
sys.path.insert(0, str(scripts_dir))

from utils.a_stock_source_intake import collect_a_stock_source_items  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


STOCK_CODES = {
    "中简科技": "300777",
    "圣邦股份": "300661",
}


def main():
    parser = argparse.ArgumentParser(description="Source Intake v2 smoke test")
    parser.add_argument("--stock", default="中简科技", help="Stock name to test")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument("--write-audit", action="store_true", help="Write compact audit JSON")
    parser.add_argument("--output-dir", default="reports", help="Directory for audit JSON")
    args = parser.parse_args()

    stock_name = args.stock
    stock_code = STOCK_CODES.get(stock_name, "")
    if not stock_code:
        logger.error(f"Unknown stock: {stock_name}")
        sys.exit(1)

    config = {
        "enabled": True,
        "a_stock": {
            "cninfo_announcements": {
                "enabled": True,
                "lookback_days": 365,
                "max_items": 12,
                "categories": ["年度报告", "季度报告", "业绩预告", "权益分派", "投资者关系活动", "风险提示"],
            },
            "eastmoney_stock_news": {"enabled": True, "max_items": 10},
            "eastmoney_research_reports": {"enabled": True, "max_items": 8},
            "eastmoney_global_news": {"enabled": False},
        },
    }

    logger.info(f"Running Source Intake smoke for {stock_name}({stock_code})")
    result = collect_a_stock_source_items(
        stock_name=stock_name,
        stock_code=stock_code,
        config=config,
    )

    audit = {
        "stock_name": stock_name,
        "stock_code": stock_code,
        "date": date.today().isoformat(),
        "status": result.get("status"),
        "total_items": len(result.get("items", [])),
        "source_statuses": result.get("source_statuses"),
        "warnings": result.get("warnings", []),
        "credit_breakdown": {},
    }

    credit_breakdown = {}
    for item in result.get("items", []):
        credit = item.extra.get("source_credit", 0)
        source_type = item.extra.get("source_type", "unknown")
        key = f"{source_type}:{credit}"
        credit_breakdown[key] = credit_breakdown.get(key, 0) + 1
    audit["credit_breakdown"] = credit_breakdown

    if args.json:
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    else:
        logger.info(f"status={audit['status']} total_items={audit['total_items']}")
        for name, status in audit["source_statuses"].items():
            logger.info(f"  {name}: {status}")

    if args.write_audit:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"source_intake_smoke_{stock_name}_{date.today().strftime('%Y%m%d')}.json"
        out_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Audit written to {out_path}")


if __name__ == "__main__":
    main()
