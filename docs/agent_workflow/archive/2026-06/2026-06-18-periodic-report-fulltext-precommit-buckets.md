# Periodic Report Fulltext Pre-commit Buckets

Date: 2026-06-18

## Scope

This audit covers the annual/semiannual fulltext experimental path after:

- deterministic required business metrics
- deterministic required financial-risk metrics
- product/project/customer backfill
- HK periodic-report cache helpers
- Source Intake material-layer renderer and optional pipeline ctx switch
- PerStockReporter source_intake sub-config wiring
- `run_中简科技.py --fast-test` local-cache preview validation

This is a pre-commit organization note. It does not approve broad report-pipeline behavior, `KnowledgeSynthesizer`, scoring, risk scoring, technical analysis, or runtime caches.

## Bucket 1: Mainline Code And Tests

These files belong together as the current functional path.

### Fulltext Analysis And Deterministic Inputs

- `scripts/utils/periodic_report_fulltext_llm_analysis.py`
- `scripts/utils/periodic_report_required_metrics.py`
- `scripts/utils/periodic_report_required_financial_metrics.py`
- `scripts/utils/periodic_report_product_project_evidence.py`
- `tests/utils/test_periodic_report_fulltext_llm_analysis.py`
- `tests/utils/test_periodic_report_required_metrics.py`
- `tests/utils/test_periodic_report_required_financial_metrics.py`
- `tests/utils/test_periodic_report_product_project_evidence.py`

### HK Helper

- `scripts/utils/hk_periodic_report_fetcher.py`
- `tests/utils/test_hk_periodic_report_fetcher.py`

### Source Intake Boundary

- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`
- `scripts/utils/evidence_note_writer.py`
- `scripts/utils/stock_reporter.py`
- `config/stocks.json`
- `tests/utils/test_periodic_report_fulltext_intake.py`
- `tests/utils/test_evidence_note_writer.py`
- `tests/reporter/test_source_intake_evidence_renderer.py`
- `tests/reporter/test_source_intake_merge_skill.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_analysis_skills.py`
- `tests/reporter/test_claim_risk_signal_skill.py`
- `tests/reporter/test_pipeline_integration.py`
- `tests/reporter/test_stock_reporter_source_intake_config.py`

### Preview Script

- `scripts/periodic_report_fulltext_preview.py`
- `tests/reporter/test_periodic_report_fulltext_preview_script.py`

### Ignore Policy And Generated Test Output Cleanup

- `.gitignore`
- deleted `tests/reporter/tmp_out/*`

Decision: keep the deletion. Pipeline tests now write to `tmp_path`, and these tracked files were stale generated output.

## Bucket 2: Design And Sample Evidence

Keep these docs for auditability and future handoff:

- `docs/agent_workflow/2026-06-17-periodic-report-experimental-path-status.md`
- `docs/agent_workflow/2026-06-17-periodic-report-experimental-path-scoped-review.md`
- `docs/agent_workflow/2026-06-17-periodic-report-scoped-diff-review.md`
- `docs/agent_workflow/2026-06-17-periodic-report-source-intake-integration-design.md`
- `docs/agent_workflow/2026-06-17-yingjixin-periodic-report-llm-preview.md`
- `docs/agent_workflow/2026-06-17-huadajiutian-periodic-report-llm-preview.md`
- `docs/agent_workflow/2026-06-17-saiweiwei-periodic-report-llm-preview.md`
- `docs/agent_workflow/2026-06-18-periodic-report-fulltext-precommit-buckets.md`

The company preview docs are intentionally short and record why the rules were shaped this way. They are not runtime outputs.

## Bucket 3: Do Not Commit

Do not include local runtime caches or previews:

- `data/raw/periodic_reports/**`
- `/tmp/*annual*`
- `/tmp/*fulltext*`
- generated `reports/` or `knowledge/` files unless a separate report-validation task explicitly approves them

Current `.gitignore` should keep the periodic-report cache out of git.

## Real Entry Preview

Validated after wiring the optional source-intake sub-config:

```bash
cd scripts && python3 run_中简科技.py --fast-test
```

Local Claude Code verification reported:

- `reports/中简科技_20260619.md`: 14,444 B
- `reports/中简科技_20260619.html`: 9,894 B
- `reports/中简科技_20260619.pdf`: 1,560,593 B
- `check_report_quality`: PASS
- fulltext section rendered under `Source Intake 分层证据观察`
- source row stayed `75 / professional_analysis`
- no `confirmed_fact` / `fact_candidate` promotion
- no scoring, risk scoring, or KnowledgeSynthesizer core-fact leak

## Bucket 4: Later Refactor / Performance Work

Do not mix this into the current stabilization commit.

### Large File Splits

- `scripts/utils/periodic_report_fulltext_llm_analysis.py`
  - likely split into prompt builder, validator, renderer, risk backfill, and product/project integration.
- `scripts/utils/periodic_report_required_metrics.py`
  - likely split A-share table extraction from shared normalization and concentration parsing.
- `scripts/utils/periodic_report_product_project_evidence.py`
  - likely split constants, snippet extraction, scoring, and summary generation.

### Performance Backlog

- product/project snippet de-duplication should preserve order with a set.
- marker scanning should use precompiled combined regexes per marker group where practical.
- diversity-token scoring should avoid repeated linear scans over large token tuples.

Before changing performance internals, add equivalence tests plus a small benchmark fixture.

## Suggested Focused Gate

```bash
python3 -m pytest \
  tests/utils/test_periodic_report_fulltext_llm_analysis.py \
  tests/utils/test_periodic_report_required_metrics.py \
  tests/utils/test_periodic_report_required_financial_metrics.py \
  tests/utils/test_periodic_report_product_project_evidence.py \
  tests/utils/test_hk_periodic_report_fetcher.py \
  tests/utils/test_periodic_report_fulltext_intake.py \
  tests/utils/test_evidence_note_writer.py \
  tests/reporter/test_periodic_report_fulltext_preview_script.py \
  tests/reporter/test_source_intake_evidence_renderer.py \
  tests/reporter/test_source_intake_merge_skill.py \
  tests/reporter/test_synthesis_skills.py \
  tests/reporter/test_analysis_skills.py \
  tests/reporter/test_claim_risk_signal_skill.py \
  tests/reporter/test_pipeline_integration.py -q
```

Also run:

```bash
git diff --check
```

## Current Recommendation

Proceed with Bucket 1 and Bucket 2 as the next commit group. Defer Bucket 4 until after one local full-report preview validates that `enable_source_intake=True` plus `enable_periodic_report_fulltext_intake=True` displays the material-layer section in a real report.
