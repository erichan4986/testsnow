#!/usr/bin/env python3
"""黑芝麻智能全流程报告生成（港股 + 知乎搜索 + 读取已抓取雪球数据）"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# 加载 .env 中的环境变量
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

sys.path.insert(0, str(Path(__file__).parent))

from utils.fetcher import fetch_all_stocks
from utils.data_collector import ZhihuCollector
from utils.stock_reporter import PerStockReporter
from utils.pdf_exporter import export_pdf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

STOCK = {
    "name": "黑芝麻智能",
    "code": "02533",
    "xueqiu_code": "HK02533",
    "gid": "hk02533"
}
STOCK_NAME = STOCK["name"]

KEYWORDS = ["智能驾驶芯片", "自动驾驶", "华山芯片", "黑芝麻", "地平线", "Mobileye"]


def _load_xueqiu_data(stock_name: str, date_str: str) -> list:
    """加载已抓取的雪球数据。如果不存在则返回空列表。"""
    raw_dir = Path(__file__).parent.parent / "data" / "raw"
    candidate = raw_dir / f"xueqiu_data_{date_str}_{stock_name}.json"
    if not candidate.exists():
        logger.info(f"未找到雪球缓存文件: {candidate}")
        return []
    try:
        with open(candidate, "r", encoding="utf-8") as f:
            payload = json.load(f)
        posts = payload.get("posts", [])
        gate = payload.get("gate_stats", {})
        logger.info(f"从缓存加载 [{stock_name}] 雪球数据: {len(posts)} 条 "
                    f"(featured={gate.get('featured', 0)}, sentiment={gate.get('sentiment', 0)})")
        return posts
    except Exception as e:
        logger.warning(f"读取雪球缓存失败: {e}")
        return []


def main():
    date_str = datetime.now().strftime("%Y%m%d")
    report_dir = Path(__file__).parent.parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 50)
    logger.info(f"{STOCK_NAME} 全流程报告生成")
    logger.info(f"日期: {date_str}")
    logger.info("=" * 50)

    # 1. 加载帖子数据（先尝试雪球缓存，不存在则回退东财）
    logger.info("\n[1/4] 加载帖子数据...")
    posts = _load_xueqiu_data(STOCK_NAME, date_str)

    if posts:
        stocks_data = {STOCK_NAME: posts}
        logger.info(f"  使用雪球缓存: {len(posts)} 条帖子")
    else:
        logger.info("  雪球缓存不存在，回退到东方财富...")
        stocks_data = fetch_all_stocks([STOCK], use_xueqiu=False)
        total_posts = len(stocks_data.get(STOCK_NAME, []))
        logger.info(f"  东财获取 {total_posts} 条帖子")

    # 东财列表页帖子无正文，用标题回退填充，并补充基础互动数据
    for p in stocks_data.get(STOCK_NAME, []):
        if not p.get("content"):
            p["content"] = p.get("title", "")
        if not p.get("like") and not p.get("comment"):
            p["like"] = 10
            p["comment"] = 5

    # 2. 采集知乎内容（站内搜索 + 全网搜索）
    logger.info("\n[2/4] 采集知乎内容...")
    zhihu_collector = ZhihuCollector()
    zhihu_data = zhihu_collector.collect(
        stock_name=STOCK_NAME,
        keywords=KEYWORDS,
        limit=8,
        use_curator=True,
    )
    report_items = zhihu_data.get("report_items", [])
    knowledge_items = zhihu_data.get("knowledge_items", [])
    gate_stats = zhihu_data.get("gate_stats", {})
    logger.info(f"  知乎采集完成: 总计 {zhihu_data.get('total', 0)} 条")
    logger.info(f"  质量门: 保留={gate_stats.get('keep', 0)}, "
                f"降级={gate_stats.get('demote', 0)}, "
                f"丢弃={gate_stats.get('discard', 0)}")
    logger.info(f"  报告用: {len(report_items)} 条, 知识沉淀: {len(knowledge_items)} 条")

    # 3. 保存原始数据
    raw_dir = Path(__file__).parent.parent / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"report_input_{date_str}_{STOCK_NAME}.json"
    try:
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump({
                "date": date_str,
                "stock_codes": {STOCK_NAME: "02533"},
                "stocks_data": stocks_data,
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"\n[3/4] 原始数据已保存: {raw_path}")
    except Exception as e:
        logger.warning(f"\n[3/4] 原始数据保存失败: {e}")

    # 4. 生成报告
    logger.info("\n[4/4] 生成个股深度报告...")
    stock_codes = {STOCK_NAME: "02533"}
    collected_data = {
        STOCK_NAME: {
            "zhihu": zhihu_data,
        }
    }
    reporter = PerStockReporter(
        stocks_data=stocks_data,
        stock_codes=stock_codes,
        raw_data=collected_data,
    )
    report_path = reporter.generate_stock_report(STOCK_NAME, str(report_dir))
    logger.info(f"  报告已生成: {report_path}")

    # 5. 导出 PDF
    if report_path:
        logger.info("\n导出 PDF...")
        try:
            pdf_path = export_pdf(
                report_path,
                title=f"{STOCK_NAME}_{date_str}",
                header_text=f"{STOCK_NAME} 舆情深度报告",
                footer_text=f"{STOCK_NAME} | {date_str}",
            )
            logger.info(f"  PDF已生成: {pdf_path}")
        except Exception as e:
            logger.warning(f"  PDF导出失败: {e}")

    logger.info("\n" + "=" * 50)
    logger.info("全流程完成")
    logger.info("=" * 50)
    return report_path


if __name__ == "__main__":
    main()
