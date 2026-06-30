# Periodic Report Experimental Path Status

Date: 2026-06-17

## Positioning

The annual/semiannual standalone path is currently a bounded evidence-material layer, not a final report pipeline.

It is intended to convert long periodic reports into structured, evidence-bound material for later synthesis:

- fulltext evidence chunks (`fulltext-*` ids)
- deterministic required business metrics
- deterministic required financial risk metrics
- product/project/customer backfill notes
- optional LLM fixed-section judgments

The output remains `professional_analysis` with `source_credit=75`. It must not be treated as official confirmed facts by itself.

## Current Boundaries

This path must not directly:

- enter core facts
- enter scoring or technical/risk scoring
- write to `knowledge/`
- write to `reports/`
- replace company announcement source intake
- upgrade management discussion or LLM interpretation into confirmed facts

It may be rendered to `/tmp` for preview and manual review.

## Why Deterministic Backfill Exists

The deterministic layer is not expected to write a polished 90-point human-facing summary.

Its job is to make sure the final LLM sees hard-to-miss material:

- segment revenue and gross margin
- region and sales-mode tables
- production/sales/inventory changes
- customer and supplier concentration
- profit quality, cash flow, inventory impairment, capex, financial assets, goodwill, audit/governance signals
- product/project/customer terms that are easy to lose in long annual reports

If the deterministic prose is slightly mechanical, that is acceptable as long as it is grounded and useful as synthesis input.

## Current Experimental Files

- `scripts/periodic_report_fulltext_preview.py`
- `scripts/utils/periodic_report_evidence_pack.py`
- `scripts/utils/periodic_report_fulltext_llm_analysis.py`
- `scripts/utils/periodic_report_required_metrics.py`
- `scripts/utils/periodic_report_required_financial_metrics.py`
- `scripts/utils/periodic_report_product_project_evidence.py`
- `scripts/utils/hk_periodic_report_fetcher.py`
- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`

Focused tests:

- `tests/reporter/test_periodic_report_fulltext_preview_script.py`
- `tests/utils/test_periodic_report_evidence_pack.py`
- `tests/utils/test_periodic_report_fulltext_llm_analysis.py`
- `tests/utils/test_periodic_report_required_metrics.py`
- `tests/utils/test_periodic_report_required_financial_metrics.py`
- `tests/utils/test_periodic_report_product_project_evidence.py`
- `tests/utils/test_hk_periodic_report_fetcher.py`
- `tests/utils/test_periodic_report_fulltext_intake.py`

## Current Acceptance Gate

Before considering this path stable enough for later integration, run:

```bash
python3 -m pytest tests/reporter/test_periodic_report_fulltext_preview_script.py tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_required_metrics.py tests/utils/test_periodic_report_required_financial_metrics.py tests/utils/test_periodic_report_product_project_evidence.py tests/utils/test_periodic_report_fulltext_llm_analysis.py tests/utils/test_periodic_report_fulltext_intake.py tests/utils/test_hk_periodic_report_fetcher.py -q
git diff --check
```

Sample previews should be generated under `/tmp`, not `reports/` or `knowledge/`.

## Local Cache Policy

`data/raw/periodic_reports/` contains local Jina text caches for repeatable manual validation of annual-report experiments.

Decision as of 2026-06-17:

- keep the directory usable locally for validation speed
- do not commit full annual-report text caches by default
- `.gitignore` excludes `data/raw/periodic_reports/`
- if regression tests need durable fixtures later, create small purpose-built snippets under `tests/fixtures/` instead of committing full cached reports

## LLM Context Hygiene

The current path is usable, but several files are large enough that agents should avoid reading them wholesale unless necessary:

- `scripts/utils/periodic_report_fulltext_llm_analysis.py` (~1,900 lines)
- `scripts/utils/periodic_report_required_metrics.py` (~1,300 lines)
- `scripts/utils/periodic_report_product_project_evidence.py` (~1,300 lines)
- `tests/utils/test_periodic_report_fulltext_llm_analysis.py` (~1,260 lines)

When handing work to another agent, point it to the specific helper function, test name, or failing assertion first. Full-file reads are acceptable for final review, but they are expensive as the default entry point.

## Standalone Preview Entry

`scripts/periodic_report_fulltext_preview.py` is the current standalone preview script.

Example:

```bash
python3 scripts/periodic_report_fulltext_preview.py --stock-code 300777 --stock-name 中简科技 --report-type annual_report --source-intake-section --output /tmp/zhongjian_periodic_report_fulltext_preview_script.md
```

The script:

- reads only local `data/raw/periodic_reports/` caches
- defaults to deterministic preview with `enable_llm=False`
- can render either raw fulltext item Markdown or the Source Intake section wrapper
- writes to `/tmp` by default
- does not write to `reports/` or `knowledge/`

Two extraction regressions are covered after the preview script exposed them:

- A-share `营业收入` must not be overwritten by generic HK `收入` fallback rows.
- Empty A-share `短期借款`/`长期借款` balance-sheet rows must not create HK `borrowings` values from later unrelated numbers.
