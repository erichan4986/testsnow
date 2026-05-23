#!/usr/bin/env python3
"""
周期性报告生成器
用法:
    python generate_periodic_report.py --type quarterly --year 2025 --quarter 2 --stock 300661
    python generate_periodic_report.py --type semiannual --year 2025 --half 1 --stock 300661
    python generate_periodic_report.py --type annual --year 2025 --stock 300661
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "utils"))

from periodic_reporter import PeriodicReporter


def main():
    parser = argparse.ArgumentParser(description="生成周期性报告")
    parser.add_argument("--type", choices=["quarterly", "semiannual", "annual"], required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--quarter", type=int, choices=[1, 2, 3, 4])
    parser.add_argument("--half", type=int, choices=[1, 2])
    parser.add_argument("--stock", required=True, help="股票代码，如 300661")
    parser.add_argument("--name", default="", help="股票名称（用于输出文件名）")
    args = parser.parse_args()

    reporter = PeriodicReporter()
    reporter.generate(
        report_type=args.type,
        year=args.year,
        quarter=args.quarter,
        half=args.half,
        stock_code=args.stock,
        stock_name=args.name or args.stock,
    )


if __name__ == "__main__":
    main()
