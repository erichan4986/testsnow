"""
个股深度报告生成器

基于雪球采集数据，为每只股票生成独立的深度舆情分析报告，
包含竞争格局对比、精品帖子深度解读（>=150字+判断）、关键评论摘录等。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class PerStockReporter:
    """个股深度报告生成器 —— 仅保留 facade 接口，所有板块渲染已迁移至 SectionRenderers。"""

    def __init__(self, stocks_data: Dict[str, List[Dict]] = None, data_path: str = None, stock_codes: Dict[str, str] = None, raw_data: Dict[str, Any] = None):
        """
        Args:
            stocks_data: 直接传入股票数据字典
            data_path: 或从JSON文件路径加载
            stock_codes: 股票名称到6位代码的映射，如 {"乐鑫科技": "688018"}
            raw_data: 原始采集数据（研报、公告、资金流向等）
        """
        if stocks_data:
            self.stocks_data = stocks_data
        elif data_path:
            with open(data_path, "r", encoding="utf-8") as f:
                self.stocks_data = json.load(f)
        else:
            self.stocks_data = {}

        self.stock_codes = stock_codes or {}
        self.raw_data = raw_data or {}
        self.date_str = datetime.now().strftime("%Y%m%d")
        self.date_display = datetime.now().strftime("%Y年%m月%d日")

    def generate_all_reports(self, output_dir: str = None) -> List[str]:
        """
        生成所有股票的深度报告

        Returns:
            生成的Markdown文件路径列表
        """
        if output_dir is None:
            output_dir = Path(__file__).parent.parent.parent / "reports"
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        report_paths = []
        for stock_name in self.stocks_data:
            md_path, html_path = self.generate_stock_report(stock_name, str(output_dir))
            if md_path:
                report_paths.append(md_path)
            if html_path:
                report_paths.append(html_path)
            logger.info(f"[{stock_name}] 深度报告已生成: {md_path} | Dashboard: {html_path}")

        # 同时生成一份汇总简报
        summary_path = self._generate_summary_report(str(output_dir))
        report_paths.append(summary_path)
        logger.info(f"汇总简报已生成: {summary_path}")

        return report_paths

    def generate_stock_report(self, stock_name: str, output_dir: str) -> tuple:
        """
        生成单只股票的深度报告（Pipeline 入口，接口不变）。
        """
        all_posts = self.stocks_data.get(stock_name, [])
        if not all_posts:
            logger.warning(f"[{stock_name}] 无数据，跳过")
            return "", ""

        try:
            from .report_skills import build_stock_report_pipeline
            pipeline = build_stock_report_pipeline()
            ctx = pipeline.run({
                "stock_name": stock_name,
                "date_str": self.date_str,
                "output_dir": output_dir,
                "stocks_data": self.stocks_data,
                "raw_data": self.raw_data,
                "stock_codes": self.stock_codes,
            })
            md_path = ctx.output.get("md_path", "")
            html_path = ctx.output.get("html_path", "")
            if md_path:
                logger.info(f"[{stock_name}] 报告已生成: {md_path}")
            if html_path:
                logger.info(f"[{stock_name}] Dashboard 已生成: {html_path}")
            return md_path, html_path
        except Exception as e:
            logger.error(f"[{stock_name}] Pipeline 执行失败: {e}")
            return "", ""

    def _generate_summary_report(self, output_dir: str) -> str:
        """生成汇总简报"""
        from .reporter.scoring_engine import classify_sentiment

        lines = [
            f"# 雪球舆情监控汇总简报 ({self.date_display})",
            "",
            "## 市场情绪速览",
            "",
            "| 股票 | 情绪 | 热度 | 核心看点 |",
            "|------|------|------|----------|",
        ]

        for stock_name, posts in self.stocks_data.items():
            total = len(posts)
            likes = sum(p.get("like_count", 0) for p in posts)
            comments = sum(p.get("comment_count", 0) for p in posts)
            bullish, bearish, neutral = classify_sentiment(posts)
            sentiment = "看多" if len(bullish) > len(bearish) else "看空" if len(bearish) > len(bullish) else "中性"
            heat = "🔥" if likes + comments > 100 else "🌡️" if likes + comments > 50 else "❄️"

            key_point = {
                "黑芝麻智能": "智驾量产+做空风险并存",
                "长春高新": "套牢严重+融资盘风险",
                "三花智控": "特斯拉机器人核心供应商",
                "中简科技": "Q1暴雷+长期军工逻辑",
                "圣邦股份": "模拟芯片周期反转",
                "乐鑫科技": "端侧AI+量化控盘",
            }.get(stock_name, "")

            lines.append(f"| {stock_name} | {sentiment} | {heat} | {key_point} |")

        lines.extend([
            "",
            "## 本周最热赛道",
            "",
            "1. **特斯拉人形机器人/物理AI** — 三花智控、圣邦股份受益",
            "2. **智能驾驶/AEB强制标准** — 黑芝麻智能催化",
            "3. **碳纤维/商业航天** — 中简科技长期期权",
            "",
            "## 风险提示",
            "",
            "- 🔴 **黑芝麻智能**: 港股通退通风险（市值接近65亿红线）",
            "- 🔴 **长春高新**: 融资盘爆仓风险",
            "- 🟡 **三花智控**: 短期涨幅过大回调风险",
            "- 🟡 **圣邦股份**: 杰华特竞争威胁",
            "",
            f"*详细个股报告请查看同目录下 `{self.date_str}` 日期的个股文件。*",
            "",
            f"*报告生成时间: {self.date_display}*",
        ])

        markdown = "\n".join(lines)
        filepath = Path(output_dir) / f"xueqiu_summary_{self.date_str}.md"
        filepath.write_text(markdown, encoding="utf-8")
        return str(filepath)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python stock_reporter.py <数据JSON路径> [输出目录]")
        sys.exit(1)

    data_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    reporter = PerStockReporter(data_path=data_path)
    paths = reporter.generate_all_reports(output_dir)
    print(f"共生成 {len(paths)} 份报告:")
    for p in paths:
        print(f"  - {p}")
