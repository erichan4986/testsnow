# Runtime And Test Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove provably dead runtime code and consolidate four duplicated stock entrypoints and their tests onto `run_stock_report.py` without changing report logic.

**Architecture:** `scripts/run_stock_report.py` becomes the only single-stock workflow owner. Named stock scripts remain as tiny argv-forwarding wrappers. Structural hygiene tests enforce unique owners, while existing behavioral tests continue to protect the generic pipeline.

**Tech Stack:** Python 3, pytest, importlib, pathlib, AST/source-structure assertions.

---

### Task 1: Lock Runtime Hygiene Contracts

**Files:**
- Create: `tests/test_runtime_hygiene.py`
- Delete later: `scripts/utils/reporter.py`

- [ ] **Step 1: Write failing unique-owner tests**

Create tests that assert `scripts/utils/reporter.py` does not exist, `utils.reporter` resolves to `reporter/__init__.py`, `ReportManager` imports from the package, and the nine known dead definitions are absent from their source ASTs.

- [ ] **Step 2: Run RED**

Run:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_runtime_hygiene.py -q -p no:cacheprovider
```

Expected: failure because the shadow module and dead definitions still exist.

- [ ] **Step 3: Remove dead owners**

Delete `scripts/utils/reporter.py`, the eight private helpers listed in the design, and the duplicate PDF log line. Do not modify `_extract_conclusion`.

- [ ] **Step 4: Run GREEN and affected tests**

Run the hygiene test plus broker digest, periodic extraction, source intake, report manager, and generic entry tests.

### Task 2: Fill Generic Entry Contract Gaps

**Files:**
- Modify: `scripts/run_stock_report.py`
- Modify: `tests/reporter/test_run_stock_report_entry.py`

- [ ] **Step 1: Add failing frontmatter test**

Add a knowledge post fixture with nested `interactions.likes/comments`; assert `_parse_markdown_post()` returns those values.

- [ ] **Step 2: Run RED**

Expected: generic parser returns defaults `10/5`.

- [ ] **Step 3: Implement narrow nested interaction parsing**

Port the existing bounded regex behavior from the old 圣邦/中简 entries. Do not add YAML dependencies.

- [ ] **Step 4: Add and verify fast-test network guard**

Add a test with no caches and no knowledge posts that asserts `fetch_all_stocks` is not called and the generic entry uses an empty post list. This should already pass and records the intended owner contract.

- [ ] **Step 5: Add configured-stock invariants**

Parameterize the stock configuration checks needed from the old entry tests: 黑芝麻 periodic narrative display, 圣邦 periodic fulltext/narrative display, and 中简 Agent-Reach/Source Intake presence.

### Task 3: Replace Named Entrypoints With Wrappers

**Files:**
- Modify: `scripts/run_中际旭创.py`
- Modify: `scripts/run_圣邦股份.py`
- Modify: `scripts/run_黑芝麻智能.py`
- Modify: `scripts/run_中简科技.py`
- Create: `tests/reporter/test_named_stock_entry_wrappers.py`

- [ ] **Step 1: Write failing wrapper tests**

Parameterize all four module paths and stock names. Patch each module's `_run_generic_report`, call `main(["--fast-test", "--no-pdf"])`, and assert exact argv `['--stock', stock_name, '--fast-test', '--no-pdf']` plus unchanged return code.

- [ ] **Step 2: Run RED**

Expected: current modules have no `_run_generic_report` forwarding owner.

- [ ] **Step 3: Implement minimal wrappers**

Each file keeps shebang/docstring, inserts its script directory in `sys.path`, imports `run_stock_report.main as _run_generic_report`, defines `STOCK_NAME`, forwards `main(argv=None)`, and uses `raise SystemExit(main(sys.argv[1:]))` under `__main__`.

- [ ] **Step 4: Run GREEN**

Run the wrapper tests and generic entry tests.

### Task 4: Delete Superseded Entrypoint Tests

**Files:**
- Delete: `tests/reporter/test_run_black_sesame_entry.py`
- Delete: `tests/reporter/test_run_shengbang_entry.py`
- Delete: `tests/reporter/test_run_zhongjian_entry.py`

- [ ] **Step 1: Map every old assertion**

Record each old contract as either generic entry behavior, stock config invariant, or wrapper forwarding. Do not delete until every row has a surviving test owner.

- [ ] **Step 2: Delete the three duplicate files**

- [ ] **Step 3: Run entry/config suites**

Run named wrapper, generic entry, Agent-Reach config, and Source Intake config tests.

### Task 5: Consolidate Exact Duplicate Tests

**Files:**
- Modify: `tests/utils/test_periodic_report_narrative_evidence_cards.py`
- Modify: `tests/utils/test_claim_risk_signals.py`
- Delete: `tests/reporter/test_skill_pipeline_observability.py`

- [ ] **Step 1: Record parameter case counts**

Capture the existing parameter lists for the three narrative admission functions and the two pairs of risk-negative functions.

- [ ] **Step 2: Merge identical bodies**

Combine parameter lists without removing or rewriting any case. Use one descriptive function per behavior.

- [ ] **Step 3: Delete permanent skip file**

Remove the six observability tests that are unconditionally skipped for an unimplemented feature.

- [ ] **Step 4: Verify focused collections and behavior**

Run both modified test modules and confirm all original parameter strings remain collected.

### Task 6: Final Verification And Accounting

**Files:**
- Create: `docs/agent_workflow/2026-07-31-runtime-test-dedup-implementation-notes.md`

- [ ] **Step 1: Run the full suite**

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```

- [ ] **Step 2: Run CI and whitespace gates**

```text
bash tools/ci_grep_gates.sh
git diff --check
```

- [ ] **Step 3: Run offline named-entry smoke**

```text
python3 scripts/run_黑芝麻智能.py --offline-smoke
```

Confirm outputs stay under `/tmp/testsnow_offline_smoke` and no network/browser path runs.

- [ ] **Step 4: Measure net line changes**

Compare `scripts/**/*.py` and `tests/**/*.py` line totals with the 68,592/63,754 baseline. Stop if runtime reduction is below 1,300 or tests reduction below 500 unless a documented correctness reason explains the difference.

- [ ] **Step 5: Write notes**

Record changed/deleted files, RED/GREEN evidence, test totals, skipped count, runtime/test numstat, smoke result, blockers, warnings, and deviations.
