# Scripts Full-Stack Audit Batch A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development to implement this plan task-by-task.

**Goal:** Delete about 200 lines of provably obsolete report runtime code without changing any active report behavior.

**Architecture:** Preserve every active owner and remove only unregistered renderers, superseded wrappers, and
zero-reference definitions proven by the locked design. A single AST/import hygiene contract prevents accidental
reintroduction and protects the active owners; existing focused and full suites protect behavior.

**Tech Stack:** Python 3, pytest, AST inspection, existing stock-report skill pipeline.

---

### Task 1: Add the RED runtime hygiene contract

**Files:**
- Modify: `tests/test_runtime_hygiene.py`

- [ ] **Step 1: Add the obsolete-surface and active-owner tests**

Add these tests using the existing `_top_level_definitions()` helper:

```python
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
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_runtime_hygiene.py -q -p no:cacheprovider
```

Expected: the new obsolete-surface test fails because the file and definitions still exist; existing tests pass.

### Task 2: Delete only the locked obsolete surfaces

**Files:**
- Delete: `scripts/utils/reporter/sections/price_target_renderer.py`
- Modify: `scripts/utils/reporter/sections/__init__.py`
- Modify: `scripts/utils/reporter/data_fetcher.py`
- Modify: `scripts/utils/periodic_report_narrative_pack_store.py`
- Modify: `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
- Modify: `scripts/utils/external_source_document.py`
- Modify: `scripts/utils/periodic_report_required_metrics.py`
- Modify: `README.md`

- [ ] **Step 1: Apply the exact deletion ledger**

Delete A1-A5 from the locked design. Keep `Iterable`, `deepcopy`,
`normalized_source_excerpt_hash`, all three rows helpers, single-document builder,
`TechnicalRenderer`, `price_target.py`, and all active source/data functions.

- [ ] **Step 2: Run hygiene GREEN**

Run the Task 1 command. Expected: all runtime hygiene tests pass.

- [ ] **Step 3: Run focused behavior tests**

Run:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_runtime_hygiene.py tests/reporter/test_assembly_skills.py tests/utils/test_periodic_report_fulltext_intake.py tests/reporter/test_periodic_report_fulltext_intake_skill.py tests/utils/test_periodic_report_narrative_pack_store.py tests/utils/test_external_source_document.py tests/utils/test_technical_ohlcv_cache.py tests/reporter/test_technical_resonance.py -q -p no:cacheprovider
```

Expected: all pass.

### Task 3: Verify the complete repository contract

**Files:**
- Create: `docs/agent_workflow/2026-08-04-scripts-full-stack-audit-batch-a-implementation-notes.md`

- [ ] **Step 1: Run full tests**

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```

Expected: zero failures; baseline is 2,851 passed / 10 skipped before the two new tests.

- [ ] **Step 2: Run repository gates**

```text
bash tools/ci_grep_gates.sh
git diff --check
```

Expected: all gates pass and no whitespace errors.

- [ ] **Step 3: Run offline main-entry smoke**

```text
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_stock_report.py --stock 黑芝麻智能 --offline-smoke
```

Expected: exit 0; outputs only under `/tmp/testsnow_offline_smoke`; no network or formal report output.

- [ ] **Step 4: Audit deletion budget and scope**

Run `git diff --numstat f6f3714 -- scripts` and sum additions/removals. Expected: runtime net
reduction of at least 185 lines and no runtime additions outside the hygiene test. Verify `git status`
contains only the allowed runtime/test/README/workflow files.

- [ ] **Step 5: Write implementation notes**

Record modified/deleted files, RED/GREEN evidence, focused/full/CI/smoke results, runtime numstat,
active-owner audit, blocker/warning/deviation, and whether Batch A is accepted. Do not commit or push.

