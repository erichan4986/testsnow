# Report Skill Import Identity Design

## Goal

Make package-internal report-skill imports deterministic without breaking the existing top-level `report_skills` test/preview entry style.

## Scope

- `report_skills/chart_skills.py`
- `report_skills/data_skills.py`
- Existing chart and data-skill tests

## Contract

- When loaded as `utils.report_skills.*`, import sibling runtime modules through `..reporter` / `..content_quality_gate`.
- When loaded as top-level `report_skills.*`, keep explicit top-level imports.
- Leaf modules must not mutate `sys.path`.
- No chart, fetch, scoring, pipeline-order, or report behavior changes.

## RED/GREEN Gate

`test_stock_reporter_charts` must pass in isolation without an externally supplied `PYTHONPATH`. It currently fails before test execution because top-level `reporter` can resolve to the repository's `reports/` namespace.

## Deferred

The same migration pattern exists in technical modules and other report skills. They remain out of scope until this narrow package path is accepted.
