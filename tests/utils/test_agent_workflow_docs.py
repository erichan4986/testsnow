from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTEXT_INDEX = REPO_ROOT / "docs" / "agent_workflow" / "context_index.md"


def test_agent_workflow_context_index_exists() -> None:
    assert CONTEXT_INDEX.exists()


def test_agent_workflow_context_index_path_markers_exist() -> None:
    content = CONTEXT_INDEX.read_text(encoding="utf-8")
    paths = re.findall(r"<!--\s*path-check:\s*([^>]+?)\s*-->", content)

    assert paths, "context_index.md should mark important local paths with path-check comments"
    missing = [path for path in paths if not (REPO_ROOT / path).exists()]
    assert missing == []


def test_agent_workflow_runbooks_exist() -> None:
    runbooks = [
        "docs/agent_workflow/runbooks/run_local_report_validation.md",
        "docs/agent_workflow/runbooks/add_periodic_report_metric.md",
        "docs/agent_workflow/runbooks/review_generated_report_quality.md",
    ]

    missing = [path for path in runbooks if not (REPO_ROOT / path).exists()]
    assert missing == []
