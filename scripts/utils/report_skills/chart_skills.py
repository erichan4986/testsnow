"""Technical analysis and chart generation skills."""

import logging
from pathlib import Path

if __name__.startswith("utils."):
    from ..skill_pipeline import BaseSkill, SkillContext
    from ..reporter.chart_generator import (
        generate_bull_bear_chart,
        generate_radar_chart,
        generate_technical_panel,
    )
    from ..reporter.scoring_engine import compute_pillar_scores
else:
    from skill_pipeline import BaseSkill, SkillContext
    from reporter.chart_generator import (
        generate_bull_bear_chart,
        generate_radar_chart,
        generate_technical_panel,
    )
    from reporter.scoring_engine import compute_pillar_scores


logger = logging.getLogger(__name__)


class TechnicalAnalysisSkill(BaseSkill):
    """Generate technical analysis panel chart from stock_raw data."""

    name = "technical_analysis"

    def run(self, ctx: SkillContext) -> SkillContext:
        stock_name = ctx.get("stock_name")
        stock_raw = ctx.get("stock_raw", {})
        output_dir = ctx.get("output_dir")

        if not output_dir:
            output_dir = str(Path(__file__).parent.parent.parent.parent / "reports" / "charts")

        tech = ctx.get("technical") or stock_raw.get("technical", {})
        daily_data = ctx.get("daily_data") or tech.get("daily_data", {})
        indicators = tech.get("indicators", {})
        patterns = indicators.get("_patterns", [])

        if daily_data and indicators:
            chart_paths = ctx.get("chart_paths", {})
            try:
                output_path = Path(output_dir) / f"{stock_name}_technical.png"
                chart_path = generate_technical_panel(
                    stock_name=stock_name,
                    daily_data=daily_data,
                    patterns=patterns,
                    indicators=indicators,
                    output_path=str(output_path),
                )
                chart_paths["technical"] = chart_path
                ctx.set("chart_technical", chart_path)
            except Exception as e:
                logger.warning(f"[{stock_name}] 技术面图生成失败，跳过: {e}")
                chart_paths["technical"] = None
                ctx.set("chart_technical", None)
            ctx.set("chart_paths", chart_paths)
        else:
            chart_paths = ctx.get("chart_paths", {})
            chart_paths["technical"] = None
            ctx.set("chart_paths", chart_paths)
            ctx.set("chart_technical", None)

        return ctx


class ChartGenerationSkill(BaseSkill):
    """Generate report charts used in Markdown/PDF output."""

    name = "chart_generation"

    def run(self, ctx: SkillContext) -> SkillContext:
        stock_name = ctx.get("stock_name")
        stock_raw = ctx.get("stock_raw", {})
        keep_posts = ctx.get("keep_posts", [])
        quote = ctx.get("quote")
        consensus = ctx.get("consensus")
        ind_fwd_pe = ctx.get("ind_fwd_pe")
        ps = ctx.get("ps")
        output_dir = ctx.get("output_dir")

        if not output_dir:
            output_dir = str(Path(__file__).parent.parent.parent.parent / "reports" / "charts")

        # Compute pillar scores for radar chart
        pillar = ctx.get("pillar_scores") or compute_pillar_scores(
            stock_raw, keep_posts, quote, consensus, ind_fwd_pe, ps
        )
        total_score = ctx.get("total_score")
        if pillar is not None and total_score is None:
            total_score = round(
                pillar["valuation"] * 0.30 +
                pillar["technical"] * 0.25 +
                pillar["sentiment"] * 0.20 +
                pillar["fundamental"] * 0.15 +
                pillar["fundflow"] * 0.10,
                1,
            )

        # Radar chart
        chart_paths = ctx.get("chart_paths", {})
        if pillar is not None and total_score is not None:
            radar_path = Path(output_dir) / f"{stock_name}_radar.png"
            radar_chart_path = generate_radar_chart(
                stock_name=stock_name,
                pillar_scores=pillar,
                total_score=total_score,
                output_path=str(radar_path),
            )
            chart_paths["radar"] = radar_chart_path
            ctx.set("chart_radar", radar_chart_path)
        else:
            chart_paths["radar"] = None
            ctx.set("chart_radar", None)
        ctx.set("pillar_scores", pillar)
        ctx.set("total_score", total_score)

        # Bull-bear chart
        bullish_args = ctx.get("bullish_args", [])
        bearish_args = ctx.get("bearish_args", [])
        bb_chart_path = None
        if bullish_args or bearish_args:
            try:
                bb_chart_path = generate_bull_bear_chart(
                    stock_name, bullish_args, bearish_args,
                    str(Path(output_dir) / f"{stock_name}_bullbear.png"),
                )
            except Exception as e:
                logger.warning(f"[{stock_name}] 多空图生成失败，跳过: {e}")
        chart_paths["bullbear"] = bb_chart_path
        ctx.set("chart_bullbear", bb_chart_path)

        # 同业估值保留表格，不再生成单独的估值折线/对比图片。
        chart_paths["valuation"] = None
        ctx.set("chart_valuation", None)

        ctx.set("chart_paths", chart_paths)
        return ctx
