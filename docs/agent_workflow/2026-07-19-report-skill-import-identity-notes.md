# Report Skill Import Identity Notes

## Changes

- `chart_skills.py` uses package-relative chart/scoring imports under `utils.report_skills` and an explicit top-level branch for legacy `report_skills` callers.
- `data_skills.py` follows the same rule for content quality and data-fetcher imports.
- Both leaf modules no longer mutate `sys.path`.
- `TechnicalRenderer` uses one chart projection helper for full, core-only, and legacy output.

## RED/GREEN

- RED: the core-only renderer test omitted the configured technical chart.
- GREEN: the focused core-only test passes after the shared chart helper.
- RED: isolated `test_stock_reporter_charts` failed before execution because `reporter.chart_generator` resolved through an ambiguous namespace.
- GREEN: the integration test passes without an externally supplied `PYTHONPATH` after package-relative imports.

## Verification

- Report skill and stock reporter focused tests: 39 passed
- Technical renderer and report quality: 117 passed
- Full suite: 2532 passed, 16 skipped
- CI grep gates: passed
- `git diff --check`: clean

## Remaining Import Work

Technical modules and several other report skills still contain direct-import compatibility fallbacks.
They should migrate in small package-owned slices with isolated entry tests; this batch does not claim the
repository-wide import migration is complete.
