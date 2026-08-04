# Periodic Report Metric Series - Codex Implementation Notes

> Date: 2026-07-24
> Verdict: PASS
> Batch 2 accepted: yes

## Modified Files

Runtime:

- `scripts/utils/periodic_report_structured_facts.py`
- `scripts/utils/periodic_report_metric_series.py` (new)
- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`

Tests:

- `tests/utils/test_periodic_report_structured_facts.py`
- `tests/utils/test_periodic_report_metric_series.py` (new)
- `tests/utils/test_periodic_report_fulltext_intake.py`

Workflow:

- design, two design self-reviews, implementation plan, and this note.

## TDD Evidence

1. Structured-fact provenance: 2 expected failures (`source_doc` keyword and
   missing `InvalidOperation`) -> 13 passed.
2. Initial MetricSeries: module import RED -> 2 passed.
3. Conflict/base/gap rules: 3 expected failures -> 7 passed.
4. Existing derived-fact assembly and compact diagnostics: 4 expected failures
   -> 11 passed.
5. Cache history integration: missing helper import RED -> focused integration
   GREEN.
6. Implementation self-review round 1: stock-less series ids and weak
   pack/fact identity checks produced 3 expected failures -> fixed and GREEN.
7. Implementation self-review round 2: NaN, ambiguous value basis, and isolated
   cache parser failure produced 3 expected failures -> fixed and GREEN.

Final focused set: 55 passed.

## Self-Review Repairs

### Round 1

- added stock code to filing and derived series ids;
- validated exact fact ids, pack/fact periods, source document identity, and
  SHA-256 format;
- diagnosed invalid empty packs instead of silently accepting them;
- kept same-period conflicts fail closed.

### Round 2

- rejected NaN/non-finite filing and derived values;
- rejected derived ratios when more than one filing value basis can satisfy an
  input;
- isolated one historical-cache processing exception so it cannot break the
  current report path;
- confirmed no raw `source_excerpt` is copied into MetricSeries.

No blocker or must-fix remains after Round 2.

## Verification

- focused plus downstream contracts: `384 passed in 4.99s`;
- full offline suite: `2651 passed, 16 skipped in 53.65s`;
- CI grep gates: all passed;
- `git diff --check`: clean;
- module compilation: passed;
- scope audit: the new context key is written only by the intake skill and is
  not read by a renderer, scorer, risk rule, target-price path, or Knowledge
  writer.

## Local-Cache Smoke

Read-only cache root: `/Users/erichan/testsnow/data/raw/periodic_reports`.

| Stock | Packs | Filing series | Points | Derived series | Diagnostics | Time |
|---|---:|---:|---:|---:|---:|---:|
| 中际旭创 | 1 | 2 | 2 | 0 | 2 | 0.459s |
| 黑芝麻智能 | 1 | 2 | 2 | 0 | 2 | 0.298s |

Both local histories currently contain only the 2025 annual cache. The pack is
therefore valid but one-period only. Net profit was missing or could not be
anchored in these two real inputs, so cash conversion was correctly omitted and
diagnosed rather than inferred.

No network, browser, LLM, report generation, cache write, Knowledge write, or
data mutation occurred.

## Runtime Delta

Relative to Batch 1 HEAD:

| File | Added | Removed | Net |
|---|---:|---:|---:|
| `periodic_report_structured_facts.py` | 23 | 6 | +17 |
| `periodic_report_fulltext_intake_skill.py` | 139 | 6 | +133 |
| `periodic_report_metric_series.py` | 508 | 0 | +508 |
| Total runtime | 670 | 12 | +658 |

The new module is deliberately isolated rather than adding cross-period state
to the already large intake or structured-fact owners. It includes validation,
conflict handling, provenance pairing, growth calculations, derived-fact
assembly, and deterministic diagnostics. Further line-count-only compression
would merge those responsibilities and reduce auditability, so no such rewrite
was performed.

## Warning

Real multi-year behavior is fixture-verified but cannot yet be smoke-tested on
the checked local cache set because only 2025 annual text is present. Historical
cache acquisition is a data task, not a reason to weaken or bypass the series
contract.

