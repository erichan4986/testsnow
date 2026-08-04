"""Report section renderers — each renders one report section from SkillContext."""

from typing import Any, Dict, Protocol


class SectionRenderer(Protocol):
    """协议：每个 section renderer 实现 render(ctx) -> str。"""

    def render(self, ctx: Dict[str, Any]) -> str:
        ...


from .agent_reach_evidence_renderer import AgentReachEvidenceRenderer
from .executive_summary_renderer import ExecutiveSummaryRenderer
from .composite_score_renderer import CompositeScoreRenderer
from .valuation_renderer import ValuationRenderer
from .deep_analysis_renderer import DeepAnalysisRenderer
from .curated_external_analysis_renderer import CuratedExternalAnalysisRenderer
from .risk_renderer import RiskRenderer
from .html_dashboard_renderer import HTMLDashboardRenderer
from .technical_renderer import TechnicalRenderer

__all__ = [
    "SectionRenderer",
    "AgentReachEvidenceRenderer",
    "ExecutiveSummaryRenderer",
    "CompositeScoreRenderer",
    "ValuationRenderer",
    "DeepAnalysisRenderer",
    "CuratedExternalAnalysisRenderer",
    "RiskRenderer",
    "HTMLDashboardRenderer",
    "TechnicalRenderer",
]
