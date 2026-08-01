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
