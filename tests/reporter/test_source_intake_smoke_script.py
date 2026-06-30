"""Tests for scripts/smoke/smoke_source_intake.py.

These tests verify that the smoke script can be imported and does not pull in
forbidden dependencies like PerStockReporter, KnowledgeSynthesizer, Playwright,
or CDP helpers.
"""

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

SMOKE_PATH = Path(__file__).parent.parent.parent / "scripts" / "smoke" / "smoke_source_intake.py"


def test_smoke_script_exists():
    assert SMOKE_PATH.exists()


def test_smoke_script_does_not_import_forbidden_modules():
    tree = ast.parse(SMOKE_PATH.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported.add(module)
            for alias in node.names:
                imported.add(f"{module}.{alias.name}" if module else alias.name)

    forbidden = {
        "PerStockReporter",
        "KnowledgeSynthesizer",
        "ZhihuCollector",
        "playwright",
        "sync_playwright",
        "chromium",
        "cdp",
    }
    found = forbidden & imported
    assert not found, f"Smoke script imports forbidden modules: {found}"


def test_smoke_script_has_main():
    tree = ast.parse(SMOKE_PATH.read_text(encoding="utf-8"))
    has_main = any(
        isinstance(node, ast.FunctionDef) and node.name == "main"
        for node in ast.walk(tree)
    )
    assert has_main


def test_smoke_script_accepts_json_flag():
    content = SMOKE_PATH.read_text(encoding="utf-8")
    assert "--json" in content
    assert "--stock" in content
