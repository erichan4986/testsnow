#!/usr/bin/env python3
"""中简科技 Phase 2 技术形态分析报告 — 使用真实日K数据（mootdx）"""

import logging
import sys
from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
UTILS_DIR = SCRIPT_DIR / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from reporter.technical_analyzer import analyze  # noqa: E402
from technical_report_entry import write_technical_report  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(message)s")


def main():
    csv_path = REPO_ROOT / "data" / "raw" / "zhongjian_300777_daily_20260608.csv"
    daily = pd.read_csv(csv_path)
    daily["date"] = pd.to_datetime(daily["date"])
    result = analyze(daily)

    return write_technical_report(
        stock_name="中简科技",
        stock_code="300777",
        indicators=result.get("indicators", {}),
        resonance=result.get("resonance", {}),
        price_target=result.get("price_target"),
        report_dir=REPO_ROOT / "reports",
        data_lines=(
            f"\n[数据] 真实日K: {len(daily)} 根",
            f"  日期范围: {daily['date'].iloc[0]:%Y-%m-%d} 至 {daily['date'].iloc[-1]:%Y-%m-%d}",
            f"  最新收盘价: {daily['close'].iloc[-1]:.2f}",
        ),
    )


if __name__ == "__main__":
    main()
