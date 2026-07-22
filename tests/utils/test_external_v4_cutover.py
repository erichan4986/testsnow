"""Static call-graph guard for the clean v4 external-material cutover."""

from __future__ import annotations

import ast
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[2] / "scripts"
LEGACY_MODULES = {
    "curated_external_argument_cards",
    "curated_external_display_projection",
    "curated_external_topic_narrative",
}
LEGACY_SCHEMA_LITERALS = (
    "curated_external_argument_pack.v3",
    "curated_external_argument_card.v3",
    "curated_external_unit_selection.v1",
)


def test_runtime_has_no_v3_or_v31_external_pipeline_references():
    offenders = {}
    for path in RUNTIME_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        imports = {
            node.module.rsplit(".", 1)[-1]
            for node in ast.walk(ast.parse(text))
            if isinstance(node, ast.ImportFrom) and node.module
        }
        imports.update(alias.name.rsplit(".", 1)[-1] for node in ast.walk(ast.parse(text)) if isinstance(node, ast.Import) for alias in node.names)
        legacy = sorted(imports.intersection(LEGACY_MODULES))
        schemas = [literal for literal in LEGACY_SCHEMA_LITERALS if literal in text]
        if legacy or schemas:
            offenders[path.relative_to(RUNTIME_ROOT).as_posix()] = {"imports": legacy, "schemas": schemas}

    assert offenders == {}
