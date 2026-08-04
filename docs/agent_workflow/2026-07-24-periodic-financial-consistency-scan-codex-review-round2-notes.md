# Periodic Financial Consistency Scan - Codex Self-Review Round 2

> Date: 2026-07-24
> Verdict: `ok`
> Implementation ready: `yes`

## Findings And Repairs

1. **Must-fix: observations lacked temporal identity.** Two reversal changes for
   one metric would both be `{metric_key, value_kind, value}`. Growth
   observations now require `from_period/to_period`; point observations require
   `period`.
2. **Must-fix: arbitrary value-basis text could corrupt stable ids.** Filing
   admission now locks a lowercase snake-case token grammar. Derived and finding
   ids reuse the validated token without a second normalizer.
3. **Must-fix: unavailable output and diagnostics were underspecified.** The
   exact complete empty payload and top-level/row-level diagnostic codes are now
   fixed.
4. **Must-fix: derived input resolution was not an explicit failure class.** It
   now has a stable diagnostic distinct from malformed derived shape.
5. **Nice-to-have accepted: recursive leakage guard.** Findings reject prose-
   bearing keys, not merely top-level `source_excerpt`.

## Final Ownership Check

- Filing facts, cash-conversion calculation, and 50% predicate:
  `periodic_report_structured_facts.py`.
- Period points and growth calculations: `periodic_report_metric_series.py`.
- Cross-metric relations and status transitions only:
  `periodic_report_financial_scan.py`.
- Report selection/display: unchanged.

## Final Scope Check

The task is one bounded compute layer plus one prerequisite comparability bug
fix. It does not require a report consumer, source-text parser, arbitrary
threshold, persistence format, or LLM. No blocker or must-fix remains.
