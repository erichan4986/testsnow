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

    def __init__(
        self,
        stocks_data: Dict[str, List[Dict]] = None,
        data_path: str = None,
        stock_codes: Dict[str, str] = None,
        raw_data: Dict[str, Any] = None,
        agent_reach_configs: Dict[str, Dict] = None,
        source_intake_configs: Dict[str, Dict] = None,
        enable_agent_reach: bool = False,
        enable_periodic_report_fulltext_intake: bool = False,
    ):
        """
        Args:
            stocks_data: 直接传入股票数据字典
            data_path: 或从JSON文件路径加载
            stock_codes: 股票名称到6位代码的映射，如 {"乐鑫科技": "688018"}
            raw_data: 原始采集数据（研报、公告、资金流向等）
            agent_reach_configs: 每只股票 Agent-Reach 配置
            source_intake_configs: 每只股票 Source Intake v2 配置
            enable_agent_reach: 全局启用 Agent-Reach（默认 False）
            enable_periodic_report_fulltext_intake: 全局启用年报全文材料层（默认 False；单股配置优先）
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
        self.agent_reach_configs = agent_reach_configs or {}
        self.source_intake_configs = source_intake_configs or {}
        self.enable_agent_reach = enable_agent_reach
        self.enable_periodic_report_fulltext_intake = enable_periodic_report_fulltext_intake
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
        ar_cfg = self.agent_reach_configs.get(stock_name, {})
        si_cfg = self.source_intake_configs.get(stock_name, {})
        agent_reach_enabled = self.enable_agent_reach or ar_cfg.get("enabled", False)
        source_intake_enabled = bool(si_cfg.get("enabled", False))
        if not all_posts and not agent_reach_enabled and not source_intake_enabled:
            logger.warning(f"[{stock_name}] 无数据，跳过")
            return "", ""

        try:
            from .report_skills import build_stock_report_pipeline

            periodic_fulltext_cfg = si_cfg.get("periodic_report_fulltext", {}) or {}
            if "enabled" in periodic_fulltext_cfg:
                periodic_fulltext_requested = bool(periodic_fulltext_cfg.get("enabled", False))
            else:
                periodic_fulltext_requested = bool(self.enable_periodic_report_fulltext_intake)
            periodic_fulltext_enabled = bool(
                source_intake_enabled and periodic_fulltext_requested
            )
            narrative_display_cfg = (
                si_cfg.get("periodic_narrative_cards_synthesis_display", {}) or {}
            )
            narrative_display_enabled = bool(
                source_intake_enabled and narrative_display_cfg.get("enabled", False)
            )
            broker_digest_display_cfg = (
                si_cfg.get("broker_research_digest_synthesis_display", {}) or {}
            )
            broker_digest_display_enabled = bool(
                source_intake_enabled and broker_digest_display_cfg.get("enabled", False)
            )
            viewpoint_narrative_cfg = (
                si_cfg.get("curated_external_viewpoint_narrative_synthesis_display", {}) or {}
            )
            viewpoint_narrative_enabled = bool(
                source_intake_enabled and viewpoint_narrative_cfg.get("enabled", False)
            )
            viewpoint_narrative_json = self._resolve_repo_relative_path(
                viewpoint_narrative_cfg.get("narrative_json", "")
            )
            viewpoint_digest_cfg = (
                si_cfg.get("curated_external_viewpoint_digest_synthesis_display", {}) or {}
            )
            viewpoint_digest_enabled = bool(
                source_intake_enabled and viewpoint_digest_cfg.get("enabled", False)
            )
            viewpoint_digest_json = self._resolve_repo_relative_path(
                viewpoint_digest_cfg.get("digest_json", "")
            )
            ar_evidence_cfg = ar_cfg.get("evidence_notes", {}) or {}
            si_evidence_cfg = si_cfg.get("evidence_notes", {}) or {}
            evidence_notes_enabled = bool(
                (agent_reach_enabled and ar_evidence_cfg.get("enabled", False))
                or (source_intake_enabled and si_evidence_cfg.get("enabled", False))
            )
            cv_cfg = ar_cfg.get("claim_verification", {}) or si_cfg.get("claim_verification", {}) or {}
            claim_verification_enabled = bool(cv_cfg.get("enabled", False))
            claim_risk_signals_enabled = bool(cv_cfg.get("risk_signals", False))
            pipeline_kwargs = {
                "enable_agent_reach": agent_reach_enabled,
                "enable_evidence_notes": evidence_notes_enabled,
                "enable_claim_risk_signals": claim_risk_signals_enabled,
                "enable_source_intake": source_intake_enabled,
            }
            if periodic_fulltext_enabled:
                pipeline_kwargs["enable_periodic_report_fulltext_intake"] = True
            if viewpoint_digest_enabled:
                pipeline_kwargs["include_curated_external_viewpoint_digest_in_deep_analysis_display"] = True
                pipeline_kwargs["curated_external_viewpoint_digest_json"] = viewpoint_digest_json
            if viewpoint_narrative_enabled:
                pipeline_kwargs["include_curated_external_viewpoint_narrative_in_deep_analysis_display"] = True
                pipeline_kwargs["curated_external_viewpoint_narrative_json"] = viewpoint_narrative_json
            pipeline = build_stock_report_pipeline(**pipeline_kwargs)

            pipeline_input = {
                "stock_name": stock_name,
                "date_str": self.date_str,
                "output_dir": output_dir,
                "stocks_data": self.stocks_data,
                "raw_data": self.raw_data,
                "stock_codes": self.stock_codes,
                "enable_claim_risk_signals": claim_risk_signals_enabled,
            }

            if claim_verification_enabled:
                pipeline_input["enable_claim_verification_context"] = True

            if claim_verification_enabled or claim_risk_signals_enabled:
                if cv_cfg.get("base_dir"):
                    pipeline_input["claim_verification_base_dir"] = cv_cfg["base_dir"]
                if cv_cfg.get("max_verified") is not None:
                    pipeline_input["claim_verification_max_verified"] = cv_cfg["max_verified"]
                if cv_cfg.get("max_supported") is not None:
                    pipeline_input["claim_verification_max_supported"] = cv_cfg["max_supported"]
                if cv_cfg.get("max_unverified") is not None:
                    pipeline_input["claim_verification_max_unverified"] = cv_cfg["max_unverified"]

            if agent_reach_enabled:
                pipeline_input["enable_agent_reach"] = True
                web_urls = ar_cfg.get("web_urls", []) or ar_cfg.get("urls", [])
                if web_urls:
                    pipeline_input["agent_reach_urls"] = web_urls
                rss_feeds = ar_cfg.get("rss_feeds", [])
                if rss_feeds:
                    pipeline_input["agent_reach_rss_feeds"] = rss_feeds
                rss_filter_terms = ar_cfg.get("rss_filter_terms", [])
                if rss_filter_terms:
                    pipeline_input["agent_reach_rss_filter_terms"] = rss_filter_terms
                official_domains = ar_cfg.get("official_domains", [])
                if official_domains:
                    pipeline_input["agent_reach_official_domains"] = official_domains

            if source_intake_enabled:
                pipeline_input["source_intake_enabled"] = True
                pipeline_input["source_intake_config"] = si_cfg

            if periodic_fulltext_enabled:
                if periodic_fulltext_cfg.get("cache_dir"):
                    pipeline_input["periodic_report_fulltext_cache_dir"] = periodic_fulltext_cfg["cache_dir"]
                if periodic_fulltext_cfg.get("report_type"):
                    pipeline_input["periodic_report_fulltext_report_type"] = periodic_fulltext_cfg["report_type"]

            if narrative_display_enabled:
                pipeline_input["include_periodic_narrative_cards_in_synthesis_display"] = True
                if narrative_display_cfg.get("max_display_items") is not None:
                    pipeline_input["periodic_narrative_cards_max_display_items"] = (
                        narrative_display_cfg["max_display_items"]
                    )

            if broker_digest_display_enabled:
                pipeline_input["include_broker_research_digest_in_synthesis_display"] = True
                if broker_digest_display_cfg.get("max_display_items") is not None:
                    pipeline_input["broker_research_digest_max_display_items"] = (
                        broker_digest_display_cfg["max_display_items"]
                    )

            if viewpoint_digest_enabled:
                pipeline_input["include_curated_external_viewpoint_digest_in_deep_analysis_display"] = True
                pipeline_input["curated_external_viewpoint_digest_json"] = viewpoint_digest_json

            if viewpoint_narrative_enabled:
                pipeline_input["include_curated_external_viewpoint_narrative_in_deep_analysis_display"] = True
                pipeline_input["curated_external_viewpoint_narrative_json"] = viewpoint_narrative_json

            if evidence_notes_enabled:
                pipeline_input["enable_evidence_notes"] = True
                evidence_cfg = ar_evidence_cfg if ar_evidence_cfg.get("enabled") else si_evidence_cfg
                pipeline_input["evidence_notes_dry_run"] = evidence_cfg.get("dry_run", True)
                if evidence_cfg.get("base_dir"):
                    pipeline_input["knowledge_base_dir"] = evidence_cfg["base_dir"]

            ctx = pipeline.run(pipeline_input)
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

    @staticmethod
    def _resolve_repo_relative_path(path_value: str) -> str:
        """Resolve config file paths relative to the repository root."""
        if not path_value:
            return ""
        path = Path(path_value)
        if path.is_absolute():
            return str(path)
        repo_root = Path(__file__).resolve().parents[2]
        return str(repo_root / path)

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
