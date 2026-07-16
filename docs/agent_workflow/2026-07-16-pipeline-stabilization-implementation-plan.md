# Pipeline Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the default offline test suite and make three annual-material
CLIs deterministic under an inherited relative `PYTHONPATH` without changing
report business behavior.

**Architecture:** Add one `scripts/_path_bootstrap.py` helper that canonicalizes
only the target path, removes equivalent aliases, and prepends it while preserving
all unrelated `sys.path` entries. Adopt it in the three scoped scripts; correct
four stale tests without changing their runtime owners.

**Tech Stack:** Python 3.10, `pathlib`, `pytest`, subprocess CLI tests.

---

### Task 1: Add the canonical path bootstrap

**Files:**

- Create: `scripts/_path_bootstrap.py`
- Create: `tests/utils/test_path_bootstrap.py`

- [ ] **Step 1: Write failing helper tests**

Create `tests/utils/test_path_bootstrap.py` with an autouse fixture that restores
`sys.path`, then add tests equivalent to:

```python
import sys

import pytest

from scripts._path_bootstrap import prepend_sys_path


@pytest.fixture(autouse=True)
def restore_sys_path():
    original = list(sys.path)
    yield
    sys.path[:] = original


def test_prepend_sys_path_collapses_relative_and_absolute_aliases(monkeypatch, tmp_path):
    target = tmp_path / "utils"
    target.mkdir()
    monkeypatch.chdir(tmp_path)
    sys.path[:] = ["", "before", str(target), "utils", "after"]

    canonical = prepend_sys_path(target)

    assert canonical == str(target.resolve())
    assert sys.path == [canonical, "", "before", "after"]


def test_prepend_sys_path_is_idempotent_and_preserves_unrelated_order(tmp_path):
    target = tmp_path / "utils"
    target.mkdir()
    sys.path[:] = ["", "alpha", str(target), "omega"]

    prepend_sys_path(target)
    prepend_sys_path(target)

    assert sys.path == [str(target.resolve()), "", "alpha", "omega"]
```

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_path_bootstrap.py -q -p no:cacheprovider
```

Expected: collection fails because `_path_bootstrap` does not exist.

- [ ] **Step 3: Implement the minimal helper**

Create `scripts/_path_bootstrap.py`:

```python
"""Shared import-path bootstrap for direct command-line scripts."""

from __future__ import annotations

import sys
from pathlib import Path


def prepend_sys_path(path: str | Path) -> str:
    """Put one canonical path first while preserving unrelated entries."""
    canonical = str(Path(path).resolve())
    target = Path(canonical)
    retained = [
        entry
        for entry in sys.path
        if Path(entry or ".").resolve() != target
    ]
    sys.path[:] = [canonical, *retained]
    return canonical
```

- [ ] **Step 4: Verify GREEN**

Run the command from Step 2. Expected: all helper tests pass.

### Task 2: Migrate the three annual-material CLIs

**Files:**

- Modify: `scripts/periodic_report_cache.py`
- Modify: `scripts/periodic_report_extractor.py`
- Modify: `scripts/prepare_annual_report_materials.py`
- Modify: `tests/utils/test_periodic_report_cache.py`
- Modify: `tests/utils/test_periodic_report_extractor.py`
- Modify: `tests/reporter/test_prepare_annual_report_materials.py`

- [ ] **Step 1: Write inherited-path regression tests**

In each test file import `os`, build the child environment without dropping
ambient variables, and set a relative inherited path:

```python
env = os.environ.copy()
env["PYTHONPATH"] = os.pathsep.join(("scripts/utils", "scripts"))
```

Pass `env=env` and `cwd=REPO_ROOT` to the existing cache and extractor subprocess
runs. Both extractor JSON and Markdown runs receive the environment.

Add this no-network prepare regression:

```python
def test_cli_help_survives_inherited_pythonpath() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(("scripts/utils", "scripts"))
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "prepare_annual_report_materials.py"), "--help"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Prepare annual report cache" in result.stdout
```

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_periodic_report_cache.py \
  tests/utils/test_periodic_report_extractor.py \
  tests/reporter/test_prepare_annual_report_materials.py \
  -q -p no:cacheprovider --tb=short
```

Expected: cache and extractor subprocess tests fail through wrapper/self-import
resolution. The prepare `--help` regression may already pass because its current
manual ordering is correct; it is a characterization test protecting migration.

