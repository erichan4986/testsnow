# Periodic Report Metric Series Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Assemble auditable annual/semiannual metric histories from existing evidence-bound filing facts and expose them as a non-display, non-scoring pipeline context pack.

**Architecture:** `periodic_report_structured_facts.py` remains the sole filing-fact and cash-conversion formula owner. A new pure `periodic_report_metric_series.py` validates and groups those rows, while the existing intake skill only discovers local cache history and orchestrates existing builders. No renderer, scoring, Knowledge, or LLM path consumes the pack in this batch.

**Tech Stack:** Python 3, `Decimal`, pytest, existing periodic-report evidence/metric/fact builders.

---

## File Structure

- `scripts/utils/periodic_report_structured_facts.py`: add source document and complete period metadata to existing facts; fix malformed-display exception handling.
- `scripts/utils/periodic_report_metric_series.py`: sole owner of series validation, deduplication, conflict handling, changes, and derived-series assembly.
- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`: cache history discovery and pipeline context publication only.
- `tests/utils/test_periodic_report_structured_facts.py`: fact-owner metadata and malformed-display regression.
- `tests/utils/test_periodic_report_metric_series.py`: pure series contract and failure modes.
- `tests/utils/test_periodic_report_fulltext_intake.py`: multi-cache orchestration, latest-cache regression, and context isolation.

### Task 1: Complete Existing Structured-Fact Provenance

**Files:**
- Modify: `tests/utils/test_periodic_report_structured_facts.py`
- Modify: `scripts/utils/periodic_report_structured_facts.py`

- [ ] **Step 1: Write failing provenance and malformed-display tests**

Add a test that calls `build_periodic_report_structured_fact_pack(..., source_doc="测试股_2025_annual_jina.txt")` and asserts the pack, every filing fact, and every derived fact retain `source_doc`. Assert the ratio derived row also contains `stock_code`, `report_year`, `report_type`, `period`, and `formula_version == "cash_conversion.v1"`.

Add a focused test importing `_display_financial_amount` and asserting an invalid value such as `"not-a-number万元"` is returned unchanged rather than raising.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
PYTHONPATH=.:scripts/utils PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_periodic_report_structured_facts.py \
  -q -p no:cacheprovider
```

Expected: failures for the missing `source_doc` parameter/fields and missing
`InvalidOperation` import.

- [ ] **Step 3: Implement the minimal fact-owner changes**

Import `InvalidOperation`. Add optional `source_doc: str = ""` to the public
builder and internal `_filing_fact`/`_build_derived_facts` calls. Include
`source_doc` only when non-empty. Add this fixed metadata to the existing ratio
row:

```python
"stock_code": stock_code,
"report_year": int(report_year),
"report_type": report_type,
"period": str(report_year),
"formula_version": "cash_conversion.v1",
```

Do not change fact ids, formulas, thresholds, core-fact display, or risk signals.

- [ ] **Step 4: Run tests and verify GREEN**

Run the Task 1 command. Expected: all structured-fact tests pass.

### Task 2: Build The Pure Filing Metric Series

**Files:**
- Create: `tests/utils/test_periodic_report_metric_series.py`
- Create: `scripts/utils/periodic_report_metric_series.py`

- [ ] **Step 1: Write the first RED tests for valid histories**

Create compact fact-pack factories with full `source_doc`, hashes, and evidence
ids. Add tests asserting:

1. 2024 and 2025 annual revenue become one oldest-first series;
2. the change is `100.00万元` and `10.00%` for 1000 -> 1100;
3. annual and semiannual facts become separate series ids;
4. top-level flags are `report_eligible=False` and `scoring_eligible=False`;
5. no output contains `source_excerpt`.

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
PYTHONPATH=.:scripts/utils PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_periodic_report_metric_series.py \
  -q -p no:cacheprovider
```

Expected: import failure because the series module does not exist.

- [ ] **Step 3: Implement schema, admission, grouping, and valid changes**

Implement:

```python
METRIC_SERIES_SCHEMA_VERSION = "periodic_report_metric_series_pack.v1"
GROWTH_FORMULA_VERSION = "periodic_growth.v1"

def build_periodic_report_metric_series_pack(
    *, stock_code: str, stock_name: str, fact_packs: list[dict]
) -> dict:
    ...
