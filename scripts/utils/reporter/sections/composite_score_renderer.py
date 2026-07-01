"""综合评分板块渲染器。"""

from typing import Any, Dict, List, Optional


class CompositeScoreRenderer:
    """综合评分与推荐板块 — G = B + M 综合评分 + EV Expectation + 目标价区间 + AI 推荐。"""

    @staticmethod
    def required_keys() -> List[str]:
        return ["stock_name"]

    def render(self, ctx: Dict[str, Any]) -> str:
        stock_name = ctx.get("stock_name", "")
        if not stock_name:
            return ""

        posts = ctx.get("posts", [])
        stock_raw = ctx.get("stock_raw", {})
        quote = ctx.get("quote")
        consensus = ctx.get("consensus")
        ind_fwd_pe = ctx.get("industry_fwd_pe")
        pillar = ctx.get("pillar")

        try:
            from ..scoring_engine import composite_score_section
        except ImportError:
            try:
                import sys
                from pathlib import Path
                utils_dir = Path(__file__).parent.parent.parent
                if str(utils_dir) not in sys.path:
                    sys.path.insert(0, str(utils_dir))
                from reporter.scoring_engine import composite_score_section
            except Exception:
                return ""

        recommendation_decision = ctx.get("recommendation_decision")

        md = composite_score_section(
            stock_name=stock_name,
            posts=posts,
            stock_raw=stock_raw,
            quote=quote,
            consensus=consensus,
            industry_fwd_pe=ind_fwd_pe,
            pillar=pillar,
            recommendation_decision=recommendation_decision,
        )

        chart_paths = ctx.get("chart_paths", ctx.get("_chart_paths", {}))
        radar_chart = chart_paths.get("radar")
        if radar_chart:
            md += (
                "\n\n### 五维评分雷达图\n\n"
                f'<p align="center"><img src="{radar_chart}" alt="{stock_name} 五维评分雷达图" '
                'style="max-width: 360px; width: 70%; height: auto;" /></p>\n'
            )

        return md
