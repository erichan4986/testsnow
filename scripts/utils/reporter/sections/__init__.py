"""Report section renderers — each renders one report section from SkillContext."""

from typing import Any, Dict, Protocol


class SectionRenderer(Protocol):
    """协议：每个 section renderer 实现 render(ctx) -> str。"""

    def render(self, ctx: Dict[str, Any]) -> str:
        ...


def _chart_paths(ctx: Dict[str, Any]) -> Dict[str, str]:
    """从 context 或 reporter 中提取图表路径。"""
    return ctx.get("chart_paths", ctx.get("_chart_paths", {}))


from .agent_reach_evidence_renderer import AgentReachEvidenceRenderer
from .executive_summary_renderer import ExecutiveSummaryRenderer
from .composite_score_renderer import CompositeScoreRenderer
from .valuation_renderer import ValuationRenderer
from .deep_analysis_renderer import DeepAnalysisRenderer
from .risk_renderer import RiskRenderer
from .html_dashboard_renderer import HTMLDashboardRenderer
from .technical_renderer import TechnicalRenderer
from .price_target_renderer import PriceTargetRenderer

__all__ = [
    "SectionRenderer",
    "_chart_paths",
    "AgentReachEvidenceRenderer",
    "ExecutiveSummaryRenderer",
    "CompositeScoreRenderer",
    "ValuationRenderer",
    "DeepAnalysisRenderer",
    "RiskRenderer",
    "HTMLDashboardRenderer",
    "TechnicalRenderer",
    "PriceTargetRenderer",
]
