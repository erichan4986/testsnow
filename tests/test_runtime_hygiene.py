from __future__ import annotations

import ast
import importlib
import inspect
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _top_level_definitions(relative_path: str) -> set[str]:
    tree = ast.parse((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def test_report_manager_has_one_runtime_owner() -> None:
    assert not (SCRIPTS_DIR / "utils" / "reporter.py").exists()

    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        reporter = importlib.import_module("utils.reporter")
    finally:
        sys.path.remove(str(SCRIPTS_DIR))

    assert Path(reporter.__file__).resolve() == SCRIPTS_DIR / "utils" / "reporter" / "__init__.py"
    assert Path(inspect.getsourcefile(reporter.ReportManager)).resolve() == (
        SCRIPTS_DIR / "utils" / "reporter" / "report_manager.py"
    )


def test_known_dead_private_helpers_are_absent() -> None:
    expected_absent = {
        "scripts/utils/broker_research_digest.py": {
            "_generic_driver_block_excerpt",
            "_looks_like_financial_snapshot_without_driver",
        },
        "scripts/utils/a_stock_source_intake.py": {
            "_contains_reference_value",
            "_report_row_matches_target",
        },
        "scripts/utils/periodic_report_evidence_pack.py": {"_extract_section_excerpt"},
        "scripts/utils/periodic_report_required_financial_metrics.py": {
            "_hk_current_thousand_metric",
            "_last_rate_cell",
        },
        "scripts/utils/periodic_report_required_metrics.py": {"_block_for_usage"},
        "scripts/utils/reporter/sections/__init__.py": {"_chart_paths"},
    }

    for path, names in expected_absent.items():
        assert _top_level_definitions(path).isdisjoint(names), path


def test_pdf_success_is_logged_once() -> None:
    source = (SCRIPTS_DIR / "run_stock_report.py").read_text(encoding="utf-8")
    assert source.count('logger.info("PDF已生成: %s", pdf_path)') == 1


def test_batch_a_obsolete_runtime_surfaces_are_absent() -> None:
    assert not (
        SCRIPTS_DIR / "utils" / "reporter" / "sections" / "price_target_renderer.py"
    ).exists()

    expected_absent = {
        "scripts/utils/reporter/data_fetcher.py": {"fetch_index_bars"},
        "scripts/utils/periodic_report_narrative_pack_store.py": {
            "v2_note_card_fingerprint",
        },
        "scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py": {
            "build_periodic_report_filing_core_facts_from_cache",
            "build_periodic_report_explanation_pack_from_cache",
            "build_periodic_report_narrative_cards_from_cache",
        },
        "scripts/utils/external_source_document.py": {
            "build_external_source_documents",
        },
        "scripts/utils/periodic_report_required_metrics.py": {
            "RequiredMetricsError",
        },
    }
    for path, names in expected_absent.items():
        assert _top_level_definitions(path).isdisjoint(names), path


def test_batch_a_active_owners_remain() -> None:
    assert "TechnicalRenderer" in _top_level_definitions(
        "scripts/utils/reporter/sections/technical_renderer.py"
    )
    assert "normalized_source_excerpt_hash" in _top_level_definitions(
        "scripts/utils/periodic_report_narrative_pack_store.py"
    )
    assert "build_external_source_document" in _top_level_definitions(
        "scripts/utils/external_source_document.py"
    )
    assert {
        "_filing_core_facts_from_cache_rows",
        "_explanation_pack_from_cache_rows",
        "_narrative_cards_from_cache_rows",
    } <= _top_level_definitions(
        "scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py"
    )


def test_batch_d_bootstrap_entry_surface_is_absent() -> None:
    path = "scripts/run_stock_report.py"
    source = (REPO_ROOT / path).read_text(encoding="utf-8")
    assert _top_level_definitions(path).isdisjoint(
        {
            "_write_stocks_config",
            "_default_bootstrap_output",
            "_build_default_a_stock_source_intake",
            "_build_bootstrap_stock",
            "_handle_bootstrap",
        }
    )
    for option in (
        "--bootstrap-config",
        "--write-config",
        "--bootstrap-output",
        "--code",
        "--xueqiu-code",
        "--gid",
    ):
        assert option not in source


def test_batch_e_detached_knowledge_skill_is_absent() -> None:
    module_path = SCRIPTS_DIR / "utils" / "report_skills" / "knowledge_skills.py"
    package_source = (module_path.parent / "__init__.py").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    ci_gate = (REPO_ROOT / "tools" / "ci_grep_gates.sh").read_text(encoding="utf-8")
    context_index = (REPO_ROOT / "docs" / "agent_workflow" / "context_index.md").read_text(encoding="utf-8")

    assert not module_path.exists()
    assert "KnowledgePersistenceSkill" not in package_source
    assert "knowledge_skills.py" not in readme
    assert "test_knowledge_skills.py" not in readme
    assert "report_skills/knowledge_skills.py" not in ci_gate
    assert "report_skills/knowledge_skills.py" not in context_index


def test_batch_f1_detached_external_preview_utilities_are_absent() -> None:
    detached_pairs = (
        (
            SCRIPTS_DIR / "utils" / "social_viewpoint_source_packets.py",
            REPO_ROOT / "tests" / "utils" / "test_social_viewpoint_source_packets.py",
        ),
        (
            SCRIPTS_DIR / "utils" / "curated_external_video_subtitles.py",
            REPO_ROOT / "tests" / "utils" / "test_curated_external_video_subtitles.py",
        ),
        (
            SCRIPTS_DIR / "utils" / "curated_external_candidate_discovery.py",
            REPO_ROOT / "tests" / "utils" / "test_curated_external_candidate_discovery.py",
        ),
    )

    for runtime_path, test_path in detached_pairs:
        assert not runtime_path.exists()
        assert not test_path.exists()


def test_batch_f2_public_compatibility_hard_cut() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    reporter_init = SCRIPTS_DIR / "utils" / "reporter" / "__init__.py"
    sections_init = reporter_init.parent / "sections" / "__init__.py"

    for module_name in ("judgment_generator.py", "wechat_sogou_fetcher.py"):
        assert not (SCRIPTS_DIR / "utils" / module_name).exists()
        assert module_name not in readme

    reporter_source = reporter_init.read_text(encoding="utf-8")
    sections_source = sections_init.read_text(encoding="utf-8")
    assert "from .report_manager import ReportManager" in reporter_source
    assert "from .constants import" not in reporter_source
    assert "from .data_fetcher import" not in reporter_source
    assert "from .scoring_engine import" not in reporter_source
    assert "SectionRenderer" not in sections_source
    assert "Renderer" not in sections_source
    for test_path in (REPO_ROOT / "tests").rglob("*.py"):
        if test_path.resolve() == Path(__file__).resolve():
            continue
        source = test_path.read_text(encoding="utf-8")
        assert "from scripts.utils.reporter.sections import" not in source
        assert "from reporter.sections import" not in source

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; sys.path.insert(0, 'scripts'); "
                "import utils.reporter as reporter; "
                "from utils.reporter import ReportManager, data_fetcher; "
                "import utils.reporter.sections as sections; "
                "from utils.reporter.sections.technical_renderer import TechnicalRenderer; "
                "assert ReportManager.__module__ == 'utils.reporter.report_manager'; "
                "assert data_fetcher.__name__ == 'utils.reporter.data_fetcher'; "
                "assert not hasattr(reporter, 'compute_pillar_scores'); "
                "assert not hasattr(sections, 'TechnicalRenderer')"
            ),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_batch_b_dead_compatibility_surfaces_are_absent() -> None:
    expected_absent = {
        "scripts/utils/reporter/data_fetcher.py": {
            "stock_quote_eastmoney",
            "fund_flow_daily",
        },
        "scripts/utils/reporter/scoring_engine.py": {
            "valuation_industry_judgment",
        },
        "scripts/utils/reporter/sections/executive_summary_renderer.py": {
            "_extract_conclusion",
        },
    }
    for path, names in expected_absent.items():
        assert _top_level_definitions(path).isdisjoint(names), path

    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        reporter = importlib.import_module("utils.reporter")
    finally:
        sys.path.remove(str(SCRIPTS_DIR))
    assert not hasattr(reporter, "valuation_industry_judgment")

    assert "fetch_tencent_quote" in _top_level_definitions(
        "scripts/utils/reporter/data_fetcher.py"
    )
    assert "compute_pillar_scores" in _top_level_definitions(
        "scripts/utils/reporter/scoring_engine.py"
    )
    assert "_deterministic_conclusion" in _top_level_definitions(
        "scripts/utils/reporter/sections/executive_summary_renderer.py"
    )
    assert "_baidu_fund_flow_history" in _top_level_definitions(
        "scripts/utils/data_collector.py"
    )
    assert "_bridge_technical_fund_flow" in _top_level_definitions(
        "scripts/utils/report_skills/technical_skills.py"
    )


def test_batch_g1_duplicate_chapter4_annual_projection_is_absent() -> None:
    source = (
        SCRIPTS_DIR / "utils" / "reporter" / "sections" / "deep_analysis_renderer.py"
    ).read_text(encoding="utf-8")
    for name in (
        "_annual_report_business_profile_section",
        "_annual_rows_by_group",
        "_annual_row_text_key",
        "_annual_row_visible_body",
        "_select_annual_portrait_row",
        "_is_suspicious_zero_annual_row",
        "_material_snapshot",
        "_truncate_title",
    ):
        assert f"def {name}(" not in source


def test_batch_g2_formal_thin_broker_raw_memo_bypass_is_absent() -> None:
    source = (
        SCRIPTS_DIR / "utils" / "reporter" / "sections" / "deep_analysis_renderer.py"
    ).read_text(encoding="utf-8")
    for token in (
        "def _broker_research_memo_section(",
        "def _broker_row_author(",
        "def _max_snapshot_ref(",
        "broker_citation_offset",
        'ctx.get("broker_research_memo")',
    ):
        assert token not in source


def test_batch_h1_chapter4_memo_intermediate_schemas_are_absent() -> None:
    sources = "\n".join(
        (SCRIPTS_DIR / path).read_text(encoding="utf-8")
        for path in (
            "utils/deep_analysis_material_snapshot.py",
            "utils/report_skills/synthesis_skills.py",
        )
    )
    for token in (
        "annual_report_memo.v1",
        "broker_research_memo.v1",
        "def _build_annual_report_memo(",
        "def _build_broker_research_memo(",
        'ctx.get("annual_report_memo")',
        'ctx.get("broker_research_memo")',
    ):
        assert token not in sources
