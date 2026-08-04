"""Static call-graph guard for the clean v4 external-material cutover."""

from __future__ import annotations

import ast
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[2] / "scripts"
LEGACY_MODULES = {
    "curated_external_argument_cards",
    "curated_external_display_projection",
    "curated_external_topic_narrative",
    "curated_external_to_synthesis_items",
}
LEGACY_LITERALS = (
    "curated_external_argument_v2",
    "curated_external_argument_v3",
    "curated_external_argument_pack.v2",
    "curated_external_argument_pack.v3",
    "curated_external_argument_pack.v3.1",
    "curated_external_argument_card.v2",
    "curated_external_argument_card.v3",
    "curated_external_unit_selection.v1",
)
OWNED_FUNCTIONS = {
    "resolve_external_scope": "utils/external_scope.py",
    "external_family_title": "utils/external_evidence.py",
    "validate_external_evidence_unit": "utils/external_evidence.py",
    "build_external_argument_pack_v4": "utils/external_pack.py",
    "read_external_argument_pack_v4": "utils/external_pack.py",
    "build_curated_external_argument_display": "utils/curated_external_display.py",
}


def _runtime_paths():
    for path in RUNTIME_ROOT.rglob("*.py"):
        if "archive" not in path.relative_to(RUNTIME_ROOT).parts:
            yield path


def _imports(tree: ast.AST) -> set[str]:
    imports = {
        node.module.rsplit(".", 1)[-1]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imports.update(
        alias.name.rsplit(".", 1)[-1]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    return imports


def test_runtime_has_no_retired_external_pipeline_references():
    offenders = {}
    for path in _runtime_paths():
        text = path.read_text(encoding="utf-8")
        legacy_imports = sorted(_imports(ast.parse(text)).intersection(LEGACY_MODULES))
        legacy_literals = [literal for literal in LEGACY_LITERALS if literal in text]
        if legacy_imports or legacy_literals:
            offenders[path.relative_to(RUNTIME_ROOT).as_posix()] = {
                "imports": legacy_imports,
                "literals": legacy_literals,
            }

    assert offenders == {}


def test_v4_runtime_has_one_owner_for_each_public_contract_and_display_writer():
    definitions = {name: [] for name in OWNED_FUNCTIONS}
    writers = []
    for path in _runtime_paths():
        relative = path.relative_to(RUNTIME_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in definitions:
                definitions[node.name].append(relative)
            if isinstance(node, ast.Dict):
                for key in node.keys:
                    if isinstance(key, ast.Constant) and key.value == "_curated_external_argument_cards":
                        writers.append(relative)

    assert definitions == {name: [path] for name, path in OWNED_FUNCTIONS.items()}
    assert writers == ["utils/curated_external_display.py"]
