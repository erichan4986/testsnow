#!/usr/bin/env python3
"""Run lightweight claim intake smoke steps and render claim audit.

This orchestrator is intentionally small: it does not run reports, LLMs,
Chrome/CDP, Xueqiu detail scraping, or Zhihu refresh. Optional intake steps are
explicit flags; the claim verification audit always runs last.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from smoke_cached_community_claims import run_smoke as run_cached_community_smoke
from smoke_claim_verification_audit import run_audit as run_claim_audit
from smoke_fresh_social_claims import run_smoke as run_fresh_social_smoke


def _repo_root() -> Path:
    return Path(__file__).parent.parent


def run_flow(
    stock: str,
    code: str = "",
    base_dir: str = None,
    output: str = None,
    date_str: str = None,
    cached_community: bool = False,
    fresh_eastmoney_guba: bool = False,
    write_inputs: bool = False,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Run selected lightweight intake steps, then write claim audit."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    if base_dir is None:
        base_dir = str(_repo_root() / "knowledge")
    if output is None:
        output = str(_repo_root() / "docs" / "agent_workflow" / f"{date_str}-{stock}-claim-intake-audit.md")

    intakes: List[Dict[str, Any]] = []

    if cached_community:
        cached = run_cached_community_smoke(
            stock_name=stock,
            stock_code=code,
            base_dir=base_dir,
            date_str=date_str,
            write=write_inputs,
            overwrite=overwrite,
        )
        intakes.append({"name": "cached_community", "result": cached})

    if fresh_eastmoney_guba:
        fresh = run_fresh_social_smoke(
            stock_name=stock,
            stock_code=code,
            base_dir=base_dir,
            date_str=date_str,
            eastmoney_guba=True,
            write=write_inputs,
            overwrite=overwrite,
        )
        intakes.append({"name": "fresh_social", "result": fresh})

    audit = run_claim_audit(stock=stock, base_dir=base_dir, output=output)

    return {
        "stock": stock,
        "code": code,
        "date": date_str,
        "write_inputs": write_inputs,
        "overwrite": overwrite,
        "intakes": intakes,
        "audit": audit,
    }


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run claim intake smoke flow and render audit")
    parser.add_argument("--stock", required=True, help="Stock name, e.g. 中简科技")
    parser.add_argument("--code", default="", help="Stock code, e.g. 300777")
    parser.add_argument("--base-dir", default=None, help="Knowledge root, default ./knowledge")
    parser.add_argument("--output", default=None, help="Audit markdown output path")
    parser.add_argument("--date", default=None, help="Output date, default today")
    parser.add_argument("--cached-community", action="store_true", help="Run cached community claim smoke first")
    parser.add_argument("--fresh-eastmoney-guba", action="store_true", help="Run fresh Eastmoney guba direct smoke first")
    parser.add_argument("--write-inputs", action="store_true", help="Actually write intake notes; default dry-runs intakes")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite intake notes when writing")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    return parser.parse_args([] if argv is None else argv)


def main(argv=None):
    args = _parse_args(argv)
    summary = run_flow(
        stock=args.stock,
        code=args.code,
        base_dir=args.base_dir,
        output=args.output,
        date_str=args.date,
        cached_community=args.cached_community,
        fresh_eastmoney_guba=args.fresh_eastmoney_guba,
        write_inputs=args.write_inputs,
        overwrite=args.overwrite,
    )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"audit: {summary['audit']['path']}")
        for intake in summary["intakes"]:
            result = intake["result"]
            print(f"{intake['name']}: status={result.get('status')} claims={result.get('claim_count')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
