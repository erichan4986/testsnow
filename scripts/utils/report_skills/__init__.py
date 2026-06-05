"""Report generation skills package."""

if __name__.startswith("utils."):
    from ..skill_pipeline import SkillPipeline
else:
    from skill_pipeline import SkillPipeline

from .analysis_skills import cross_source_consolidation_skill, scoring_skill
from .chart_skills import ChartGenerationSkill, TechnicalAnalysisSkill
from .data_skills import (
    competitor_fetching_skill,
    data_loading_skill,
    quality_gate_skill,
    quote_fetching_skill,
)
from .assembly_skills import ReportAssemblySkill
from .synthesis_skills import SynthesisSkill

__all__ = [
    "cross_source_consolidation_skill",
    "data_loading_skill",
    "quality_gate_skill",
    "quote_fetching_skill",
    "competitor_fetching_skill",
    "scoring_skill",
    "TechnicalAnalysisSkill",
    "ChartGenerationSkill",
    "SynthesisSkill",
    "ReportAssemblySkill",
    "build_stock_report_pipeline",
]


def build_stock_report_pipeline(llm_client=None) -> SkillPipeline:
    """构建股票报告生成 Pipeline。"""
    return SkillPipeline([
        data_loading_skill,
        quality_gate_skill,
        cross_source_consolidation_skill,
        quote_fetching_skill,
        competitor_fetching_skill,
        TechnicalAnalysisSkill(),
        SynthesisSkill(llm_client=llm_client),
        scoring_skill,
        ChartGenerationSkill(),
        ReportAssemblySkill(),
    ])
