"""Report generation skills package."""

if __name__.startswith("utils."):
    from ..skill_pipeline import SkillPipeline
else:
    from skill_pipeline import SkillPipeline

from .agent_reach_query_skill import agent_reach_query_skill
from .agent_reach_skill import agent_reach_fetch_skill
from .agent_reach_quality_skill import agent_reach_quality_skill
from .a_stock_source_intake_skill import a_stock_source_intake_skill
from .source_intake_merge_skill import source_intake_merge_skill
from .evidence_note_skill import evidence_note_writer_skill
from .claim_risk_signal_skill import claim_risk_signal_skill
from .periodic_report_fulltext_intake_skill import periodic_report_fulltext_intake_skill
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
    "a_stock_source_intake_skill",
    "source_intake_merge_skill",
    "evidence_note_writer_skill",
    "claim_risk_signal_skill",
    "periodic_report_fulltext_intake_skill",
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


def build_stock_report_pipeline(
    llm_client=None,
    enable_agent_reach: bool = False,
    enable_evidence_notes: bool = False,
    enable_claim_risk_signals: bool = False,
    enable_source_intake: bool = False,
    enable_periodic_report_fulltext_intake: bool = False,
    include_curated_external_evidence_cards_in_synthesis_display: bool = False,
    curated_external_evidence_cards_json: str = "",
    curated_external_evidence_cards_max_display_items: int = 8,
    curated_external_evidence_cards_min_cards: int = 3,
    curated_external_evidence_cards_min_total_excerpt_chars: int = 1200,
    include_curated_external_viewpoint_narrative_in_deep_analysis_display: bool = False,
    curated_external_viewpoint_narrative_json: str = "",
    include_curated_external_viewpoint_digest_in_deep_analysis_display: bool = False,
    curated_external_viewpoint_digest_json: str = "",
) -> SkillPipeline:
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

    if enable_source_intake:
        skills.append(a_stock_source_intake_skill)

    if enable_agent_reach or enable_source_intake:
        skills.append(source_intake_merge_skill)

    if enable_periodic_report_fulltext_intake:
        skills.append(periodic_report_fulltext_intake_skill)

    if enable_evidence_notes and (enable_agent_reach or enable_source_intake):
        skills.append(evidence_note_writer_skill)

    skills.extend([
        cross_source_consolidation_skill,
        quote_fetching_skill,
        competitor_fetching_skill,
        technical_fetching_skill,
        TechnicalAnalysisSkill(),
        SynthesisSkill(
            llm_client=llm_client,
            include_curated_external_evidence_cards_in_synthesis_display=include_curated_external_evidence_cards_in_synthesis_display,
            curated_external_evidence_cards_json=curated_external_evidence_cards_json,
            curated_external_evidence_cards_max_display_items=curated_external_evidence_cards_max_display_items,
            curated_external_evidence_cards_min_cards=curated_external_evidence_cards_min_cards,
            curated_external_evidence_cards_min_total_excerpt_chars=curated_external_evidence_cards_min_total_excerpt_chars,
            include_curated_external_viewpoint_narrative_in_deep_analysis_display=include_curated_external_viewpoint_narrative_in_deep_analysis_display,
            curated_external_viewpoint_narrative_json=curated_external_viewpoint_narrative_json,
            include_curated_external_viewpoint_digest_in_deep_analysis_display=include_curated_external_viewpoint_digest_in_deep_analysis_display,
            curated_external_viewpoint_digest_json=curated_external_viewpoint_digest_json,
        ),
    ])

    if enable_claim_risk_signals:
        skills.append(claim_risk_signal_skill)

    skills.extend([
        scoring_skill,
        ChartGenerationSkill(),
        ReportAssemblySkill(),
    ])

    return SkillPipeline(skills)
