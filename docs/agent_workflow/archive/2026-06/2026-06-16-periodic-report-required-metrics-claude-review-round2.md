# Claude Review Round 2: Periodic Report Required Metrics

Date: 2026-06-16

## Task

Review the R2 revision in:

`docs/agent_workflow/2026-06-16-periodic-report-required-metrics-design.md`

Focus only on the section:

`## Codex R2 Design Revision`

This is still review-only. Do not edit source code, tests, config, reports, `knowledge/`, or `data/raw/`.

## Context

Round 1 found two blockers:

1. `required_business_metrics` could collide with the validated LLM output schema.
2. Broad required-metric bypass could weaken no-fabrication guarantees.

R2 resolves this by:

- making required metrics deterministic prompt/renderer input, not LLM output;
- consuming `periodic_report_evidence_pack.py` blocks first;
- keeping evidence-pack ids separate from fulltext LLM evidence refs;
- allowing validator fallback only by exact normalized value match;
- specifying row schemas, unit handling, missing visibility, renderer signature, and focused tests.

## Review Focus

Please check:

1. Whether R2 fully resolves the Round 1 blockers.
2. Whether the exact normalized value-match rule is safe and implementable.
3. Whether evidence-pack ids vs fulltext ids distinction is clear enough.
4. Whether row schemas are specific enough for tests and renderer.
5. Whether the allowed implementation scope remains helper-only / experimental.
6. Whether any missing tests still block implementation.

## Required Output

Append feedback to the end of:

`docs/agent_workflow/2026-06-16-periodic-report-required-metrics-design.md`

Use this exact heading:

`## Round 2 Feedback`

Include:

- `Status`: `Ready to implement`, `Needs minor fixes`, or `Must-fix before task`
- `R3 Needed`: `Yes` or `No`
- Findings ordered by severity
- Required deltas, if any
- Missing tests, if any
- Blockers, if any

## Constraints

- Do not modify source code.
- Do not run external network.
- Do not call LLM APIs.
- Do not start Chrome/CDP.
- Do not generate reports.
- Do not write `knowledge/`, `reports/`, or `data/raw/`.
