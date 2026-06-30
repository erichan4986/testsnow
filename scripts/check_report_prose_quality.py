#!/usr/bin/env python3
"""CLI for advisory prose-quality checks on generated stock reports.

Usage:
    python scripts/check_report_prose_quality.py reports/中际旭创_20260630.md
    python scripts/check_report_prose_quality.py reports/*.md --json
    python scripts/check_report_prose_quality.py reports/*.md --fail-on-warning
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "utils"))

from report_prose_quality import (  # noqa: E402
    check_report_prose_file,
    format_prose_quality_result,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="检查股票报告 Markdown 的行文质量 warning")
    parser.add_argument("reports", nargs="+", help="Markdown 报告路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="出现 warning 时返回非零状态码；默认仅提示，不阻断流程",
    )
    args = parser.parse_args()

    results = [check_report_prose_file(Path(path)) for path in args.reports]

    if args.json:
        import json

        print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(format_prose_quality_result(result) for result in results))

    has_warnings = any(result.issues for result in results)
    return 1 if args.fail_on_warning and has_warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
