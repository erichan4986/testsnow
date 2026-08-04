#!/usr/bin/env python3
"""澜起科技 Phase 2 技术形态分析报告 — 使用真实日K数据（mootdx + 本地前复权）"""

import logging
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
UTILS_DIR = SCRIPT_DIR / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from data_collector import TechnicalCollector  # noqa: E402
from technical_report_entry import write_technical_report  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _export_source_data(collector: TechnicalCollector) -> None:
    data_dir = REPO_ROOT / "data" / "raw"
    data_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")

    daily = collector.fetch_kline("688008", market=1, days=250)
    if daily is not None and not daily.empty:
        path = data_dir / f"lanqi_688008_daily_{stamp}_raw.csv"
        daily.to_csv(path, index=False, encoding="utf-8-sig")
        logger.info("[CSV] 原始日K已保存: %s", path)

    weekly = collector.fetch_weekly_kline("688008", market=1, weeks=72)
    if weekly is not None and not weekly.empty:
        path = data_dir / f"lanqi_688008_weekly_{stamp}.csv"
        weekly.to_csv(path, index=False, encoding="utf-8-sig")
        logger.info("[CSV] 周线已保存: %s", path)


def main():
    collector = TechnicalCollector()
    technical = collector.collect("688008", market=1, days=250, adjustment="qfq")
    indicators = technical.get("indicators")
    if not indicators:
        raise RuntimeError("澜起科技未取得可用技术指标")
    _export_source_data(collector)

    return write_technical_report(
        stock_name="澜起科技",
        stock_code="688008",
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
