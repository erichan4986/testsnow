#!/usr/bin/env python3
"""Generic single-stock report entry.

Production usage:
    python scripts/run_stock_report.py --stock 中际旭创

Engineering usage:
    python scripts/run_stock_report.py --stock 中际旭创 --fast-test --no-pdf
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
UTILS_DIR = SCRIPTS_DIR / "utils"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

env_path = REPO_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)

from utils.data_collector import ZhihuCollector
from utils.fetcher import fetch_all_stocks
from utils.pdf_exporter import export_pdf
from utils.stock_reporter import PerStockReporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_CITATION_RE = re.compile(r"\[\^?\d+\]")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成任意已配置股票的单股深度报告")
    default_raw_dir = str(REPO_ROOT / "data" / "raw")
    default_report_dir = str(REPO_ROOT / "reports")
    parser.add_argument("--stock", required=True, help="股票名称、代码或雪球代码，例如 中际旭创 / 300308 / SZ300308")
    parser.add_argument("--config", default=str(REPO_ROOT / "config" / "stocks.json"), help="股票配置 JSON 路径")
    parser.add_argument("--raw-dir", default=default_raw_dir, help="原始输入/缓存目录")
    parser.add_argument("--report-dir", default=default_report_dir, help="报告输出目录")
    parser.add_argument("--date", default=None, help="固定日期 YYYYMMDD，默认今天")
    parser.add_argument(
        "--fast-test",
        action="store_true",
        help="工程验证模式：跳过知乎采集和 LLM curator，只复用本地缓存/knowledge posts。",
    )
    parser.add_argument(
        "--offline-smoke",
        action="store_true",
        help="真正离线的入口 smoke：隐含 --fast-test/--no-pdf，并禁用 LLM、行情 API、技术采集和图表生成。",
    )
    parser.add_argument("--no-pdf", action="store_true", help="跳过 PDF 导出")

    parser.add_argument("--keyword", action="append", default=[], help="补充知乎/材料搜索关键词，可重复")
    parser.add_argument("--code", default="", help="bootstrap 新股票时填写交易代码")
    parser.add_argument("--xueqiu-code", default="", help="bootstrap 新股票时填写雪球代码，如 SZ300308/HK02533")
    parser.add_argument("--gid", default="", help="bootstrap 新股票时填写行情 gid，默认使用 --code")
    parser.add_argument(
        "--bootstrap-config",
        action="store_true",
        help="股票未配置时生成配置草稿；默认只写 /tmp 预览，不跑报告。",
    )
    parser.add_argument("--write-config", action="store_true", help="配合 --bootstrap-config，把草稿追加写入 config/stocks.json")
    parser.add_argument(
        "--bootstrap-output",
        default="",
        help="bootstrap 预览输出路径，默认 /tmp/<stock>_stock_config_preview.json",
    )
    args = parser.parse_args([] if argv is None else argv)
    args._default_raw_dir = default_raw_dir
    args._default_report_dir = default_report_dir
    return args


def _apply_offline_smoke_mode(args: argparse.Namespace) -> None:
    args.fast_test = True
    args.no_pdf = True
    if args.raw_dir == getattr(args, "_default_raw_dir", ""):
        args.raw_dir = "/tmp/testsnow_offline_smoke/raw"
    if args.report_dir == getattr(args, "_default_report_dir", ""):
        args.report_dir = "/tmp/testsnow_offline_smoke/reports"
    _install_offline_smoke_patches()


def _install_offline_smoke_patches() -> None:
    """Disable network/browser-heavy report steps for entry smoke tests.

    This is intentionally scoped to the current process and only used by
    run_stock_report.py --offline-smoke. Production report generation is
    unchanged.
    """
    for key in (
        "DEEPSEEK_API_KEY",
        "MOONSHOT_API_KEY",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ):
        os.environ.pop(key, None)

    if str(UTILS_DIR) not in sys.path:
        sys.path.insert(0, str(UTILS_DIR))

    try:
        content_quality_gate = importlib.import_module("content_quality_gate")

        def _offline_init_client(self):
            self.client = None
            self.model = ""

        def _offline_assess_batch(self, items):
            return [self._rule_based_assess(item) for item in items]

        content_quality_gate.LLMQualityAssessor._init_client = _offline_init_client
        content_quality_gate.LLMQualityAssessor.assess_batch = _offline_assess_batch
    except Exception as exc:
        logger.warning("离线 smoke 禁用质量门 LLM 失败: %s", exc)

    # content_quality_gate auto-loads .env at import time, so remove keys again
    # before modules that initialize their own LLM clients are imported later.
    for key in (
        "DEEPSEEK_API_KEY",
        "MOONSHOT_API_KEY",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ):
        os.environ.pop(key, None)

    try:
        content_consolidator = importlib.import_module("content_consolidator")

        def _offline_init_consolidator_llm(self):
            self._client = None

        content_consolidator.ContentConsolidator._init_llm = _offline_init_consolidator_llm
    except Exception as exc:
        logger.warning("离线 smoke 禁用跨源归纳 LLM 失败: %s", exc)

    try:
        knowledge_synthesizer = importlib.import_module("knowledge_synthesizer")

        def _offline_init_synthesizer_client(self):
            self.client = None

        knowledge_synthesizer.KnowledgeSynthesizer._init_client = _offline_init_synthesizer_client
    except Exception:
        # The report skill may import KnowledgeSynthesizer via the package
        # path later; environment keys were already removed, so that path will
        # still remain offline. Avoid noisy warnings for this optional patch.
        pass

    try:
        data_fetcher = importlib.import_module("reporter.data_fetcher")
        _patch_data_fetcher_module(data_fetcher)
        try:
            utils_data_fetcher = importlib.import_module("utils.reporter.data_fetcher")
            _patch_data_fetcher_module(utils_data_fetcher)
        except Exception:
            pass
    except Exception as exc:
        logger.warning("离线 smoke 禁用 renderer lazy 数据抓取失败: %s", exc)

    try:
        executive_summary = importlib.import_module(
            "utils.reporter.sections.executive_summary_renderer"
        )
        executive_summary._llm_extract_thesis = lambda text: {
            "bullish": [],
            "bearish": [],
            "conclusion": "",
        }
    except Exception as exc:
        logger.warning("离线 smoke 禁用执行摘要 LLM 失败: %s", exc)

    try:
        from utils.report_skills import data_skills

        data_skills.fetch_tencent_quote = lambda code: None
        data_skills.fetch_consensus_eps = lambda code: None
        data_skills.industry_fwd_pe = lambda stock_name: None
        data_skills.fetch_ps = lambda code, quote: None
        data_skills.fetch_competitor_metrics = lambda stock_name, stock_codes: None
    except Exception as exc:
        logger.warning("离线 smoke 禁用行情/同业数据失败: %s", exc)

    try:
        from utils.report_skills import technical_skills

        class _OfflineTechnicalCollector:
            def collect(self, *args, **kwargs):
                return None

        technical_skills.load_wind_package = lambda *args, **kwargs: {}
        technical_skills.TechnicalCollector = _OfflineTechnicalCollector
    except Exception as exc:
        logger.warning("离线 smoke 禁用技术采集失败: %s", exc)

    try:
        from utils.report_skills import chart_skills

        chart_skills.generate_technical_panel = lambda *args, **kwargs: None
        chart_skills.generate_radar_chart = lambda *args, **kwargs: None
        chart_skills.generate_bull_bear_chart = lambda *args, **kwargs: None
        chart_skills.generate_valuation_comparison = lambda *args, **kwargs: None
    except Exception as exc:
        logger.warning("离线 smoke 禁用图表生成失败: %s", exc)


def _patch_data_fetcher_module(module) -> None:
    module.fetch_tencent_quote = lambda code: None
    module.fetch_consensus_eps = lambda code: None
    module.industry_fwd_pe = lambda stock_name: None
    module.fetch_ps = lambda code, quote: None
    module.fetch_competitor_metrics = lambda stock_name, stock_codes: None


def _load_stocks_config(config_path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"配置文件不存在: {config_path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"配置文件不是合法 JSON: {config_path}: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError(f"配置文件顶层必须是股票列表: {config_path}")
    return [item for item in payload if isinstance(item, dict)]


def _write_stocks_config(config_path: Path, stocks: list[dict[str, Any]]) -> None:
    config_path.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _find_stock(stocks: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    query_norm = query.strip().upper()
    for stock in stocks:
        candidates = {
            str(stock.get("name", "")).strip().upper(),
            str(stock.get("code", "")).strip().upper(),
            str(stock.get("xueqiu_code", "")).strip().upper(),
            str(stock.get("gid", "")).strip().upper(),
        }
        if query_norm in candidates:
            return stock
    return None


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _default_bootstrap_output(stock_name: str) -> Path:
    return Path("/tmp") / f"{stock_name}_stock_config_preview.json"


def _build_default_a_stock_source_intake(keywords: list[str]) -> dict[str, Any]:
    theme_keywords = _dedupe_keep_order([
        *keywords,
        "半导体",
        "AI算力",
        "机器人",
        "汽车芯片",
        "光通信",
    ])
    research_queries = [f"{keyword} 行业研究报告" for keyword in keywords[1:] or keywords[:1]]
    research_queries.extend([
        "产业链 深度报告",
        "行业 中期策略",
        "国产替代 研究报告",
    ])
    return {
        "enabled": True,
        "a_stock": {
            "enabled": True,
            "cninfo_announcements": {
                "enabled": True,
                "lookback_days": 365,
                "max_items": 12,
                "categories": [
                    "年度报告",
                    "季度报告",
                    "业绩预告",
                    "权益分派",
                    "投资者关系活动",
                    "风险提示",
                ],
                "read_detail_content": True,
                "detail_content_categories": [
                    "业绩预告",
                    "季度报告",
                    "一季度报告",
                    "三季度报告",
                    "风险提示",
                ],
                "max_detail_items": 3,
                "detail_max_chars": 6000,
            },
            "eastmoney_stock_news": {
                "enabled": False,
                "max_items": 10,
                "lookback_days": 30,
            },
            "eastmoney_research_reports": {
                "enabled": True,
                "max_items": 8,
            },
            "eastmoney_global_news": {
                "enabled": True,
                "max_items": 5,
                "lookback_days": 30,
                "keywords": theme_keywords,
            },
            "iwencai_industry_research": {
                "enabled": True,
                "max_items": 8,
                "max_items_per_query": 3,
                "recent_days": 90,
                "fallback_days": 180,
                "queries": _dedupe_keep_order(research_queries),
            },
        },
        "evidence_notes": {
            "enabled": True,
            "dry_run": False,
        },
        "periodic_report_fulltext": {
            "enabled": True,
            "report_type": "annual_report",
        },
        "claim_verification": {
            "enabled": True,
            "risk_signals": True,
            "max_verified": 6,
            "max_supported": 4,
            "max_unverified": 6,
        },
    }


def _build_bootstrap_stock(args: argparse.Namespace) -> dict[str, Any]:
    keywords = _dedupe_keep_order([args.stock, *args.keyword])
    return {
        "name": args.stock,
        "code": args.code,
        "xueqiu_code": args.xueqiu_code,
        "gid": args.gid or args.code,
        "keywords": keywords,
        "source_intake": _build_default_a_stock_source_intake(keywords),
        "needs_review": True,
    }


def _handle_bootstrap(args: argparse.Namespace, config_path: Path, stocks: list[dict[str, Any]]) -> int:
    if args.write_config and not args.code:
        print("写入 config 前必须显式提供 --code，避免把半成品股票配置落库。", file=sys.stderr)
        return 2

    stock = _build_bootstrap_stock(args)
    if args.write_config:
        stocks.append(stock)
        _write_stocks_config(config_path, stocks)
        logger.info("已追加新股票配置: %s", config_path)
        return 0

    output_path = Path(args.bootstrap_output) if args.bootstrap_output else _default_bootstrap_output(args.stock)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(stock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("已生成股票配置预览: %s", output_path)
    return 0


def _stock_for_fetcher(stock: dict[str, Any]) -> dict[str, str]:
    return {
        "name": str(stock.get("name", "")).strip(),
        "code": str(stock.get("code", "")).strip(),
        "xueqiu_code": str(stock.get("xueqiu_code", "")).strip(),
        "gid": str(stock.get("gid", "") or stock.get("code", "")).strip(),
    }


def _keywords_for_stock(stock: dict[str, Any], cli_keywords: list[str]) -> list[str]:
    configured = stock.get("keywords")
    base = configured if isinstance(configured, list) else []
    return _dedupe_keep_order([str(stock.get("name", "")).strip(), *[str(k) for k in base], *cli_keywords])


def _empty_zhihu_data() -> dict[str, Any]:
    return {
        "report_items": [],
        "knowledge_items": [],
        "gate_stats": {},
        "total": 0,
        "api_calls": 0,
        "fast_test": True,
    }


def _load_cached_zhihu_data(raw_dir: Path, stock_name: str, date_str: str) -> dict[str, Any]:
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
            payload = json.loads(path.read_text(encoding="utf-8"))
            zhihu_data = payload.get("raw_data", {}).get(stock_name, {}).get("zhihu")
            if isinstance(zhihu_data, dict):
                logger.info("  快速测试复用知乎缓存: %s", path.name)
                return zhihu_data
        except Exception as exc:
            logger.warning("读取知乎缓存失败 %s: %s", path.name, exc)
    return {}


def _load_xueqiu_data(raw_dir: Path, stock_name: str, date_str: str) -> list[dict[str, Any]]:
    candidate = raw_dir / f"xueqiu_data_{date_str}_{stock_name}.json"
    candidates = []
    if candidate.exists():
        candidates.append(candidate)
    candidates.extend(
        p
        for p in sorted(
            raw_dir.glob(f"xueqiu_data_*_{stock_name}.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if p not in candidates
    )

    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            posts = payload.get("posts", [])
            if isinstance(posts, list):
                logger.info("从缓存加载 [%s] 雪球数据: %s 条 (%s)", stock_name, len(posts), path.name)
                return [post for post in posts if isinstance(post, dict)]
        except Exception as exc:
            logger.warning("读取雪球缓存失败 %s: %s", path.name, exc)
    logger.info("未找到任何雪球缓存文件")
    return []


def _parse_markdown_post(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    title = path.stem
    url = ""
    like = 10
    comment = 5
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            body = parts[2].strip()
            for line in frontmatter.splitlines():
                if not line or line.startswith("#") or ":" not in line:
                    continue
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip()
                if key == "title" and val:
                    title = val
                elif key in ("source_url", "url"):
                    url = val
                elif key == "likes" and val.isdigit():
                    like = int(val)
                elif key == "comments" and val.isdigit():
                    comment = int(val)

    if not title or title == path.stem:
        heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if heading:
            title = heading.group(1).strip()
    body = _CITATION_RE.sub("", body).strip() or title
    return {"title": title, "content": body, "url": url, "like": like, "comment": comment}


def _load_knowledge_posts(stock_name: str) -> list[dict[str, Any]]:
    posts_dir = REPO_ROOT / "knowledge" / "10-Stocks" / stock_name / "posts"
    if not posts_dir.exists():
        logger.info("未找到 knowledge posts 目录: %s", posts_dir)
        return []
    posts = []
    for path in sorted(posts_dir.glob("*.md")):
        try:
            posts.append(_parse_markdown_post(path))
        except Exception as exc:
            logger.warning("解析 knowledge post 失败 %s: %s", path.name, exc)
    logger.info("从 knowledge 加载 [%s] posts: %s 条", stock_name, len(posts))
    return posts


def _normalize_posts(posts: list[dict[str, Any]], stock_name: str) -> dict[str, list[dict[str, Any]]]:
    normalized = []
    for post in posts:
        item = dict(post)
        if not item.get("content"):
            item["content"] = item.get("title", "")
        if not item.get("like") and not item.get("comment"):
            item["like"] = 10
            item["comment"] = 5
        normalized.append(item)
    return {stock_name: normalized}


def _load_posts(args: argparse.Namespace, stock: dict[str, Any], raw_dir: Path, date_str: str) -> dict[str, list[dict[str, Any]]]:
    stock_name = str(stock.get("name", "")).strip()
    posts = _load_xueqiu_data(raw_dir, stock_name, date_str)
    if posts:
        return _normalize_posts(posts, stock_name)

    if args.fast_test:
        logger.info("快速测试模式：无雪球缓存，尝试 knowledge posts...")
        knowledge_posts = _load_knowledge_posts(stock_name)
        if knowledge_posts:
            return _normalize_posts(knowledge_posts, stock_name)
        logger.warning("快速测试模式未找到本地帖子缓存，使用空帖子列表")
        return {stock_name: []}

    logger.info("雪球缓存不存在，回退到东方财富...")
    fetched = fetch_all_stocks([_stock_for_fetcher(stock)], use_xueqiu=False)
    return _normalize_posts(fetched.get(stock_name, []), stock_name)


def _collect_zhihu(args: argparse.Namespace, stock: dict[str, Any], raw_dir: Path, date_str: str) -> dict[str, Any]:
    stock_name = str(stock.get("name", "")).strip()
    if args.fast_test:
        logger.info("快速测试模式：跳过知乎采集和 LLM curator")
        return _load_cached_zhihu_data(raw_dir, stock_name, date_str) or _empty_zhihu_data()

    keywords = _keywords_for_stock(stock, args.keyword)
    logger.info("采集知乎内容，关键词: %s", ", ".join(keywords))
    collector = ZhihuCollector()
    return collector.collect(stock_name=stock_name, keywords=keywords, limit=8, use_curator=True)


def _save_report_input(
    raw_dir: Path,
    date_str: str,
    stock: dict[str, Any],
    stocks_data: dict[str, list[dict[str, Any]]],
    collected_data: dict[str, Any],
) -> Path:
    stock_name = str(stock.get("name", "")).strip()
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"report_input_{date_str}_{stock_name}.json"
    payload = {
        "date": date_str,
        "stock_codes": {stock_name: str(stock.get("code", "")).strip()},
        "stocks_data": stocks_data,
        "raw_data": collected_data,
    }
    raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return raw_path


def _summarize_zhihu(zhihu_data: dict[str, Any]) -> None:
    gate_stats = zhihu_data.get("gate_stats", {})
    logger.info("知乎采集完成: 总计 %s 条", zhihu_data.get("total", 0))
    logger.info(
        "质量门: 保留=%s, 降级=%s, 丢弃=%s",
        gate_stats.get("keep", 0),
        gate_stats.get("demote", 0),
        gate_stats.get("discard", 0),
    )
    logger.info(
        "报告用: %s 条, 知识沉淀: %s 条",
        len(zhihu_data.get("report_items", [])),
        len(zhihu_data.get("knowledge_items", [])),
    )


def _run_report(args: argparse.Namespace, stock: dict[str, Any]) -> int:
    stock_name = str(stock.get("name", "")).strip()
    date_str = args.date or datetime.now().strftime("%Y%m%d")
    raw_dir = Path(args.raw_dir)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 50)
    logger.info("%s 单股深度报告生成", stock_name)
    logger.info("日期: %s", date_str)
    logger.info("=" * 50)

    logger.info("[1/4] 加载帖子数据...")
    stocks_data = _load_posts(args, stock, raw_dir, date_str)

    logger.info("[2/4] 准备知乎/深度材料...")
    zhihu_data = _collect_zhihu(args, stock, raw_dir, date_str)
    _summarize_zhihu(zhihu_data)

    collected_data = {stock_name: {"zhihu": zhihu_data}}
    raw_path = _save_report_input(raw_dir, date_str, stock, stocks_data, collected_data)
    logger.info("[3/4] 原始数据已保存: %s", raw_path)

    logger.info("[4/4] 生成报告...")
    reporter = PerStockReporter(
        stocks_data=stocks_data,
        stock_codes={stock_name: str(stock.get("code", "")).strip()},
        raw_data=collected_data,
        agent_reach_configs={stock_name: stock["agent_reach"]} if stock.get("agent_reach") else {},
        source_intake_configs={stock_name: stock["source_intake"]} if stock.get("source_intake") else {},
    )
    md_path, html_path = reporter.generate_stock_report(stock_name, str(report_dir))
    if md_path:
        logger.info("报告已生成: %s", md_path)
    if html_path:
        logger.info("Dashboard 已生成: %s", html_path)

    if md_path and not args.no_pdf:
        logger.info("导出 PDF...")
        try:
            pdf_path = export_pdf(
                md_path,
                title=f"{stock_name}_{date_str}",
                header_text=f"{stock_name} 舆情深度报告",
                footer_text=f"{stock_name} | {date_str}",
            )
            logger.info("PDF已生成: %s", pdf_path)
        except Exception as exc:
            logger.warning("PDF导出失败: %s", exc)

    logger.info("全流程完成")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.offline_smoke:
        _apply_offline_smoke_mode(args)

    config_path = Path(args.config)
    try:
        stocks = _load_stocks_config(config_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    stock = _find_stock(stocks, args.stock)
    if stock is None:
        if args.bootstrap_config:
            return _handle_bootstrap(args, config_path, stocks)
        print(
            f"未找到股票配置: {args.stock}。请先运行 --bootstrap-config 生成配置草稿，"
            "补齐 code/xueqiu_code/关键词后再生成正式报告。",
            file=sys.stderr,
        )
        return 2

    if args.bootstrap_config:
        print(f"股票已存在于配置中: {stock.get('name')}", file=sys.stderr)
        return 2

    return _run_report(args, stock)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
