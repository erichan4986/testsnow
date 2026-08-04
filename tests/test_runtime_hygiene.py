from __future__ import annotations

import ast
import importlib
import inspect
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
