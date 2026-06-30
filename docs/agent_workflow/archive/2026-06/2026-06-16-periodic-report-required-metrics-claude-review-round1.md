# Claude Review Round 1: Periodic Report Required Metrics

Date: 2026-06-16

## Task

Review the design doc:

`docs/agent_workflow/2026-06-16-periodic-report-required-metrics-design.md`

This is a review-only task. Do not edit source code, tests, config, reports, `knowledge/`, or `data/raw/`.

## Context

The current experimental full-text annual-report path can generate six-section LLM summaries, but it omitted required operating metrics in the Yingjixin 2025 annual-report output:

- product/segment gross margins;
- product-level inventory changes;
- customer/supplier concentration.

The source annual report text and `fulltext-2-3` block did contain these metrics, so the root issue is not data fetch. It is that the current prompt/validator pipeline treats hard annual-report metrics as optional LLM narrative.

The proposed design adds a deterministic `required_business_metrics` layer and renders it before the LLM sections.

## Review Focus

Please evaluate:

1. Whether the proposed deterministic metrics schema is sufficient.
2. Whether the table/header-driven extraction approach is robust for A-share annual and semiannual reports.
3. Whether the design avoids overfitting to Yingjixin or Zhongjian.
4. Whether the validator change is safe and does not weaken no-fabrication guarantees.
5. Whether the allowed/forbidden file list is appropriate.
6. Whether the Yingjixin and Zhongjian acceptance criteria are concrete enough.
7. Missing tests, especially around Jina spacing, line-broken product names, and table truncation.

## Required Output

Append your feedback to the end of:

`docs/agent_workflow/2026-06-16-periodic-report-required-metrics-design.md`

Use this exact heading:

`## Round 1 Feedback`

Include:

- `Status`: one of `Ready to implement`, `Needs minor fixes`, or `Must-fix before task`
- `R2 Needed`: `Yes` or `No`
- Findings ordered by severity
- Required design deltas
- Missing tests
- Any blockers

## Constraints

- Do not modify any source code.
- Do not run external network.
- Do not call LLM APIs.
- Do not start Chrome/CDP.
- Do not generate reports.
- Do not write `knowledge/`, `reports/`, or `data/raw/`.
