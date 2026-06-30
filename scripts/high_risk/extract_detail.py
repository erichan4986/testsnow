#!/usr/bin/env python3
"""雪球帖子详情页批量提取脚本

用法:
    python scripts/high_risk/extract_detail.py --stock 黑芝麻智能
    python scripts/high_risk/extract_detail.py --all

读取 data/raw/xueqiu_data_{date}_{stock}.json 中的帖子 URL，
使用 DetailPageFetcher 进入详情页提取完整正文，写入 knowledge/10-Stocks/{stock}/posts/。
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from utils.detail_page_fetcher import DetailPageFetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

CDP_PORT = 9222

STOCKS = [
    "黑芝麻智能",
    "长春高新",
    "三花智控",
    "中简科技",
    "圣邦股份",
    "乐鑫科技",
]


def load_stock_posts(stock_name: str, date_str: str) -> list:
    """加载已抓取的列表页数据。"""
    raw_dir = REPO_ROOT / "data" / "raw"
    candidate = raw_dir / f"xueqiu_data_{date_str}_{stock_name}.json"
    if not candidate.exists():
        logger.warning(f"未找到列表页数据: {candidate}")
        return []
    with open(candidate, "r", encoding="utf-8") as f:
        payload = json.load(f)
    posts = payload.get("posts", [])
    logger.info(f"[{stock_name}] 从列表页加载 {len(posts)} 条帖子")
    return posts


def main(argv=None):
    parser = argparse.ArgumentParser(description="雪球帖子详情页批量提取")
    parser.add_argument("--stock", type=str, help="指定股票名称")
    parser.add_argument("--all", action="store_true", help="处理全部6只股票")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y%m%d"), help="列表页数据日期 (默认今天)")
    parser.add_argument("--cdp-port", type=int, default=CDP_PORT, help="Chrome CDP 端口")
    args = parser.parse_args(argv)

    stocks_to_process = []
    if args.all:
        stocks_to_process = STOCKS
    elif args.stock:
        stocks_to_process = [args.stock]
    else:
        parser.print_help()
        sys.exit(1)

    vault_base = REPO_ROOT / "knowledge" / "10-Stocks"

    # 初始化成熟的 DetailPageFetcher
    fetcher = DetailPageFetcher(
        vault_base=vault_base,
        cdp_url=f"http://localhost:{args.cdp_port}",
        delay_range=(3, 5),
        request_interval=5,
    )

    try:
        for stock_name in stocks_to_process:
            posts = load_stock_posts(stock_name, args.date)
            if not posts:
                continue

            # 只取 featured 帖子进入详情页
            featured = [p for p in posts if p.get("_track") == "featured"]
            if not featured:
                logger.info(f"[{stock_name}] 无 featured 帖子，跳过详情页提取")
                continue

            logger.info(f"[{stock_name}] 开始提取 {len(featured)} 条 featured 帖子详情...")

            # 构造 DetailPageFetcher 需要的格式
            dp_posts = []
            for p in featured:
                dp_posts.append({
                    "url": p.get("url", ""),
                    "title": p.get("title", ""),
                    "author": p.get("author", ""),
                    "date": p.get("time", ""),
                    "like_count": p.get("like_count", 0),
                    "comment_count": p.get("comment_count", 0),
                    "repost_count": p.get("repost_count", 0),
                })

            success_urls = fetcher.fetch_posts(stock_name, dp_posts)
            logger.info(f"[{stock_name}] 详情页提取完成: {len(success_urls)}/{len(dp_posts)}")
    finally:
        fetcher.close()

    logger.info("全部完成")


if __name__ == "__main__":
    main()
