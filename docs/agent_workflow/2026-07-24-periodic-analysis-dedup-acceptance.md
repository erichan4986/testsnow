# Periodic Analysis Dedup Acceptance

## Verdict

PASS with local market/PDF environment warnings.

## Scope And Delta

Baseline: `d1be180`.

| Area | Added | Removed | Net |
|---|---:|---:|---:|
| MetricSeries/FinancialScan/ExternalMap tracked runtime | 33 | 84 | -51 |
| Shared contract utility | 30 | 0 | +30 |
| Intake cache materialization | 184 | 172 | +12 |
| **Runtime total** | **247** | **256** | **-9** |
| Tests | 150 | 0 | +150 |

Batch A removed `_unique_evidence`, `_merge_evidence`,
`_merge_mapping_evidence`, and two generic `_decimal` implementations. Caller
specific regex, suffix, precision, rounding, and negative-zero rules remain
local. Batch A runtime net is `-21`.

Batch B added one read-once cache row path and lazy structured material. Public
cache wrappers retain their signatures and latest-only/all-history behavior.
Batch B runtime net is `+12`, below the `+30` hard stop; total cleanup remains
runtime-negative.

## Measured Work Reduction

The two-cache pipeline RED fixture measured the old path at six file reads:
five for the latest cache and one for history. The accepted path reads each file
once, reducing six reads to two. Structured evidence builds fall from four to
two, while the latest display evidence remains a separate single build with its
original `annual_report` contract.

Direct latest-only wrappers were regression-tested and still read only the
latest cache. MetricSeries still reads every matching historical cache. A failed
historical read produces `cache_read_failed` without removing valid history.
Equal mtimes retain deterministic path tie-breaking.

## Implementation Self-Reviews

### Round 1

Found that the first material loader made latest-only public wrappers read every
historical file. Added a failing I/O-count test and introduced narrow
`latest_only` loading. No output contract changed.

### Round 2

Audited empty text, missing year, read failure, processing failure, annual vs
semiannual report types, mtime/path selection, source ordering, and exception
propagation. Added mixed read-failure and equal-mtime characterization tests.
No unresolved blocker or must-fix remains.

## Verification

- New contract tests: passed.
- Intake tests: `33 passed`.
- Architecture/downstream focused suite: passed.
- Full offline suite: `2728 passed, 16 skipped`.
- CI grep gates: all passed.
- Python compilation: passed.
- `git diff --check`: clean.

`python3 scripts/run_黑芝麻智能.py --fast-test` completed and generated fresh
Markdown/HTML using local cached material. Source-boundary and prose checks
passed. The report-quality check lacked daily/weekly/volume/volatility/confidence
because sandboxed HK market requests failed; PDF export was blocked by local
Chromium Mach-port permissions. These are environment limitations outside the
periodic material path.

## Deferred Deliberately

FinancialScan's strict MetricSeries revalidation remains intact. It is a
fail-closed boundary, not removable duplication. Numeric source syntax and
formatting also remain layer-specific. Further line-count compression would
trade away those explicit contracts for little runtime benefit.
