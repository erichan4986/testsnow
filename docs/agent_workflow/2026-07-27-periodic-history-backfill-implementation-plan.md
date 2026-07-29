# Periodic Report History Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to execute this plan task-by-task. This is a
> data-only operation; do not modify tracked runtime or test code.

**Goal:** Stage, validate and publish missing 2023-2024 official annual-report
caches for 中际旭创、复旦微电 and 黑芝麻智能, then prove that the existing annual
MetricSeries and FinancialScan paths consume the available history.

**Architecture:** Use a temporary `/tmp` orchestrator around the existing
CNINFO/HKEX discovery and cache APIs. Downloads land in a staging directory,
validation completes before publication, and only previously missing paths are
copied into the canonical cache. Existing 2025 files are hash-protected.

**Tech Stack:** Python standard library, existing periodic-report cache and
structured-fact modules, pytest, report quality scripts.

---

### Task 1: Capture immutable baseline

**Files:**
- Read: `data/raw/periodic_reports/*_2025_annual_jina.txt`
- Create: `/tmp/periodic-history-backfill-20260729/baseline.json`

- [ ] **Step 1: Verify the worktree is clean**

Run: `git status --short`

Expected: no output.

- [ ] **Step 2: Record the canonical inventory and SHA-256 values**

Create `baseline.json` with, for each target stock, the existing annual text
paths and SHA-256 values. Include the tracked HEAD and current timestamp.

- [ ] **Step 3: Assert the requested missing periods are absent**

Expected before download:

```text
中际旭创: 2023 missing, 2024 missing, 2025 present
复旦微电: 2023 missing, 2024 missing, 2025 present
黑芝麻智能: 2023 missing, 2024 missing, 2025 present
```

Stop if a requested canonical path already exists; do not overwrite it.

### Task 2: Build the temporary official-source orchestrator

**Files:**
- Create: `/tmp/periodic-history-backfill-20260729/backfill.py`
- Create: `/tmp/periodic-history-backfill-20260729/staging/`
- Create: `/tmp/periodic-history-backfill-20260729/discovery-manifest.json`

- [ ] **Step 1: Implement target discovery**

The temporary script must import the existing repository functions:

```python
from periodic_report_cache import (
    cache_periodic_report_from_url,
    discover_cninfo_annual_report,
    standard_cache_paths,
)
from hk_periodic_report_fetcher import discover_hkex_periodic_report
```

Use this exact target matrix:

```python
TARGETS = (
    ("中际旭创", "300308", "A", 2023),
    ("中际旭创", "300308", "A", 2024),
    ("复旦微电", "688385", "A", 2023),
    ("复旦微电", "688385", "A", 2024),
    ("黑芝麻智能", "02533", "HK", 2023),
    ("黑芝麻智能", "02533", "HK", 2024),
)
```

For A shares, call `discover_cninfo_annual_report`. For the HK share, call
`discover_hkex_periodic_report(..., report_type="annual", lang="ZH")`.
Persist title, date, URL, stock, year and status in the discovery manifest.

- [ ] **Step 2: Enforce source-domain and availability rules**

Accept only `cninfo.com.cn` subdomains for A shares and `hkexnews.hk`
subdomains for the HK share. A discovery error is a blocker for A shares. For
黑芝麻智能 2023 only, `ValueError: No HKEX annual report found` becomes
`official_report_not_available`; no substitute URL may be supplied.

- [ ] **Step 3: Download only into staging**

Call `cache_periodic_report_from_url` with `report_type="annual"` and the
staging cache directory. Do not point any download call at the canonical cache.

### Task 3: Validate every staged period

**Files:**
- Read: `/tmp/periodic-history-backfill-20260729/staging/`
- Update: `/tmp/periodic-history-backfill-20260729/discovery-manifest.json`

- [ ] **Step 1: Verify cache integrity**

For every downloaded period, require:

```python
assert text.strip()
assert hashlib.sha256(text.encode("utf-8")).hexdigest() == meta["text_hash_sha256"]
assert meta["stock_name"] == stock_name
assert str(meta["stock_code"]) == stock_code
assert int(meta["report_year"]) == year
assert meta["report_type"] == "annual"
```

Also require that `official_url` matches the discovered URL and approved
domain, and that the source PDF exists under staging `_downloads`.

