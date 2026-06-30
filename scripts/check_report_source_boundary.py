#!/usr/bin/env python3
"""CLI for checking source-boundary rules in generated stock reports.

Usage:
    python3 scripts/check_report_source_boundary.py reports/中际旭创_20260630.md
    python3 scripts/check_report_source_boundary.py reports/*.md --json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "utils"))

from report_source_boundary import (  # noqa: E402
    check_report_source_boundary_file,
    format_source_boundary_result,
    source_boundary_results_to_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="检查报告 4.1-4.4 source boundary")
    parser.add_argument("reports", nargs="+", help="Markdown 报告路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    results = [check_report_source_boundary_file(Path(path)) for path in args.reports]

    if args.json:
        print(source_boundary_results_to_json(results))
    else:
        print("\n\n".join(format_source_boundary_result(result) for result in results))

    return 1 if any(not result.passed for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
