# Structured Financial History Source - Claude Review Round 1

## Role

Perform a read-only architecture and implementation-readiness review. Do not
modify runtime code, tests, configuration, data, Knowledge notes or reports.

## Primary Design

Read:

- `docs/agent_workflow/2026-07-29-structured-financial-history-source-design.md`

## Required Context

Inspect the real current code and contracts:

- `scripts/utils/reporter/data_fetcher.py`
- `scripts/utils/periodic_report_metric_series.py`
- `scripts/utils/periodic_report_structured_facts.py`
- `scripts/utils/periodic_report_contract_utils.py`
- `scripts/utils/periodic_report_financial_scan.py`
- `scripts/utils/periodic_external_evidence_map.py`
- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
- `scripts/utils/report_skills/__init__.py`
- corresponding tests under `tests/utils/` and `tests/reporter/`

Also inspect the current dirty diff. Do not assume the summary is correct and do
not ask to revert unrelated existing worktree changes.

## Review Questions

1. Does the design actually eliminate historical PDF processing from the
   production history path while preserving latest-year annual narrative and
   current filing core facts?
2. Are the A-share and HK Eastmoney field/date/report-type rules precise enough
   to avoid quarterly, adjusted-profit, currency and wrong-period admission?
3. Is the compact cache sufficient to reproduce and audit each selected metric
   without storing annual-report prose or the provider's entire payload?
4. Can `fact_packs` and `source_points` share one MetricSeries grouping/change
   implementation without weakening the accepted v1 validator?
5. Does the proposed cash-conversion helper move preserve one formula owner,
   diagnostics and formula version, or is there a smaller correct approach?
6. Is the hard boundary preventing API history from reaching current core facts,
   Chapter 4.1, scoring, target, risk, technical or recommendation fully testable?
7. Does keeping the existing intake skill as the context publisher avoid a
   second orchestration owner, or hide an ownership problem?
8. Are explicit refresh, atomic retention and cache-only report behavior
   sufficient for provider failures and reproducible reports?
9. Is the proposed runtime target `+220`, hard stop `+300`, credible? Identify
   concrete old production code that should be replaced or later deleted.
10. Are any required tests, failure modes or stop conditions missing?

## Required Output

Write findings to:

`docs/agent_workflow/2026-07-29-structured-financial-history-source-claude-review-round1-notes.md`

Use this structure:

- `verdict: ok | needs_revision`
- blockers
- must-fix
- nice-to-have
- requirement-test gaps
- ownership and duplicate-path audit
- runtime-budget assessment
- implementation-ready: yes | no

Every blocker/must-fix must cite concrete file/function evidence and propose a
narrow design correction. Do not implement fixes.
