"""Report assembly skill."""

import logging
from pathlib import Path

if __name__.startswith("utils."):
    from ..skill_pipeline import BaseSkill, SkillContext
    from ..reporter.constants import COMPETITOR_MAP, INDUSTRY_MAP
else:
    from skill_pipeline import BaseSkill, SkillContext
    from reporter.constants import COMPETITOR_MAP, INDUSTRY_MAP

logger = logging.getLogger(__name__)

HEADER_TEMPLATE = """# {stock_name} 舆情深度报告

**报告日期**: {date_display}
**所属赛道**: {industry}
**可比公司**: {competitors}
**数据来源**: 雪球网热门讨论

---"""

FOOTER_TEMPLATE = """---

*本报告基于雪球网公开讨论数据由 Claude AI 深度分析生成，仅供参考，不构成投资建议。*
*报告生成时间: {date_display}*
"""


class ReportAssemblySkill(BaseSkill):
    """Markdown + HTML Dashboard 组装。直接调用 SectionRenderers 生成报告。"""
    name = "report_assembly"

    RENDERERS = [
        ("executive_summary", "utils.reporter.sections.executive_summary_renderer", "ExecutiveSummaryRenderer"),
        ("composite_score", "utils.reporter.sections.composite_score_renderer", "CompositeScoreRenderer"),
        ("valuation", "utils.reporter.sections.valuation_renderer", "ValuationRenderer"),
        ("technical", "utils.reporter.sections.technical_renderer", "TechnicalRenderer"),
        ("price_target", "utils.reporter.sections.price_target_renderer", "PriceTargetRenderer"),
        ("deep_analysis", "utils.reporter.sections.deep_analysis_renderer", "DeepAnalysisRenderer"),
        ("risk", "utils.reporter.sections.risk_renderer", "RiskRenderer"),
    ]

    def run(self, ctx: SkillContext) -> SkillContext:
        """组装 Markdown + HTML Dashboard。"""
        stock_name = ctx.get("stock_name")
        output_dir = ctx.get("output_dir")
        date_str = ctx.get("date_str")

        md_content = self._assemble_markdown(ctx)
        html_content = self._assemble_html(ctx)

        md_path = Path(output_dir) / f"{stock_name}_{date_str}.md"
        html_path = Path(output_dir) / f"{stock_name}_{date_str}.html"

        md_path.write_text(md_content, encoding="utf-8")
        html_path.write_text(html_content, encoding="utf-8")

        ctx.set("md_path", str(md_path))
        ctx.set("html_path", str(html_path))
        return ctx

    def _header(self, ctx: SkillContext) -> str:
        stock_name = ctx.get("stock_name", "")
        date_str = ctx.get("date_str", "")
        date_display = f"{date_str[:4]}年{date_str[4:6]}月{date_str[6:]}日" if len(date_str) == 8 else date_str
        industry = INDUSTRY_MAP.get(stock_name, "—")
        competitors = "、".join(COMPETITOR_MAP.get(stock_name, [])) or "—"
        return HEADER_TEMPLATE.format(
            stock_name=stock_name,
            date_display=date_display,
            industry=industry,
            competitors=competitors,
        )

    def _footer(self, ctx: SkillContext) -> str:
        date_str = ctx.get("date_str", "")
        date_display = f"{date_str[:4]}年{date_str[4:6]}月{date_str[6:]}日" if len(date_str) == 8 else date_str
        return FOOTER_TEMPLATE.format(date_display=date_display)

    def _render_section(self, name: str, module_path: str, class_name: str, ctx: SkillContext) -> str:
        try:
            module = __import__(module_path, fromlist=[class_name])
            renderer_cls = getattr(module, class_name)
        except Exception as e:
            logger.error(f"[{name}] 无法导入渲染器 {module_path}.{class_name}: {e}")
            return f"<!-- {name}: renderer import failed ({e}) -->"

        required = []
        try:
            required = renderer_cls.required_keys()
        except Exception:
            pass

        missing = [k for k in required if ctx.get(k) is None]
        if missing:
            logger.warning(f"[{name}] 跳过渲染，缺少键: {missing}")
            return f"<!-- {name}: skipped (missing keys: {', '.join(missing)}) -->"

        try:
            renderer = renderer_cls()
            return renderer.render(ctx)
        except Exception as e:
            logger.error(f"[{name}] 渲染失败: {e}")
            return f"<!-- {name}: rendering failed ({e}) -->"

    def _assemble_markdown(self, ctx: SkillContext) -> str:
        sections = [self._header(ctx)]

        for name, module_path, class_name in self.RENDERERS:
            sections.append(self._render_section(name, module_path, class_name, ctx))

        sections.append("> **精品帖子深度解读与关键评论摘录已迁移至知识库。**")
        sections.append(self._footer(ctx))

        return "\n\n".join(s for s in sections if s)

    def _assemble_html(self, ctx: SkillContext) -> str:
        try:
            from utils.reporter.sections.html_dashboard_renderer import HTMLDashboardRenderer
        except ImportError:
            try:
                import sys
                from pathlib import Path
                utils_dir = Path(__file__).parent.parent
                if str(utils_dir) not in sys.path:
                    sys.path.insert(0, str(utils_dir))
                from reporter.sections.html_dashboard_renderer import HTMLDashboardRenderer
            except Exception as e:
                logger.error(f"HTMLDashboardRenderer 导入失败: {e}")
                return f"<!-- HTML Dashboard rendering failed: {e} -->"

        required = HTMLDashboardRenderer.required_keys()
        missing = [k for k in required if ctx.get(k) is None]
        if missing:
            logger.warning(f"[html_dashboard] 跳过渲染，缺少键: {missing}")
            return f"<!-- html_dashboard: skipped (missing keys: {', '.join(missing)}) -->"

        try:
            renderer = HTMLDashboardRenderer()
            return renderer.render(ctx)
        except Exception as e:
            logger.error(f"[html_dashboard] 渲染失败: {e}")
            return f"<!-- html_dashboard: rendering failed ({e}) -->"
