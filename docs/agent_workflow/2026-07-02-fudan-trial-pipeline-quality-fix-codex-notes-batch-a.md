# Batch A Quality Gates Implementation Notes

## Scope

Implemented Batch A quality gates only.

No report entry was run. No changes were made to LLM prompt/synthesis, Direct-Only filtering, financial fact pack, unit normalization, scoring, technical analysis, Xueqiu/CDP/Playwright, data collection, or generated report content.

## Files Changed

| File | Change |
|---|---|
| `scripts/utils/report_quality.py` | Added Markdown-level gates for deep-analysis subsection completeness, MLCC/product mismatch, financial unit conflict, metric-specific financial missing contradiction, and header config missing warning. |
| `tests/reporter/test_report_quality.py` | Added focused tests for the five Fudan trial failure modes and one negative metric-specific missing-data test. |

## Gates Added

| Code | Severity | Purpose |
|---|---|---|
| `missing_deep_analysis_subsection` | error | Fails when `## 四、深度分析` exists but 4.1 / 4.2 / 4.3 is missing. |
| `product_industry_mismatch` | error | Fails obvious MLCC-style product mismatch when report itself says no direct relation. |
| `financial_fact_unit_conflict` | error | Fails when core facts show 万元-level key financials while the report also contains 亿元-level same-family metrics. |
| `financial_data_missing_contradiction` | error | Fails when 4.2 says revenue/profit is missing while the report contains revenue/profit facts. |
| `header_config_missing` | warning | Warns when report header still renders `所属赛道` or `可比公司` as `—`. |

## Red / Green

Initial test run after adding tests failed as expected:

- `missing_deep_analysis_subsection` not emitted.
- `product_industry_mismatch` not emitted.
- `financial_fact_unit_conflict` not emitted.
- `financial_data_missing_contradiction` not emitted.
- `header_config_missing` not emitted.

After implementation, focused quality tests passed.

## Verification

```text
python3 -m pytest tests/reporter/test_report_quality.py -q
# 31 passed
```

```text
python3 -m pytest tests/reporter/test_report_quality.py tests/reporter/test_stock_reporter_source_intake_config.py tests/reporter/test_assembly_skills.py tests/reporter/test_deep_analysis_renderer.py -q
# 118 passed
```

```text
bash tools/ci_grep_gates.sh
# ci_grep_gates: all gates passed
```

```text
git diff --check
# clean
```

## Old Fudan Report Check

The existing generated report was not regenerated. Running the new checker against it now fails, as intended:

```text
python3 scripts/check_report_quality.py reports/复旦微电_20260702.md
# FAIL
# missing_deep_analysis_subsection: missing=4.3
# product_industry_mismatch: MLCC with negated direct relation
# financial_fact_unit_conflict: 营业收入|39.82万元
# financial_data_missing_contradiction: metric=profit
# header_config_missing: warning
```

This confirms the new gates catch the issues found during manual review of the old report.

## Blockers / Deviations

- Blockers: none.
- Deviations: none.
- Remaining pipeline fixes are Batch B and Batch C: Direct-Only filtering and financial fact/unit normalization.
