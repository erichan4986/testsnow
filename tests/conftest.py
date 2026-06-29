from __future__ import annotations

from pathlib import Path
from typing import Iterable, Set

import pytest


REPORT_CORE_FILES = {
    "test_assembly_skills.py",
    "test_deep_analysis_renderer.py",
    "test_report_quality.py",
    "test_risk_renderer.py",
    "test_scoring_engine_contract.py",
    "test_scoring_engine_risk.py",
    "test_stock_reporter_source_intake_config.py",
    "test_synthesis_skills.py",
    "test_curated_external_full_body_viewpoint_preview.py",
    "test_curated_external_viewpoint_narrative_preview.py",
}

EXTERNAL_MATERIAL_PREFIXES = (
    "test_agent_reach_",
    "test_broker_research_",
    "test_cached_community_",
    "test_claim_intake_",
    "test_claim_verification_",
    "test_curated_external_",
    "test_deploy_wechat_",
    "test_fresh_social_",
    "test_fulltext_material_",
    "test_iwencai_",
    "test_periodic_report_",
    "test_prepare_annual_",
    "test_source_intake_",
    "test_wechat_",
)

INTEGRATION_PREFIXES = (
    "test_run_",
    "test_pipeline_",
    "test_stock_reporter_",
)

INTEGRATION_FILES = {
    "test_chart_generator.py",
    "test_chart_skills.py",
    "test_market_resonance_integration.py",
    "test_prepare_annual_report_materials.py",
}

SLOW_FILES = {
    "test_chart_generator.py",
    "test_pipeline_integration.py",
    "test_prepare_annual_report_materials.py",
}

LEGACY_PREFIXES = ()
LEGACY_FILES = set()


def markers_for_path(path: str | Path) -> Set[str]:
    """Return automatic pytest markers for a test file path."""
    name = Path(str(path).replace("\\", "/")).name
    markers: Set[str] = set()

    if name in REPORT_CORE_FILES:
        markers.add("report_core")
    if name.startswith(EXTERNAL_MATERIAL_PREFIXES):
        markers.add("external_material")
    if name.startswith(INTEGRATION_PREFIXES) or name in INTEGRATION_FILES:
        markers.add("integration")
    if name in SLOW_FILES:
        markers.add("slow")
    if name.startswith(LEGACY_PREFIXES) or name in LEGACY_FILES:
        markers.add("legacy")

    return markers


def pytest_collection_modifyitems(config: pytest.Config, items: Iterable[pytest.Item]) -> None:
    for item in items:
        for marker in markers_for_path(str(item.fspath)):
            item.add_marker(getattr(pytest.mark, marker))
