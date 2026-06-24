#!/usr/bin/env bash
# Lightweight repository safety gates.
#
# This script is intentionally narrow. It catches obvious invariant violations
# that are cheap to detect textually and leaves semantic invariants to pytest.

set -u
set -o pipefail

ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
FAILED=0

red() { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }

fail_gate() {
  red "FAIL: $1"
  FAILED=1
}

echo "[gate a] periodic report / broker research material-layer isolation ..."
CORE_LEAK_FILES=(
  "$ROOT/scripts/utils/reporter/scoring_engine.py"
  "$ROOT/scripts/utils/reporter/sections/risk_renderer.py"
  "$ROOT/scripts/utils/report_skills/knowledge_skills.py"
  "$ROOT/scripts/utils/periodic_report_filing_fact_note_writer.py"
)
HELPER_LEAK_FILES=(
  "$ROOT/scripts/utils/periodic_report_narrative_evidence_cards.py"
  "$ROOT/scripts/utils/periodic_report_narrative_card_note_writer.py"
  "$ROOT/scripts/utils/periodic_report_narrative_card_synthesis_items.py"
  "$ROOT/scripts/utils/broker_research_digest_synthesis_items.py"
)
LEAK_HITS=""
for file in "${CORE_LEAK_FILES[@]}"; do
  [ -f "$file" ] || continue
  hits=$(grep -nE 'periodic_report_fulltext|periodic_report_narrative_evidence|synthesis_display|broker_research' "$file" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    rel="${file#$ROOT/}"
    LEAK_HITS="${LEAK_HITS}${LEAK_HITS:+$'\n'}${rel}:$hits"
  fi
done
for file in "${HELPER_LEAK_FILES[@]}"; do
  [ -f "$file" ] || continue
  hits=$(grep -nE 'periodic_report_fulltext|synthesis_display([^_A-Za-z0-9]|$)' "$file" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    rel="${file#$ROOT/}"
    LEAK_HITS="${LEAK_HITS}${LEAK_HITS:+$'\n'}${rel}:$hits"
  fi
done
if [ -n "$LEAK_HITS" ]; then
  fail_gate "fulltext/display material leaked into scoring/risk/Knowledge files"
  printf '%s\n' "$LEAK_HITS"
else
  green "ok"
fi

echo "[gate b] source safety AST checks ..."
AST_OUTPUT=$(python3 - "$ROOT" <<'PY'
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
source_roots = [root / "scripts"]
exclude_parts = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "env",
}

secret_name_re = re.compile(r"(api[_-]?key|token|password|secret|authorization|cookie)", re.I)
secret_value_re = re.compile(
    r"^(sk-[A-Za-z0-9_\-]{8,}|xq_[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9._\-]{12,}|[A-Za-z0-9_\-]{24,})$",
    re.I,
)


def iter_py_files() -> list[Path]:
    files: list[Path] = []
    for base in source_roots:
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            rel_parts = set(path.relative_to(root).parts)
            if rel_parts & exclude_parts:
                continue
            files.append(path)
    return files


def rel(path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def is_requests_get(node: ast.Call) -> bool:
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "get"
        and isinstance(func.value, ast.Name)
        and func.value.id == "requests"
    )


def is_yaml_load(node: ast.Call) -> bool:
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "load"
        and isinstance(func.value, ast.Name)
        and func.value.id == "yaml"
    )


def assigned_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return assigned_name(node.value)
    return ""


def string_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


errors: list[str] = []

for path in iter_py_files():
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        errors.append(f"{rel(path)}: parse failed: {exc}")
        continue

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if is_requests_get(node):
                if not any(keyword.arg == "timeout" for keyword in node.keywords):
                    errors.append(f"{rel(path)}:{node.lineno}: requests.get call missing timeout")
            elif is_yaml_load(node):
                errors.append(f"{rel(path)}:{node.lineno}: unsafe yaml.load call; use yaml.safe_load")
            continue

        if isinstance(node, ast.Assign):
            targets = [assigned_name(target) for target in node.targets]
            value = string_value(node.value)
        elif isinstance(node, ast.AnnAssign):
            targets = [assigned_name(node.target)]
            value = string_value(node.value) if node.value is not None else None
        else:
            continue

        if not value:
            continue
        if not any(secret_name_re.search(target or "") for target in targets):
            continue
        if secret_value_re.search(value.strip()):
            names = ", ".join(target for target in targets if target) or "<unknown>"
            errors.append(f"{rel(path)}:{node.lineno}: obvious secret literal assigned to {names}")

for error in errors:
    print(error)

sys.exit(1 if errors else 0)
PY
)
AST_STATUS=$?
if [ "$AST_STATUS" -ne 0 ]; then
  fail_gate "AST source safety checks failed"
  printf '%s\n' "$AST_OUTPUT"
else
  green "ok"
fi

if [ "$FAILED" -ne 0 ]; then
  echo
  red "ci_grep_gates: one or more gates failed"
  exit 1
fi

echo
green "ci_grep_gates: all gates passed"
