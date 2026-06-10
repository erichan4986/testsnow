#!/usr/bin/env python3
"""从 data/raw JSON 直接同步 featured 帖子内容到 Vault。

用法:
    python scripts/sync_vault_from_raw.py --date 20260602 --stock 黑芝麻智能
    python scripts/sync_vault_from_raw.py --date 20260602 --all

不需要启动 Chrome，直接从已抓取的 JSON 中读取完整正文写入 Vault。
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

STOCKS = [
    "黑芝麻智能",
    "长春高新",
    "三花智控",
    "中简科技",
    "圣邦股份",
    "乐鑫科技",
]


def _extract_post_id(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def _write_post_to_vault(
    vault_base: Path,
    stock_name: str,
    post: dict,
) -> Path:
    """将单条帖子写入 Vault（YAML frontmatter + 完整正文）。"""
    url = post.get("url", "")
    post_id = _extract_post_id(url)
    stock_dir = vault_base / stock_name / "posts"
    stock_dir.mkdir(parents=True, exist_ok=True)
    output_path = stock_dir / f"{post_id}.md"

    # YAML frontmatter
    fm = [
        "---",
        f'source_url: "{url}"',
        f"stock_name: {stock_name}",
        f'author: "{post.get("author", "")}"',
        f'title: "{post.get("title", "").replace(chr(34), chr(92)+chr(34))}"',
        f'date: "{post.get("time", "")}"',
        "interactions:",
        f'  likes: {post.get("like_count", 0)}',
        f'  comments: {post.get("comment_count", 0)}',
        f'  reposts: {post.get("repost_count", 0)}',
        f'collected_at: "{datetime.now().isoformat()}"',
        "---",
    ]

    title = post.get("title", "Untitled")
    content = post.get("content", "")

    md_content = "\n".join(fm) + f"\n\n# {title}\n\n{content}\n"
    output_path.write_text(md_content, encoding="utf-8")
    return output_path


def sync_stock(vault_base: Path, raw_dir: Path, stock_name: str, date_str: str) -> int:
    """同步单只股票的 featured 帖子到 Vault。返回写入数量。"""
    raw_path = raw_dir / f"xueqiu_data_{date_str}_{stock_name}.json"
    if not raw_path.exists():
        logger.warning(f"[{stock_name}] 未找到 raw 数据: {raw_path}")
        return 0

    with open(raw_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    posts = payload.get("posts", [])
    featured = [p for p in posts if p.get("_track") == "featured"]

    written = 0
    for post in featured:
        content = post.get("content", "")
        if not content or len(content) < 100:
            continue
        _write_post_to_vault(vault_base, stock_name, post)
        written += 1

    logger.info(f"[{stock_name}] Vault 同步完成: {written}/{len(featured)} 条 featured 帖子")
    return written


def main():
    parser = argparse.ArgumentParser(description="从 data/raw 同步帖子到 Vault")
    parser.add_argument("--stock", type=str, help="指定股票名称")
    parser.add_argument("--all", action="store_true", help="处理全部6只股票")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y%m%d"), help="数据日期")
    args = parser.parse_args()

    stocks_to_process = []
    if args.all:
        stocks_to_process = STOCKS
    elif args.stock:
        stocks_to_process = [args.stock]
    else:
        parser.print_help()
        sys.exit(1)

    raw_dir = Path(__file__).parent.parent / "data" / "raw"
    vault_base = Path(__file__).parent.parent / "knowledge" / "10-Stocks"

    total = 0
    for stock_name in stocks_to_process:
        total += sync_stock(vault_base, raw_dir, stock_name, args.date)

    logger.info(f"全部完成，共写入 {total} 条帖子到 Vault")


if __name__ == "__main__":
    main()