```

Use `Decimal`; accept only the three existing filing metrics and exact
`万元`/`CNY` dimensions; require pack/fact schema, matching entity, period,
source document, evidence refs, and both hashes. Keep helper responsibilities
separate:

- `_validated_filing_rows(...)`
- `_build_filing_series(...)`
- `_build_changes(...)`
- `_source_evidence(...)`
- `_diagnostic(...)`

Sort series by id and points by report year. Quantize output to two decimals.

- [ ] **Step 4: Run tests and verify GREEN**

Run the Task 2 test command. Expected: initial valid-history tests pass.

- [ ] **Step 5: Add RED tests for duplicate, conflict, base, and gap behavior**

Add independent tests asserting:

- identical same-year facts from zh/en documents collapse and produce two
  distinct `source_evidence` records;
- different same-year values omit the period and emit
  `conflicting_period_values`;
- zero and negative prior values retain absolute change but omit growth and
  emit `non_positive_growth_base`;
- 2022 -> 2025 emits no change and diagnoses
  `non_consecutive_period_gap`;
- mismatched stock, missing hashes, wrong unit/currency, malformed amount, and
  unsupported source type are rejected with deterministic codes.

- [ ] **Step 6: Run those tests and verify RED**

Run the Task 2 command. Expected: new edge-case assertions fail because the
minimal valid-history implementation does not yet cover all rejection paths.

- [ ] **Step 7: Implement fail-closed behavior and provenance merging**

Group accepted rows by series dimensions and year. Deduplicate equal Decimals,
merge sorted evidence tuples, and remove a year when more than one numeric value
exists. Emit only compact diagnostics. Ensure counts reflect accepted/rejected
facts and conflicts without counting copied source-pack diagnostics as rejected
facts.

- [ ] **Step 8: Run tests and verify GREEN**

Run the Task 2 command. Expected: all filing-series tests pass.

### Task 3: Assemble Existing Derived Facts

**Files:**
- Modify: `tests/utils/test_periodic_report_metric_series.py`
- Modify: `scripts/utils/periodic_report_metric_series.py`

- [ ] **Step 1: Write RED derived-series tests**

Add tests asserting:

- an existing `operating_cash_flow_to_net_profit` row becomes one derived point;
- `-20.00%` remains negative;
- `formula_version`, period, and input refs are preserved;
- point provenance is the union of the accepted net-profit and OCF filing
  points;
- a missing/conflicted input point rejects the derived row;
- conflicting same-period derived values fail closed;
- input-pack diagnostics are copied only as `code`, `metric_key`, `source_doc`,
  `report_year`, and `report_type`.

- [ ] **Step 2: Run tests and verify RED**

Run the Task 2 command. Expected: derived-series assertions fail.

- [ ] **Step 3: Implement derived validation and assembly**

Read only `fact_pack["derived_facts"]`; require the existing metric key,
`periodic_report_derived_fact`, fixed formula version, valid signed percentage,
same-period metadata, and exact input refs. Look up the two accepted filing
points; never recalculate the ratio. Merge their source evidence and apply the
same duplicate/conflict rules.

- [ ] **Step 4: Run tests and verify GREEN**

Run the Task 2 command. Expected: all pure series tests pass.

### Task 4: Add Local Cache History Orchestration

**Files:**
- Modify: `tests/utils/test_periodic_report_fulltext_intake.py`
- Modify: `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`

- [ ] **Step 1: Write RED cache-history tests**

Add fixtures for `测试股_2024_annual_jina.txt` and
`测试股_2025_annual_jina.txt`. Assert:

- `_find_periodic_report_cache_files()` returns both paths once, oldest year
  first after deterministic sorting;
- overlapping patterns do not duplicate a path;
- `build_periodic_report_metric_series_from_cache()` returns two revenue
  points and one growth row;
- the existing latest-core-facts helper still reads the newest-mtime cache;
- no matching cache returns a complete empty pack, not `{}`;
- the skill publishes `periodic_report_metric_series_pack` without adding any
  renderer/external-evidence keys.

- [ ] **Step 2: Run intake tests and verify RED**

Run:

```bash
PYTHONPATH=.:scripts/utils PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_periodic_report_fulltext_intake.py \
  -q -p no:cacheprovider
```

Expected: missing helper/context key failures.

- [ ] **Step 3: Implement cache history and context publication**

Refactor cache pattern construction into one helper. Add
`_find_periodic_report_cache_files()` that deduplicates by resolved path while
retaining original `Path` objects and sorts deterministically by year then path.
Keep `_find_latest_periodic_report_cache_file()` selecting max by
`(st_mtime_ns, path.as_posix())`.

Implement `build_periodic_report_metric_series_from_cache()` by calling the
existing evidence, required metrics, and structured-fact builders per file.
Read failures, empty files, and missing years become compact diagnostics. Call
the pure series builder even with zero packs. In the skill, set the result under
`periodic_report_metric_series_pack`; do not add a consumer.

- [ ] **Step 4: Run intake and series tests and verify GREEN**

Run:

```bash
PYTHONPATH=.:scripts/utils PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_periodic_report_fulltext_intake.py \
  tests/utils/test_periodic_report_structured_facts.py \
  tests/utils/test_periodic_report_metric_series.py \
  -q -p no:cacheprovider
```

Expected: all focused tests pass.

### Task 5: Acceptance, Self-Review, And Repair

**Files:**
- Create: `docs/agent_workflow/2026-07-24-periodic-report-metric-series-codex-notes.md`
- Modify only the six files above if acceptance finds a scoped defect.

- [ ] **Step 1: Run downstream contract tests**

Run structured-fact writer, synthesis, renderer, report-quality, and source-
boundary suites. Any failure caused by this batch must be fixed with a new RED
test before changing runtime code.

- [ ] **Step 2: Run full offline verification**

```bash
PYTHONPATH=.:scripts/utils PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  -q -p no:cacheprovider
bash tools/ci_grep_gates.sh
git diff --check
```

- [ ] **Step 3: Run local-cache smoke checks**

Build one series pack for 中际旭创 and 黑芝麻智能 from local caches without
writing any data/report/Knowledge files. Record source pack count, series count,
points, diagnostics, and elapsed time.

- [ ] **Step 4: Perform two implementation self-reviews**

Round 1 checks correctness, ownership, raw-text leakage, conflict behavior,
scope, and duplicate code. Fix each accepted issue test-first. Round 2 repeats
the audit after fixes and must have no blocker or must-fix.

- [ ] **Step 5: Write acceptance notes and commit**

Record RED/GREEN evidence, focused/downstream/full test counts, CI/diff results,
smoke output, runtime numstat, self-review fixes, warnings, and deviations. Only
after fresh verification, commit with:

```text
feat: add periodic report metric series
```

