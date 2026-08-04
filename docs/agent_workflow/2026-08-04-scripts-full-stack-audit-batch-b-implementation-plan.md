# Scripts Full-Stack Audit Batch B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove four dead compatibility surfaces while preserving the active report pipeline and reducing runtime by at least 80 lines.

**Architecture:** Extend the existing AST-based runtime hygiene contract first, then delete only the locked definitions/export and one inert test monkeypatch. Active quote, fund-flow, scoring, and structured executive-summary owners remain unchanged.

**Tech Stack:** Python 3, pytest, AST-based hygiene tests, shell CI gates.

---

### Task 1: Lock the Hard-Cut Contract

**Files:**
- Modify: `tests/test_runtime_hygiene.py`

- [ ] **Step 1: Write the failing hygiene test**

Add a test that asserts the four definitions are absent, the reporter package
does not expose `valuation_industry_judgment`, and the active top-level owners
remain:

```python
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
```

- [ ] **Step 2: Verify RED**

Run:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_runtime_hygiene.py::test_batch_b_dead_compatibility_surfaces_are_absent -q -p no:cacheprovider
```

Expected: failure because B1-B4 definitions and the B3 export still exist.

### Task 2: Perform the Minimal Deletion

**Files:**
- Modify: `scripts/utils/reporter/data_fetcher.py`
- Modify: `scripts/utils/reporter/scoring_engine.py`
- Modify: `scripts/utils/reporter/__init__.py`
- Modify: `scripts/utils/reporter/sections/executive_summary_renderer.py`
- Modify: `tests/reporter/test_fulltext_material_isolation.py`

- [ ] **Step 1: Delete only the locked surfaces**

Remove the complete definitions of `stock_quote_eastmoney`, `fund_flow_daily`,
`valuation_industry_judgment`, and `_extract_conclusion`; remove the B3 package
import and B4's inert monkeypatch. Do not edit surrounding active functions.

- [ ] **Step 2: Verify GREEN**

Run the RED command again. Expected: PASS.

- [ ] **Step 3: Run focused behavior tests**

Run:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_runtime_hygiene.py tests/reporter/test_data_fetcher_manual_financials.py tests/reporter/test_data_fetcher_market_cap.py tests/reporter/test_data_fetcher_peers.py tests/reporter/test_scoring_engine_contract.py tests/reporter/test_scoring_engine_risk.py tests/reporter/test_executive_summary_renderer.py tests/reporter/test_executive_summary_view.py tests/reporter/test_fulltext_material_isolation.py tests/reporter/test_technical_skills_contract.py tests/test_data_collector.py tests/utils/test_data_source_fallback_hygiene.py -q -p no:cacheprovider
```

Expected: all pass.

- [ ] **Step 4: Check the deletion budget**

Use `git diff --numstat` on the four runtime files. Stop if runtime net deletion
is below 80 lines or any runtime addition appears.

### Task 3: Verify the Full Pipeline

- [ ] **Step 1: Run the full suite**

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```

Expected: no failures.

- [ ] **Step 2: Run static gates**

```text
bash tools/ci_grep_gates.sh
git diff --check
```

Expected: all gates pass and no whitespace errors.

- [ ] **Step 3: Run the offline report smoke**

```text
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_stock_report.py --stock 黑芝麻智能 --offline-smoke
```

Expected: exit 0; outputs only under `/tmp/testsnow_offline_smoke`; no LLM
request, retry, provider call, or browser activity.

- [ ] **Step 4: Review scope**

Confirm only the planned runtime/tests/docs are changed and all pre-existing
broker-note, old-report, and plan-packet changes are untouched.