- [ ] **Step 3: Replace local path snippets**

In each scoped script import:

```python
from _path_bootstrap import prepend_sys_path
```

Then replace the local membership/remove logic with:

```python
prepend_sys_path(UTILS_DIR)
```

For `prepare_annual_report_materials.py`, preserve current precedence:

```python
prepend_sys_path(UTILS_DIR)
prepend_sys_path(PREVIEWS_DIR)
```

- [ ] **Step 4: Verify GREEN in both environments**

Run the Step 2 command, then run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts/utils:scripts \
python3 -m pytest \
  tests/utils/test_periodic_report_cache.py \
  tests/utils/test_periodic_report_extractor.py \
  tests/reporter/test_prepare_annual_report_materials.py \
  -q -p no:cacheprovider --tb=short
```

Expected: both commands pass.

### Task 3: Correct stale test contracts

**Files:**

- Modify: `tests/utils/test_a_stock_source_intake.py`
- Modify: `tests/reporter/test_claim_risk_signal_skill.py`

- [ ] **Step 1: Record the existing RED failures**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_a_stock_source_intake.py::test_eastmoney_stock_news_adapter_marks_professional_observation \
  tests/utils/test_a_stock_source_intake.py::test_eastmoney_global_news_attaches_industry_chain_metadata_for_4_3 \
  tests/utils/test_a_stock_source_intake.py::test_medium_credit_items_are_not_confirmed_fact \
  tests/reporter/test_claim_risk_signal_skill.py::test_output_structured_risk_signals_passes_to_risk_section \
  -q -p no:cacheprovider --tb=short
```

Expected: four failures matching the verified date, section-policy, and package-
import causes.

- [ ] **Step 2: Apply test-only contract corrections**

Pass `today=date(2026, 6, 24)` to both affected stock-news adapter calls.

Change the industry-chain assertion to:

```python
assert items[0].extra["allowed_sections"] == ["4.1"]
```

Rename that test suffix from `_for_4_3` to `_for_4_1` so its name matches the
current contract.

In the claim-risk test, remove the function-local `sys.path.insert` and use:

```python
from reporter.scoring_engine import risk_score_section
```

Do not edit any runtime source-intake, relevance, scoring, or risk file.

- [ ] **Step 3: Verify GREEN**

Re-run the Step 1 command with the renamed industry-chain test target
`test_eastmoney_global_news_attaches_industry_chain_metadata_for_4_1`. Expected:
four passed.

- [ ] **Step 4: Run the complete focused suites**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_a_stock_source_intake.py \
  tests/utils/test_industry_news_relevance.py \
  tests/reporter/test_claim_risk_signal_skill.py \
  -q -p no:cacheprovider --tb=short
```

Expected: all tests pass with no new skips.

### Task 4: Verify scope, budget, and pipeline behavior

**Files:**

- Create: `docs/agent_workflow/2026-07-16-pipeline-stabilization-notes.md`

- [ ] **Step 1: Run the full offline suite**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider --tb=short
```

Expected: zero failures; existing explicit environment skips may remain.

- [ ] **Step 2: Run static gates**

```bash
bash tools/ci_grep_gates.sh
git diff --check
```

Expected: all gates pass and no whitespace errors.

- [ ] **Step 3: Measure runtime growth**

Run:

```bash
git diff --numstat 611c28a -- \
  scripts/_path_bootstrap.py \
  scripts/periodic_report_cache.py \
  scripts/periodic_report_extractor.py \
  scripts/prepare_annual_report_materials.py
```

Calculate net additions from the four rows. Stop if net growth exceeds `+60`;
target is at most `+30`.

- [ ] **Step 4: Run the sample report smoke test**

```bash
cd scripts
python run_黑芝麻智能.py --fast-test
```

Expected: exit zero and a Markdown report under `reports/`. Do not refresh Zhihu,
run batch collection, or access Xueqiu detail pages.

- [ ] **Step 5: Write implementation notes**

Record modified files, exact RED/GREEN results, full-suite counts, CI output,
runtime numstat, smoke-test output path, deviations, warnings, and blockers in
`docs/agent_workflow/2026-07-16-pipeline-stabilization-notes.md`.

- [ ] **Step 6: Commit the verified implementation**

Stage only the allowed runtime, test, plan, and notes files. Do not stage generated
reports or unrelated files. Commit with:

```bash
git commit -m "fix: stabilize annual material cli imports"
```
