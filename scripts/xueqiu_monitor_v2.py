#!/usr/bin/env python3
"""
雪球股票舆情监控系统 v2

每周手动运行，采集 6 只持仓股票的社区舆情，生成 Markdown 分析报告。

用法:
    cd scripts
    python xueqiu_monitor_v2.py

环境变量:
    MOONSHOT_API_KEY: Kimi (Moonshot) API 密钥（用于 LLM 分析）
    MOONSHOT_MODEL: 模型名称，默认 moonshot-v1-128k
    USE_XUEQIU: 是否尝试雪球（需要 Chrome 已登录），默认 false
    XUEQIU_CDP_URL: Chrome DevTools Protocol 地址，默认 http://localhost:9222
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

# 加载 .env 文件中的环境变量
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# 将 utils 加入路径
sys.path.insert(0, str(Path(__file__).parent))

from utils.fetcher import fetch_all_stocks
from utils.analyzer import KimiAnalyzer
from utils.reporter import ReportManager
from utils.data_collector import TechnicalCollector, ReportCollector, AnnouncementCollector, FundFlowCollector, NewsCollector
from utils.financial_agent import FinancialAgent
from utils.obsidian_writer import ObsidianWriter


def setup_logging(level=logging.INFO):
    """配置日志输出"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def load_stocks_config(config_path: str = None) -> list:
    """加载股票配置"""
    if not config_path:
        config_path = Path(__file__).parent.parent / "config" / "stocks.json"

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_monitor(use_xueqiu: bool = False, xueqiu_cdp_url: str = None):
    """
    主执行流程
    """
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("股票舆情监控系统启动")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    # 1. 加载配置
    try:
        stocks = load_stocks_config()
        logger.info(f"加载 {len(stocks)} 只股票配置")
        for s in stocks:
            logger.info(f"  - {s['name']} ({s.get('xueqiu_code', 'N/A')}) [东财GID: {s.get('gid', 'N/A')}]")
    except Exception as e:
        logger.error(f"加载配置失败: {e}")
        return 1

    # 2. 采集数据
    logger.info("\n开始数据采集...")
    try:
        stocks_data = fetch_all_stocks(
            stocks,
            use_xueqiu=use_xueqiu,
            xueqiu_cdp_url=xueqiu_cdp_url or "http://localhost:9222"
        )
        total_posts = sum(len(posts) for posts in stocks_data.values())
        logger.info(f"数据采集完成，共 {total_posts} 条帖子")
    except Exception as e:
        logger.error(f"数据采集失败: {e}")
        return 1

    # 2b. 采集扩展数据（P0: 技术指标, 研报, 公告）
    date_str = datetime.now().strftime("%Y%m%d")
    raw_data_dir = Path(__file__).parent.parent / "data" / "raw" / date_str
    raw_data_dir.mkdir(parents=True, exist_ok=True)

    tech_collector = TechnicalCollector()
    report_collector = ReportCollector()
    ann_collector = AnnouncementCollector()
    fund_collector = FundFlowCollector()
    news_collector = NewsCollector()
    writer = ObsidianWriter()
    agent = FinancialAgent()

    collected_data = {}  # stock_name -> raw data dict

    for stock in stocks:
        name = stock["name"]
        code = stock["code"]
        # Skip technical/fund for HK stocks
        is_hk = code.startswith("0") and len(code) == 5
        market = 0 if code.startswith(("00", "30")) else 1

        logger.info(f"采集 {name} ({code}) 扩展数据...")
        stock_raw = {}

        if not is_hk:
            # Technical
            tech_data = tech_collector.collect(code, market=market, days=120)
            if tech_data:
                (raw_data_dir / f"technical_{code}.json").write_text(
                    json.dumps(tech_data, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
                )
                writer.write_atomic_note(
                    stock_name=name, code=code, date=date_str,
                    category="技术指标", data=tech_data.get("indicators", {}),
                    data_source="mootdx+stockstats", valid_days=1,
                )
                stock_raw["technical"] = tech_data
                if tech_data.get("price_target"):
                    stock_raw["price_target"] = tech_data["price_target"]

            # Reports
            reports = report_collector.collect(code, months=4)
            if reports:
                (raw_data_dir / f"reports_{code}.json").write_text(
                    json.dumps(reports, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
                )
                writer.write_atomic_note(
                    stock_name=name, code=code, date=date_str,
                    category="最新研报", data={"reports": reports},
                    data_source="akshare/东财", valid_days=90,
                )
                stock_raw["reports"] = reports

            # Announcements
            anns = ann_collector.collect(code, months=3)
            if anns:
                (raw_data_dir / f"announcements_{code}.json").write_text(
                    json.dumps(anns, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
                )
                writer.write_atomic_note(
                    stock_name=name, code=code, date=date_str,
                    category="公司公告", data={"announcements": anns},
                    data_source="巨潮/akshare", valid_days=30,
                )
                stock_raw["announcements"] = anns

            # Fund flow (P1)
            fund = fund_collector.collect(code, days=7)
            if fund:
                (raw_data_dir / f"fundflow_{code}.json").write_text(
                    json.dumps(fund, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
                )
                stock_raw["fundflow"] = fund

            # News (P1)
            news = news_collector.collect(code, days=30)
            if news:
                (raw_data_dir / f"news_{code}.json").write_text(
                    json.dumps(news, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
                )
                stock_raw["news"] = news

            # Run FinancialAgent
            all_data = {
                "technical": stock_raw.get("technical", {}),
                "reports": stock_raw.get("reports", []),
                "announcements": stock_raw.get("announcements", []),
                "fundflow": stock_raw.get("fundflow", []),
                "news": stock_raw.get("news", []),
                "sentiment": stocks_data.get(name, []),
            }
            analysis = agent.analyze(name, code, all_data)
            stock_raw["analysis"] = analysis

            # Write deep analysis note
            writer.write_atomic_note(
                stock_name=name, code=code, date=date_str,
                category="深度分析", data=analysis,
                data_source="FinancialAgent/Kimi", valid_days=7,
                analysis=analysis.get("report_markdown", ""),
            )

            # Update MOC
            writer.update_moc(name, code, date_str, [
                f"{date_str}-技术指标",
                f"{date_str}-最新研报",
                f"{date_str}-公司公告",
                f"{date_str}-深度分析",
            ])

        collected_data[name] = stock_raw

    # 3. 保存原始数据
    report_mgr = ReportManager()
    try:
        raw_path = report_mgr.save_raw_data(stocks_data)
    except Exception as e:
        logger.warning(f"保存原始数据失败: {e}")

    # 4. 生成个股深度报告
    logger.info("\n生成个股深度报告...")
    try:
        from utils.stock_reporter import PerStockReporter
        stock_codes = {s["name"]: s["code"] for s in stocks}
        agent_reach_configs = {
            s["name"]: s["agent_reach"]
            for s in stocks
            if s.get("agent_reach")
        }
        reporter = PerStockReporter(
            stocks_data=stocks_data,
            stock_codes=stock_codes,
            raw_data=collected_data,
            agent_reach_configs=agent_reach_configs,
        )
        report_paths = reporter.generate_all_reports(output_dir=report_mgr.report_dir)
        for rp in report_paths:
            logger.info(f"  报告已生成: {rp}")
    except Exception as e:
        logger.error(f"生成个股报告失败: {e}")
        return 1

        # Update weekly index for periodic reports
        for stock in stocks:
            name = stock["name"]
            code = stock["code"]
            report_path = report_mgr.report_dir / f"{name}.md"
            note_path = f"knowledge/10-Stocks/{name}/{date_str}-深度分析.md"
            writer.update_weekly_index(code, date_str, str(note_path), str(report_path))

    # 5. 导出PDF
    logger.info("\n导出 PDF 报告...")
    try:
        from utils.pdf_exporter import export_pdf
        for rp in report_paths:
            if rp.endswith(".md"):
                try:
                    pdf_path = export_pdf(rp, title=Path(rp).stem)
                    logger.info(f"  PDF已生成: {pdf_path}")
                except Exception as e:
                    logger.warning(f"  PDF导出失败 [{rp}]: {e}")
    except Exception as e:
        logger.warning(f"PDF导出失败: {e}")

    logger.info("\n" + "=" * 50)
    logger.info("舆情监控任务完成")
    logger.info("=" * 50)
    return 0


def main():
    parser = argparse.ArgumentParser(description="股票舆情监控系统")
    parser.add_argument(
        "--xueqiu", action="store_true",
        help="优先尝试雪球（需要 Chrome 已登录并开启远程调试）"
    )
    parser.add_argument(
        "--cdp-url", default="http://localhost:9222",
        help="Chrome DevTools Protocol 地址（默认: http://localhost:9222）"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="输出详细日志"
    )
    args = parser.parse_args()

    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)

    # 从环境变量读取配置
    use_xueqiu = args.xueqiu or os.getenv("USE_XUEQIU", "false").lower() == "true"
    cdp_url = os.getenv("XUEQIU_CDP_URL", args.cdp_url)

    if use_xueqiu:
        logging.getLogger(__name__).info("已启用雪球采集（增强模式）")
        logging.getLogger(__name__).info(
            "提示: 请确保 Chrome 已启动远程调试: "
            "/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222"
        )

    exit_code = run_monitor(use_xueqiu=use_xueqiu, xueqiu_cdp_url=cdp_url)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
