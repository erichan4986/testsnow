"""Technical analysis and chart generation skills."""

import sys
from pathlib import Path

if __name__.startswith("utils."):
    from ..skill_pipeline import BaseSkill, SkillContext
else:
    from skill_pipeline import BaseSkill, SkillContext

# Module-level imports so tests can patch them via unittest.mock
try:
    from reporter.chart_generator import (
        generate_bull_bear_chart,
        generate_radar_chart,
        generate_technical_panel,
        generate_valuation_comparison,
    )
    from reporter.scoring_engine import compute_pillar_scores
except ImportError:
    utils_dir = Path(__file__).parent.parent
    if str(utils_dir) not in sys.path:
        sys.path.insert(0, str(utils_dir))
    from reporter.chart_generator import (
        generate_bull_bear_chart,
        generate_radar_chart,
        generate_technical_panel,
        generate_valuation_comparison,
    )
    from reporter.scoring_engine import compute_pillar_scores


class TechnicalAnalysisSkill(BaseSkill):
    """Generate technical analysis panel chart from stock_raw data."""

    name = "technical_analysis"

    def run(self, ctx: SkillContext) -> SkillContext:
        stock_name = ctx.get("stock_name")
        stock_raw = ctx.get("stock_raw", {})
        output_dir = ctx.get("output_dir")

        if not output_dir:
            output_dir = str(Path(__file__).parent.parent.parent.parent / "reports" / "charts")

        tech = stock_raw.get("technical", {})
        daily_data = tech.get("daily_data", {})
        indicators = tech.get("indicators", {})
        patterns = indicators.get("_patterns", [])

        if daily_data and indicators:
            output_path = Path(output_dir) / f"{stock_name}_technical.png"
            chart_path = generate_technical_panel(
                stock_name=stock_name,
                daily_data=daily_data,
                patterns=patterns,
                indicators=indicators,
                output_path=str(output_path),
            )
            chart_paths = ctx.get("chart_paths", {})
            chart_paths["technical"] = chart_path
            ctx.set("chart_paths", chart_paths)
            ctx.set("chart_technical", chart_path)
        else:
            chart_paths = ctx.get("chart_paths", {})
            chart_paths["technical"] = None
            ctx.set("chart_paths", chart_paths)
            ctx.set("chart_technical", None)

        return ctx


class ChartGenerationSkill(BaseSkill):
    """Generate bull-bear, radar, and valuation comparison charts."""

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
        pillar = compute_pillar_scores(stock_raw, keep_posts, quote, consensus, ind_fwd_pe, ps)
        total_score = round(
            pillar["valuation"] * 0.30 +
            pillar["technical"] * 0.25 +
            pillar["sentiment"] * 0.20 +
            pillar["fundamental"] * 0.15 +
            pillar["fundflow"] * 0.10,
            1,
        )

        # Radar chart
        radar_path = Path(output_dir) / f"{stock_name}_radar.png"
        radar_chart_path = generate_radar_chart(
            stock_name=stock_name,
            pillar_scores=pillar,
            total_score=total_score,
            output_path=str(radar_path),
        )
        chart_paths = ctx.get("chart_paths", {})
        chart_paths["radar"] = radar_chart_path
        ctx.set("pillar_scores", pillar)
        ctx.set("total_score", total_score)
        ctx.set("chart_radar", radar_chart_path)

        # Bull-bear chart
        bullish_args = ctx.get("bullish_args", [])
        bearish_args = ctx.get("bearish_args", [])
        bb_path = Path(output_dir) / f"{stock_name}_bullbear.png"
        bb_chart_path = generate_bull_bear_chart(
            stock_name=stock_name,
            bullish_args=bullish_args,
            bearish_args=bearish_args,
            output_path=str(bb_path),
        )
        chart_paths["bullbear"] = bb_chart_path
        ctx.set("chart_bullbear", bb_chart_path)

        # Valuation comparison chart
        competitor_metrics = ctx.get("competitor_metrics")
        if competitor_metrics:
            val_path = Path(output_dir) / f"{stock_name}_valuation.png"
            val_chart_path = generate_valuation_comparison(
                stock_name=stock_name,
                competitor_metrics=competitor_metrics,
                output_path=str(val_path),
            )
            chart_paths["valuation"] = val_chart_path
            ctx.set("chart_valuation", val_chart_path)
        else:
            chart_paths["valuation"] = None
            ctx.set("chart_valuation", None)

        ctx.set("chart_paths", chart_paths)
        return ctx