- [ ] **Step 2: Build structured filing facts**

For each staged text, run the existing builders in order:

```python
evidence_pack = build_periodic_report_evidence_pack(text, report_type="annual")
metrics = build_required_financial_risk_metrics(evidence_pack, raw_text=text)
fact_pack = build_periodic_report_structured_fact_pack(
    stock_code=stock_code,
    stock_name=stock_name,
    report_year=year,
    report_type="annual",
    evidence_pack=evidence_pack,
    required_financial_metrics=metrics,
    source_doc=text_path.name,
)
```

Record available `revenue`, `net_profit`, and `operating_cash_flow` facts plus
all diagnostics. Never synthesize a missing metric.

- [ ] **Step 3: Stop on identity or extraction failure**

Do not publish any period when issuer/year/type, source domain, text hash, PDF,
or evidence-pack validation fails. Missing individual metrics may continue only
with explicit diagnostics.

### Task 4: Publish validated missing periods

**Files:**
- Create: `data/raw/periodic_reports/*_2023_annual_jina.txt`
- Create: `data/raw/periodic_reports/*_2023_annual_meta.json`
- Create: `data/raw/periodic_reports/*_2024_annual_jina.txt`
- Create: `data/raw/periodic_reports/*_2024_annual_meta.json`
- Create as available: `data/raw/periodic_reports/_downloads/*_source.pdf`

- [ ] **Step 1: Recheck destination absence**

Every destination must still be absent. Abort the affected period if a path
appeared after Task 1.

- [ ] **Step 2: Copy one validated period as a unit**

Copy text, metadata and source PDF to temporary sibling names first. Rename
them to final names only after all copies succeed. If a rename fails, remove
only files created for that period; never remove a pre-existing canonical file.

- [ ] **Step 3: Recheck 2025 hashes**

Compare all 2025 hashes with `baseline.json`. Any change is a hard failure.

### Task 5: Prove MetricSeries and FinancialScan consumption

**Files:**
- Read: `data/raw/periodic_reports/`
- Create: `/tmp/periodic-history-backfill-20260729/series-validation.json`

- [ ] **Step 1: Build annual packs from canonical cache**

Use `_load_periodic_report_cache_rows`, `_metric_series_from_cache_rows` and
`build_periodic_report_financial_scan_pack` from the existing intake path. Do
not add a second parser.

- [ ] **Step 2: Assert ordered periods**

For 中际旭创 and 复旦微电, every metric present in all three filings must have
points ordered `2023, 2024, 2025` and two deterministic changes. For
黑芝麻智能, assert all officially available periods are ordered and record the
explicit 2023 availability diagnostic when applicable.

- [ ] **Step 3: Verify derived facts use accepted inputs only**

Cash-conversion rows may exist only when both net-profit and operating-cash-flow
points passed source validation for the same stock/year/report type.

### Task 6: Run regression and report validation

**Files:**
- Natural outputs only: `reports/<stock>_<date>.md` and `.html`
- Create: `docs/agent_workflow/2026-07-29-periodic-history-backfill-acceptance.md`

- [ ] **Step 1: Run focused offline tests**

Run:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_periodic_report_cache.py \
  tests/reporter/test_prepare_annual_report_materials.py \
  tests/reporter/test_periodic_report_fulltext_intake_skill.py \
  tests/utils/test_periodic_report_metric_series.py \
  tests/utils/test_periodic_report_financial_scan.py \
  -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 2: Generate three no-PDF reports**

Run the existing `scripts/run_stock_report.py --stock <name> --no-pdf` entry for
each target. Do not enable Xueqiu or Chrome/CDP.

- [ ] **Step 3: Run report gates**

Run quality, source-boundary and prose checks for all three new Markdown files,
then `bash tools/ci_grep_gates.sh` and `git diff --check`. Technical-data network
warnings are recorded separately and do not waive annual source failures.

- [ ] **Step 4: Write acceptance evidence**

Record discoveries, unavailable periods, cache hashes, structured metrics,
series periods, FinancialScan diagnostics, report paths, quality gates,
warnings and deviations. Confirm no tracked runtime/test/config/prompt file was
modified.

- [ ] **Step 5: Commit only the acceptance document**

Stage and commit the acceptance document. Raw cache/report artifacts follow the
repository ignore policy and must not be forced into Git.
