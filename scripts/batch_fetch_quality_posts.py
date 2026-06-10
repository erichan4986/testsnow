#!/usr/bin/env python3
"""
批量抓取精品帖子详情页（CDP 模式）

筛选标准：
- 非转发、非公告
- 互动量（👍+💬+🔄）≥ 15
- 同一作者相似内容去重

使用方法：
1. 先运行启动器: ./scripts/start_chrome_cdp.sh
2. 在 Chrome 中登录雪球网
3. 运行本脚本: python3 scripts/batch_fetch_quality_posts.py
4. 抓取结果写入 knowledge/10-Stocks/<股票>/posts/
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "utils"))

from detail_page_fetcher import DetailPageFetcher


def filter_quality_posts(posts, min_interaction=15):
    """
    筛选精品帖子。

    标准：
    1. 非转发、非官方公告
    2. 互动量 ≥ min_interaction
    3. 同一作者内容相似度>70%的去重，保留互动量最高的一篇
    """
    # 过滤转发和公告
    original = [
        p for p in posts
        if not p.get("is_repost")
        and not p.get("author", "").startswith(p.get("title", "").split("：")[0])
        and not ("公告" in p.get("title", "") and "通告" in p.get("title", ""))
    ]

    # 计算互动量并排序
    for p in original:
        p["_interaction"] = p.get("like_count", 0) + p.get("comment_count", 0) + p.get("repost_count", 0)

    sorted_posts = sorted(original, key=lambda x: x["_interaction"], reverse=True)

    # 去重：同一作者内容相似度>70%只保留互动量最高的一篇
    featured = []
    for post in sorted_posts:
        if post["_interaction"] < min_interaction:
            continue

        author = post.get("author", "")
        content = post.get("content", "")
        is_duplicate = False

        for fp in featured:
            if fp.get("author") == author:
                fp_content = fp.get("content", "")
                min_len = min(len(content), len(fp_content))
                if min_len > 0:
                    same_chars = sum(1 for a, b in zip(content[:min_len], fp_content[:min_len]) if a == b)
                    if same_chars / min_len > 0.7:
                        is_duplicate = True
                        break

        if not is_duplicate:
            featured.append(post)

    return featured


def main():
    print("=" * 70)
    print("批量抓取精品帖子详情页（CDP 模式）")
    print("=" * 70)
    print()

    # 加载数据
    with open("data/raw/xueqiu_data_20260520.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # 筛选精品帖子
    all_stocks = {}
    total_posts = 0
    for stock_name, posts in data.items():
        quality = filter_quality_posts(posts, min_interaction=15)
        if quality:
            all_stocks[stock_name] = quality
            total_posts += len(quality)

    print(f"共筛选出 {len(all_stocks)} 只股票，{total_posts} 篇精品帖子：")
    print()

    for stock_name, posts in all_stocks.items():
        print(f"  📌 {stock_name}: {len(posts)} 篇")
        for i, p in enumerate(posts, 1):
            total = p["_interaction"]
            print(f"     {i}. [{p['author']}] {p['title'][:40]}... (互动:{total})")
    print()

    # 启动 DetailPageFetcher（CDP 模式）
    fetcher = DetailPageFetcher(
        vault_base=Path("knowledge/10-Stocks"),
        cdp_url="http://127.0.0.1:9222",
        delay_range=(5, 10),
        request_interval=8,
    )

    print("正在连接 Chrome CDP (http://127.0.0.1:9222)...")
    print("如果连接失败，请先运行: ./scripts/start_chrome_cdp.sh")
    print()

    # 逐只股票抓取
    grand_total = 0
    grand_success = 0

    for stock_name, posts in all_stocks.items():
        print(f"\n--- {stock_name} ({len(posts)} 篇) ---")
        success_urls = fetcher.fetch_posts(stock_name, posts)
        success_count = len(success_urls)
        grand_total += len(posts)
        grand_success += success_count

        # 显示结果摘要
        for url in success_urls:
            post_id = url.rstrip("/").split("/")[-1]
            vault_path = Path(f"knowledge/10-Stocks/{stock_name}/posts") / f"{post_id}.md"
            if vault_path.exists():
                content = vault_path.read_text(encoding="utf-8")
                import re
                match = re.search(r"^---\n.*?\n---\n\n# .*\n\n(.+)", content, re.DOTALL)
                if match:
                    body_len = len(match.group(1).strip())
                    print(f"  ✓ {post_id}: {body_len} 字")
                else:
                    print(f"  ✓ {post_id}: 已写入")
            else:
                print(f"  ✗ {post_id}: 写入失败")

        if success_count < len(posts):
            print(f"  ⚠ {len(posts) - success_count} 篇抓取失败")

    print()
    print("=" * 70)
    print(f"全部完成: {grand_success}/{grand_total} 篇成功")
    print("=" * 70)


if __name__ == "__main__":
    main()
