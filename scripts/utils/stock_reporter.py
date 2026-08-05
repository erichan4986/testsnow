"""
个股深度报告生成器

基于雪球采集数据，为每只股票生成独立的深度舆情分析报告，
包含竞争格局对比、精品帖子深度解读（>=150字+判断）、关键评论摘录等。
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from .report_run_plan import compile_report_run_plan

logger = logging.getLogger(__name__)


class PerStockReporter:
    """个股深度报告生成 facade；板块渲染由 SectionRenderers 负责。"""

    def __init__(
        self,
        stocks_data: Dict[str, List[Dict]] = None,
        stock_codes: Dict[str, str] = None,
        raw_data: Dict[str, Any] = None,
        agent_reach_configs: Dict[str, Dict] = None,
        source_intake_configs: Dict[str, Dict] = None,
        stock_configs: Dict[str, Dict] = None,
        enable_agent_reach: bool = False,
        enable_periodic_report_fulltext_intake: bool = False,
        report_llm_enabled: bool = True,
    ):
        """Configure the single-stock report facade."""
        self.stocks_data = stocks_data or {}

        self.stock_codes = stock_codes or {}
        self.raw_data = raw_data or {}
        self.agent_reach_configs = agent_reach_configs or {}
        self.source_intake_configs = source_intake_configs or {}
        self.stock_configs = stock_configs or {}
        self.enable_agent_reach = enable_agent_reach
        self.enable_periodic_report_fulltext_intake = enable_periodic_report_fulltext_intake
        self.report_llm_enabled = bool(report_llm_enabled)
        self.date_str = datetime.now().strftime("%Y%m%d")

    def generate_stock_report(self, stock_name: str, output_dir: str) -> tuple:
        """
        生成单只股票的深度报告（Pipeline 入口，接口不变）。
        """
        all_posts = self.stocks_data.get(stock_name, [])
        stock_cfg = self.stock_configs.get(stock_name, {})
        plan = compile_report_run_plan(
            repo_root=Path(__file__).resolve().parents[2],
            agent_reach_config=self.agent_reach_configs.get(stock_name, {}),
            source_intake_config=self.source_intake_configs.get(stock_name, {}),
            global_agent_reach_enabled=self.enable_agent_reach,
            global_periodic_fulltext_enabled=self.enable_periodic_report_fulltext_intake,
            environment=os.environ,
        )
        if not all_posts and not plan.can_run_without_posts:
            logger.warning(f"[{stock_name}] 无数据，跳过")
            return "", ""

        try:
            from .report_skills import build_stock_report_pipeline

            pipeline = build_stock_report_pipeline(**plan.pipeline_kwargs)

            pipeline_input = {
                "stock_name": stock_name,
                "date_str": self.date_str,
                "output_dir": output_dir,
                "stocks_data": self.stocks_data,
                "raw_data": self.raw_data,
                "stock_codes": self.stock_codes,
                "stock_config": stock_cfg,
                "report_llm_enabled": self.report_llm_enabled,
            }
            pipeline_input.update(plan.context_values)

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
