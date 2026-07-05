#!/usr/bin/env python3
"""CLI for checking generated stock report quality.

Usage:
    python scripts/check_report_quality.py reports/圣邦股份_20260604.md
    python scripts/check_report_quality.py --sample
    python scripts/check_report_quality.py reports/*.md --json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(Path(__file__).parent / "utils"))

from report_quality import check_report_file, format_quality_result  # noqa: E402


SAMPLE_REPORT = Path(__file__).parent.parent / "tests" / "fixtures" / "minimal_quality_report.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="检查股票报告 Markdown 的质量完整性")
    parser.add_argument("reports", nargs="*", help="Markdown 报告路径")
    parser.add_argument("--sample", action="store_true", help="检查仓库内置最小样例报告")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    paths = [Path(p) for p in args.reports]
    if args.sample:
        paths.append(SAMPLE_REPORT)

    if not paths:
        parser.error("请提供至少一个报告路径，或使用 --sample")

    any_failed = False
    results = []
    for path in paths:
        result = check_report_file(path)
        results.append(result)
        if not result.passed:
            any_failed = True

    if args.json:
        import json

        print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(format_quality_result(r) for r in results))

    return 1 if any_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
