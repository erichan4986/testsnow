"""Report generation skills package."""

if __name__.startswith("utils."):
    from ..skill_pipeline import SkillPipeline
else:
    from skill_pipeline import SkillPipeline

from .agent_reach_query_skill import agent_reach_query_skill
from .agent_reach_skill import agent_reach_fetch_skill
from .agent_reach_quality_skill import agent_reach_quality_skill
from .evidence_note_skill import evidence_note_writer_skill
from .analysis_skills import cross_source_consolidation_skill, scoring_skill
from .chart_skills import ChartGenerationSkill, TechnicalAnalysisSkill
from .data_skills import (
    competitor_fetching_skill,
    data_loading_skill,
    quality_gate_skill,
    quote_fetching_skill,
)
from .technical_skills import technical_fetching_skill
from .assembly_skills import ReportAssemblySkill
from .synthesis_skills import SynthesisSkill

__all__ = [
    "agent_reach_query_skill",
    "agent_reach_fetch_skill",
    "agent_reach_quality_skill",
    "evidence_note_writer_skill",
    "cross_source_consolidation_skill",
    "data_loading_skill",
    "quality_gate_skill",
    "quote_fetching_skill",
    "competitor_fetching_skill",
    "scoring_skill",
    "technical_fetching_skill",
    "TechnicalAnalysisSkill",
    "ChartGenerationSkill",
    "SynthesisSkill",
    "ReportAssemblySkill",
    "build_stock_report_pipeline",
]


def build_stock_report_pipeline(llm_client=None, enable_agent_reach: bool = False, enable_evidence_notes: bool = False) -> SkillPipeline:
    """构建股票报告生成 Pipeline。"""
    skills = [
        data_loading_skill,
        quality_gate_skill,
    ]

    if enable_agent_reach:
        skills.extend([
            agent_reach_query_skill,
            agent_reach_fetch_skill,
            agent_reach_quality_skill,
        ])
        if enable_evidence_notes:
            skills.append(evidence_note_writer_skill)

    skills.extend([
        cross_source_consolidation_skill,
        quote_fetching_skill,
        competitor_fetching_skill,
        technical_fetching_skill,
        TechnicalAnalysisSkill(),
        SynthesisSkill(llm_client=llm_client),
        scoring_skill,
        ChartGenerationSkill(),
        ReportAssemblySkill(),
    ])

    return SkillPipeline(skills)
