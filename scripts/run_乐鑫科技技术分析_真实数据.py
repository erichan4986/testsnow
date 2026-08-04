#!/usr/bin/env python3
"""乐鑫科技 Phase 2 技术形态分析报告 — 使用真实日K数据（mootdx + 本地前复权）"""

import logging
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
UTILS_DIR = SCRIPT_DIR / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from data_collector import TechnicalCollector  # noqa: E402
from technical_report_entry import write_technical_report  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(message)s")


def main():
    technical = TechnicalCollector().collect(
        "688018", market=1, days=250, adjustment="qfq",
    )
    indicators = technical.get("indicators")
    if not indicators:
        raise RuntimeError("乐鑫科技未取得可用技术指标")

    return write_technical_report(
        stock_name="乐鑫科技",
        stock_code="688018",
        indicators=indicators,
        resonance=indicators.get("_resonance", {}),
        price_target=technical.get("price_target"),
        fund_flow=technical.get("fund_flow"),
        concept_blocks=technical.get("concept_blocks"),
        report_dir=REPO_ROOT / "reports",
        title_suffix="qfq 真实数据",
        data_lines=(
            f"\n[数据] adjustment={technical.get('adjustment')}, bars={technical.get('days')}",
            f"  最新收盘价: {indicators.get('close', 'N/A')}",
        ),
    )


if __name__ == "__main__":
    main()
