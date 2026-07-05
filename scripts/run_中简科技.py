#!/usr/bin/env python3
"""中简科技全流程报告生成（A股 + 知乎搜索 + 读取已抓取雪球/知识库数据）"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

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
    "name": "中简科技",
    "code": "300777",
    "xueqiu_code": "SZ300777",
    "gid": "300777",
}
STOCK_NAME = STOCK["name"]

KEYWORDS = ["中简科技", "碳纤维", "航空航天", "军工", "复合材料", "T1100", "ZM40X"]


_CITATION_RE = re.compile(r"\[\^?\d+\]")


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(description="生成中简科技单股深度报告")
    parser.add_argument(
        "--fast-test",
        action="store_true",
        help="工程验证模式：跳过知乎采集和 LLM curator，优先复用本地缓存/knowledge posts。",
    )
    return parser.parse_args([] if argv is None else argv)


def _empty_zhihu_data() -> dict:
    return {
        "report_items": [],
        "knowledge_items": [],
        "gate_stats": {},
        "total": 0,
        "api_calls": 0,
        "fast_test": True,
    }


def _load_cached_zhihu_data(stock_name: str, date_str: str) -> dict:
    """Load zhihu data from saved report_input JSON for fast engineering runs."""
    raw_dir = Path(__file__).parent.parent / "data" / "raw"

    candidates = [raw_dir / f"report_input_{date_str}_{stock_name}.json"]
    latest = sorted(
        raw_dir.glob(f"report_input_*_{stock_name}.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    candidates.extend([p for p in latest if p not in candidates])

    for path in candidates:
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            zhihu_data = payload.get("raw_data", {}).get(stock_name, {}).get("zhihu")
            if isinstance(zhihu_data, dict):
                logger.info(f"  快速测试复用知乎缓存: {path.name}")
                return zhihu_data
        except Exception as e:
            logger.warning(f"读取知乎缓存失败 {path.name}: {e}")
    return {}


def _load_agent_reach_config(stock_name: str) -> dict:
    """Load per-stock Agent-Reach config from config/stocks.json."""
    config_path = Path(__file__).parent.parent / "config" / "stocks.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            stocks = json.load(f)
    except Exception as e:
        logger.warning(f"读取 Agent-Reach 配置失败: {e}")
        return {}

    for stock in stocks:
        if stock.get("name") == stock_name and stock.get("agent_reach"):
            return {stock_name: stock["agent_reach"]}
    return {}


def _load_source_intake_config(stock_name: str) -> dict:
    """Load per-stock Source Intake config from config/stocks.json."""
    config_path = Path(__file__).parent.parent / "config" / "stocks.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            stocks = json.load(f)
    except Exception as e:
        logger.warning(f"读取 Source Intake 配置失败: {e}")
        return {}

    for stock in stocks:
        if stock.get("name") == stock_name and stock.get("source_intake"):
            return {stock_name: stock["source_intake"]}
    return {}


def _load_xueqiu_data(stock_name: str, date_str: str) -> list:
    """加载已抓取的雪球数据。优先匹配指定日期，否则回退到最近日期的缓存。"""
    raw_dir = Path(__file__).parent.parent / "data" / "raw"

    candidate = raw_dir / f"xueqiu_data_{date_str}_{stock_name}.json"
    if candidate.exists():
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                payload = json.load(f)
            posts = payload.get("posts", [])
            gate = payload.get("gate_stats", {})
            logger.info(
                f"从缓存加载 [{stock_name}] 雪球数据: {len(posts)} 条 "
                f"(featured={gate.get('featured', 0)}, sentiment={gate.get('sentiment', 0)})"
            )
            return posts
        except Exception as e:
            logger.warning(f"读取雪球缓存失败: {e}")

    all_candidates = sorted(
        raw_dir.glob(f"xueqiu_data_*_{stock_name}.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if all_candidates:
        latest = all_candidates[0]
        logger.info(f"未找到 {date_str} 的缓存，回退到最近缓存: {latest.name}")
        try:
            with open(latest, "r", encoding="utf-8") as f:
                payload = json.load(f)
            posts = payload.get("posts", [])
            gate = payload.get("gate_stats", {})
            logger.info(
                f"从缓存加载 [{stock_name}] 雪球数据: {len(posts)} 条 "
                f"(featured={gate.get('featured', 0)}, sentiment={gate.get('sentiment', 0)})"
            )
            return posts
        except Exception as e:
            logger.warning(f"读取雪球缓存失败: {e}")

    logger.info(f"未找到任何雪球缓存文件")
    return []


def _parse_markdown_post(path: Path) -> dict:
    """Parse a knowledge post markdown file into a reporter post dict."""
    text = path.read_text(encoding="utf-8")

    title = path.stem
    url = ""
    like = 10
    comment = 5
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            body = parts[2].strip()

            for line in fm_text.splitlines():
                line = line.rstrip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip()
                if key == "title":
                    title = val or title
                elif key in ("source_url", "url"):
                    url = val
                elif key == "likes" and val.isdigit():
                    like = int(val)
                elif key == "comments" and val.isdigit():
                    comment = int(val)

            likes_match = re.search(r"^\s+likes:\s*(\d+)", fm_text, re.MULTILINE)
            if likes_match:
                like = int(likes_match.group(1))
            comments_match = re.search(r"^\s+comments:\s*(\d+)", fm_text, re.MULTILINE)
            if comments_match:
                comment = int(comments_match.group(1))

    if not title or title == path.stem:
        heading_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if heading_match:
            title = heading_match.group(1).strip()

    body = _CITATION_RE.sub("", body).strip()
    if not body:
        body = title

    return {
        "title": title,
        "content": body,
        "url": url,
        "like": like,
        "comment": comment,
    }


def _load_knowledge_posts(stock_name: str) -> list:
    """Load markdown posts from knowledge/10-Stocks/<stock>/posts/."""
    posts_dir = Path(__file__).parent.parent / "knowledge" / "10-Stocks" / stock_name / "posts"
    if not posts_dir.exists():
        logger.info(f"未找到 knowledge posts 目录: {posts_dir}")
        return []

    posts = []
    for path in sorted(posts_dir.glob("*.md")):
        try:
            posts.append(_parse_markdown_post(path))
        except Exception as e:
            logger.warning(f"解析 knowledge post 失败 {path.name}: {e}")

    logger.info(f"从 knowledge 加载 [{stock_name}] posts: {len(posts)} 条")
    return posts


def main(argv=None):
    args = _parse_args(argv)
    date_str = datetime.now().strftime("%Y%m%d")
    report_dir = Path(__file__).parent.parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 50)
    logger.info(f"{STOCK_NAME} 全流程报告生成")
    logger.info(f"日期: {date_str}")
    logger.info("=" * 50)

    # 1. 加载帖子数据
    logger.info("\n[1/4] 加载帖子数据...")
    posts = _load_xueqiu_data(STOCK_NAME, date_str)

    if posts:
        stocks_data = {STOCK_NAME: posts}
        logger.info(f"  使用雪球缓存: {len(posts)} 条帖子")
    elif args.fast_test:
        logger.info("  快速测试模式：无雪球缓存，尝试 knowledge posts...")
        knowledge_posts = _load_knowledge_posts(STOCK_NAME)
        if knowledge_posts:
            stocks_data = {STOCK_NAME: knowledge_posts}
            logger.info(f"  使用 knowledge posts: {len(knowledge_posts)} 条")
        else:
            logger.warning("  未找到 knowledge posts，使用空帖子列表")
            stocks_data = {STOCK_NAME: []}
    else:
        logger.info("  雪球缓存不存在，回退到东方财富...")
        stocks_data = fetch_all_stocks([STOCK], use_xueqiu=False)
        total_posts = len(stocks_data.get(STOCK_NAME, []))
        logger.info(f"  东财获取 {total_posts} 条帖子")

    for p in stocks_data.get(STOCK_NAME, []):
        if not p.get("content"):
            p["content"] = p.get("title", "")
        if not p.get("like") and not p.get("comment"):
            p["like"] = 10
            p["comment"] = 5

    # 2. 知乎内容
    if args.fast_test:
        logger.info("\n[2/4] 快速测试模式：跳过知乎采集和 LLM curator")
        zhihu_data = _load_cached_zhihu_data(STOCK_NAME, date_str) or _empty_zhihu_data()
    else:
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
    logger.info(
        f"  质量门: 保留={gate_stats.get('keep', 0)}, "
        f"降级={gate_stats.get('demote', 0)}, 丢弃={gate_stats.get('discard', 0)}"
    )
    logger.info(f"  报告用: {len(report_items)} 条, 知识沉淀: {len(knowledge_items)} 条")

    # 3. 保存原始数据
    collected_data = {STOCK_NAME: {"zhihu": zhihu_data}}
    raw_dir = Path(__file__).parent.parent / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"report_input_{date_str}_{STOCK_NAME}.json"
    try:
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "date": date_str,
                    "stock_codes": {STOCK_NAME: "300777"},
                    "stocks_data": stocks_data,
                    "raw_data": collected_data,
                },
                f,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        logger.info(f"\n[3/4] 原始数据已保存: {raw_path}")
    except Exception as e:
        logger.warning(f"\n[3/4] 原始数据保存失败: {e}")

    # 4. 生成报告
    logger.info("\n[4/4] 生成个股深度报告...")
    stock_codes = {STOCK_NAME: "300777"}
    agent_reach_configs = _load_agent_reach_config(STOCK_NAME)
    source_intake_configs = _load_source_intake_config(STOCK_NAME)
    reporter = PerStockReporter(
        stocks_data=stocks_data,
        stock_codes=stock_codes,
        raw_data=collected_data,
        agent_reach_configs=agent_reach_configs,
        source_intake_configs=source_intake_configs,
    )
    md_path, html_path = reporter.generate_stock_report(STOCK_NAME, str(report_dir))
    if md_path:
        logger.info(f"  报告已生成: {md_path}")
    if html_path:
        logger.info(f"  Dashboard 已生成: {html_path}")

    # 5. 导出 PDF
    if md_path:
        logger.info("\n导出 PDF...")
        try:
            pdf_path = export_pdf(
                md_path,
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
    return md_path


if __name__ == "__main__":
    main(sys.argv[1:])
