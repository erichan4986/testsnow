#!/usr/bin/env python3
"""
圣邦股份 demo - 快速生成新格式报告
"""
import json
import sys
from pathlib import Path
from datetime import datetime

# Load .env before any module imports that need API keys
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# Ensure scripts directory is in path for absolute imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils.data_collector import TechnicalCollector, ReportCollector, AnnouncementCollector, FundFlowCollector, NewsCollector, ZhihuCollector
from scripts.utils.financial_agent import FinancialAgent
from scripts.utils.obsidian_writer import ObsidianWriter
from scripts.utils.stock_reporter import PerStockReporter
from scripts.utils.reporter import ReportManager

logger = __import__("logging").getLogger(__name__)


def main():
    stock_name = "圣邦股份"
    code = "300661"
    market = 0  # Shenzhen
    date_str = datetime.now().strftime("%Y%m%d")

    print(f"=== 圣邦股份 ({code}) 多维度报告生成 ===\n")

    # 1. 采集技术指标
    print("[1/6] 采集技术指标...")
    tech = TechnicalCollector()
    tech_data = tech.collect(code, market=market, days=120)
    if tech_data:
        print(f"  - 收盘价: {tech_data['indicators'].get('close')}")
        print(f"  - MACD: {tech_data['indicators'].get('macd')}")
        print(f"  - RSI(14): {tech_data['indicators'].get('rsi_14')}")
        print(f"  - MA60: {tech_data['indicators'].get('ma_60')}")
        print(f"  - 布林带: [{tech_data['indicators'].get('boll_lower')}, {tech_data['indicators'].get('boll_mid')}, {tech_data['indicators'].get('boll_upper')}]")
    else:
        print("  - 技术指标采集失败")

    # 2. 采集研报
    print("\n[2/6] 采集最新研报...")
    reports = ReportCollector().collect(code, months=4)
    print(f"  - 获取 {len(reports)} 篇研报")
    for r in reports[:3]:
        print(f"    [{r.get('institution')}] {r.get('title')[:30]}... | 评级:{r.get('rating')} | 目标价:{r.get('target_price')}")

    # 3. 采集公告
    print("\n[3/6] 采集公司公告...")
    anns = AnnouncementCollector().collect(code, months=3)
    print(f"  - 获取 {len(anns)} 条公告")
    for a in anns[:3]:
        important = " [重要]" if a.get("is_important") else ""
        print(f"    [{a.get('date')}] {a.get('title')[:30]}... ({a.get('type')}){important}")

    # 4. 采集资金流向
    print("\n[4/6] 采集资金流向...")
    fund = FundFlowCollector().collect(code, days=7)
    print(f"  - 获取 {len(fund)} 日资金流向")
    for f in fund[:3]:
        print(f"    [{f.get('date')}] 主力净流入: {f.get('main_inflow'):.0f}万")

    # 5. 采集新闻
    print("\n[5/6] 采集个股新闻...")
    news = NewsCollector().collect(code, days=30)
    print(f"  - 获取 {len(news)} 条新闻")
    for n in news[:3]:
        print(f"    [{n.get('source')}] {n.get('title')[:40]}...")

    # 6. 采集知乎内容
    print("\n[6/6] 采集知乎内容...")
    zhihu = ZhihuCollector()
    zhihu_data = zhihu.collect(
        stock_name=stock_name,
        keywords=["模拟芯片", "信号链", "电源管理芯片", "国产替代", "半导体", "模拟IC", "芯片设计",
                  "思瑞浦", "杰华特", "纳芯微", "艾为电子"],
        limit=8,
    )
    report_items = zhihu_data.get("report_items", [])
    knowledge_items = zhihu_data.get("knowledge_items", [])
    gate_stats = zhihu_data.get("gate_stats", {})
    print(f"  - 知乎+全网共采集 {zhihu_data.get('total', 0)} 条")
    if gate_stats:
        print(f"    质量门: 硬指标通过 {gate_stats.get('hard_passed', 0)}/{gate_stats.get('total', 0)} → keep {gate_stats.get('keep', 0)} 条")
    print(f"    报告纳入: {len(report_items)} 条")
    print(f"    知识沉淀: {len(knowledge_items)} 条")
    for z in report_items[:5]:
        qg = z.get("_quality_gate", {})
        score = qg.get("quality_score", 0)
        src = z.get("source_platform", "知乎")
        print(f"    [纳入][{src}][质量{score}][{z.get('author_name')}] {z.get('title')[:40]}...")
    for z in knowledge_items[:2]:
        qg = z.get("_quality_gate", {})
        reasons = qg.get("reasons", ["未通过筛选"])
        reason = reasons[0] if reasons else "未通过筛选"
        print(f"    [沉淀][{reason}][{z.get('author_name')}] {z.get('title')[:40]}...")

    # 7. 写入 Obsidian vault
    print("\n[Obsidian] 写入原子笔记...")
    writer = ObsidianWriter()
    if tech_data:
        writer.write_atomic_note(stock_name, code, date_str, "技术指标",
                                 tech_data.get("indicators", {}), "mootdx+stockstats", valid_days=1)
    if reports:
        writer.write_atomic_note(stock_name, code, date_str, "最新研报",
                                 {"reports": reports}, "akshare/东财", valid_days=90)
    if anns:
        writer.write_atomic_note(stock_name, code, date_str, "公司公告",
                                 {"announcements": anns}, "巨潮/akshare", valid_days=30)
    if report_items:
        writer.write_atomic_note(stock_name, code, date_str, "知乎相关",
                                 {"zhihu_items": report_items}, "知乎API", valid_days=7)
    if knowledge_items:
        writer.write_atomic_note(stock_name, code, date_str, "知乎沉淀",
                                 {"zhihu_items": knowledge_items}, "知乎API", valid_days=30)
    writer.update_moc(stock_name, code, date_str, [
        f"{date_str}-技术指标", f"{date_str}-最新研报",
        f"{date_str}-公司公告", f"{date_str}-知乎相关",
        f"{date_str}-知乎沉淀", f"{date_str}-深度分析"
    ])
    print("  - MOC 已更新")

    # 8. FinancialAgent 分析
    print("\n[Kimi] 调用 FinancialAgent 深度分析...")
    agent = FinancialAgent()
    all_data = {
        "technical": tech_data or {},
        "reports": reports,
        "announcements": anns,
        "fundflow": fund,
        "news": news,
        "zhihu": report_items,
        "sentiment": [],
    }
    analysis = agent.analyze(stock_name, code, all_data)
    if analysis.get("confirmed_facts") and analysis["confirmed_facts"][0] != "Kimi API 未启用，无法生成深度分析":
        print(f"  - 确认事实: {len(analysis.get('confirmed_facts', []))} 条")
        print(f"  - 推断: {len(analysis.get('inferences', []))} 条")
        print(f"  - 观点: {len(analysis.get('opinions', []))} 条")
        print(f"  - 仓位建议: {analysis.get('position_suggestion', 'N/A')}")
    else:
        print("  - MOONSHOT_API_KEY 未设置，使用 fallback 分析")

    # 写入深度分析笔记
    writer.write_atomic_note(stock_name, code, date_str, "深度分析",
                             analysis, "FinancialAgent/Kimi", valid_days=7,
                             analysis=analysis.get("report_markdown", ""))

    # 9. 生成报告
    print("\n[Report] 生成 Markdown 报告...")
    report_mgr = ReportManager()
    collected_data = {
        stock_name: {
            "technical": tech_data,
            "reports": reports,
            "announcements": anns,
            "fundflow": fund,
            "news": news,
            "zhihu": zhihu_data,
            "analysis": analysis,
        }
    }
    # 构造双轨 dummy 数据让 reporter 不跳过
    dummy_posts = [
        {"title": "Demo post", "author": "demo", "content": "demo content with enough length to pass quality gate", "comment_count": 0, "like_count": 0, "_track": "featured"},
        {"title": "Demo sentiment", "author": "demo", "content": "demo", "comment_count": 0, "like_count": 0, "_track": "sentiment"},
    ]
    collected_data[stock_name]["_keep_posts"] = dummy_posts
    dummy_posts = [
        {"title": "Demo post", "author": "demo", "content": "demo content with enough length to pass quality gate", "comment_count": 0, "like_count": 0, "_track": "featured"},
        {"title": "Demo sentiment", "author": "demo", "content": "demo", "comment_count": 0, "like_count": 0, "_track": "sentiment"},
    ]
    reporter = PerStockReporter(
        stocks_data={stock_name: dummy_posts},
        stock_codes={stock_name: code},
        raw_data=collected_data,
    )
    report_path = reporter.generate_stock_report(stock_name, str(report_mgr.report_dir))
    print(f"  - 报告已生成: {report_path}")

    # 10. 导出 PDF
    print("\n[PDF] 导出 PDF 报告...")
    try:
        from scripts.utils.pdf_exporter import export_pdf
        date_str = reporter.date_display if reporter else ""
        pdf_path = export_pdf(
            report_path,
            title=f"{stock_name} 舆情深度报告",
            header_text=f"{stock_name} 舆情深度报告",
            footer_text=f"{stock_name} | {date_str}",
        )
        print(f"  - PDF 已生成: {pdf_path}")
    except Exception as e:
        print(f"  - PDF 导出失败: {e}")

    # 11. 显示报告路径
    print(f"\n{'='*50}")
    print(f"完成！报告位置:")
    print(f"  Markdown: {report_path}")
    print(f"  PDF:      {pdf_path if 'pdf_path' in dir() else 'N/A'}")
    print(f"  Obsidian: knowledge/10-Stocks/圣邦股份/")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
