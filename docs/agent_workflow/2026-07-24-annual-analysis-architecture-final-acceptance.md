# Annual Analysis Architecture - Final Acceptance

## Verdict

PASS.

The four-batch architecture is accepted. Full-document producer completeness,
cross-year typed facts, deterministic financial findings, and external
compatibility mapping are separate compute layers. Report display selection
remains downstream and does not reduce or mutate the producer facts.

## Accepted Checkpoints

| Batch | Commit | Result |
|---|---|---|
| Full-document coverage manifest | `02f5f84` | accepted |
| Cross-year MetricSeries | `8f41c8b` | accepted |
| Financial consistency/anomaly scan | `cd80dec` | accepted |
| External confirm/contradict/update map | `11945c0` | accepted |

Every batch has a locked design, two design self-reviews with repairs, a TDD
implementation plan, implementation self-review repairs, focused/downstream
tests, and acceptance notes.

## Architecture Boundary Audit

- The coverage manifest records the full admitted document surface; display
  selection does not determine producer completeness.
- MetricSeries reads typed filing facts and keeps report type, year, value
  basis, currency, unit, fact refs, and evidence identity explicit.
- The financial scan consumes only validated MetricSeries data. It does not
  parse report prose or modify scoring/risk/recommendation state.
- The external map consumes only validated target-company v4 financial units,
  an exactly rebound scan, and admitted filing points/changes.
- `confirm` and `contradict` are compatibility relations, not adjudication.
  `update` is chronological and never compares values across periods.
- All compute packs keep report/scoring/risk eligibility false.
- The new external map context key is written only by Synthesis and has no
  renderer, scorer, risk, target-price, technical, recommendation, Knowledge,
  or prompt consumer.
- No LLM prompt, scoring formula, target price, risk rule, technical algorithm,
  or recommendation threshold changed in this goal.

## Verification

- Batch 4 focused scanner/mapper/synthesis: `164 passed`.
- External v4, periodic, renderer, quality, and source-boundary downstream:
  `290 passed`.
- Final full offline suite: `2722 passed, 16 skipped`.
- CI grep gates: all passed.
- Python module compilation: passed.
- `git diff --check`: clean.
- Worktree was clean before and after representative report generation.

## Representative Report Acceptance

### Zhongji Innolight

- Command: `python3 scripts/run_stock_report.py --stock 中际旭创 --no-pdf`
- Exit: 0.
- Fresh outputs:
  - `reports/中际旭创_20260724.md`
  - `reports/中际旭创_20260724.html`
- `check_report_quality.py`: PASS.
- `check_report_source_boundary.py`: PASS.
- `check_report_prose_quality.py`: PASS with existing cross-section theme and
  assertion-wording warnings.
- No external-map schema name, observation id, or mapping id leaked into the
  Markdown or HTML output.

### Black Sesame Fast Test

- Command: `python3 scripts/run_黑芝麻智能.py --fast-test`
- Exit: 0; Markdown and HTML generated.
- Source-boundary and prose checks passed.
- The report-quality check lacked daily/weekly/volume/volatility/confidence
  because sandboxed HK market data was unavailable. PDF export was blocked by
  local Chromium sandbox permissions. These are environment limitations, not
  architecture regressions; the unsandboxed A-share representative report
  passed all three report gates.

## Read-Only Real-Material Smoke

Canonical v4 external packs and local annual caches for Zhongji, Fudan, and
Black Sesame were read without writes. All external displays validated. The
local cache set remains one-period, and Fudan has no admitted filing series, so
the mapper correctly returned `partial` with zero fabricated live relations.
Multi-year confirm/contradict/update behavior is covered by exact fixtures.

## Remaining Data Work

The architecture is complete. Real cross-year findings and live external
relations will become populated as additional historical annual/semiannual
caches are added. Missing history must be acquired as data; it must not be
replaced by fuzzy matching, LLM adjudication, or inferred filing values.
