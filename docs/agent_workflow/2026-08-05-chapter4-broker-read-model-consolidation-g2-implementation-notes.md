# Chapter 4 Broker Read-Model Consolidation G2 Implementation Notes

## Result

- baseline: `77dd423`
- verdict: `PASS`
- external review: skipped by explicit user-approved waiver
- blockers: none
- deviations: none

## Modified Files

Runtime:

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`

Tests:

- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/test_runtime_hygiene.py`

Workflow records:

- G2 design, external review prompt, user waiver, task, and these notes

No producer, synthesis skill, memo schema, selector, profile, pipeline,
prompt, scoring, technical, target-price, risk, recommendation, data,
knowledge, or report file was modified by G2.

## RED / GREEN Evidence

1. Lossless broker fields:
   - RED: `MaterialRow` raised `AttributeError` for `broker_metric`.
   - GREEN: metric, period, range/body, and memo status test passed.
2. Snapshot-only formal-thin rendering:
   - RED: three tests failed because the renderer read conflicting raw memo,
     omitted snapshot rows, and leaked an empty single-institution heading.
   - GREEN: snapshot section/forecast/risk, generic attribution, fail-closed
     fallback, source order, and global refs passed.
3. Structural guard:
   - current implementation passed;
   - the same token guard run against `HEAD` found all five legacy tokens and
     failed as expected.

## Requirement-Test Matrix

| Requirement | Implementation | Verification |
|---|---|---|
| Preserve metric/period/range/status | optional `MaterialRow` fields populated by `_broker_rows()` | `test_snapshot_preserves_lossless_broker_forecast_fields_and_memo_status` |
| Snapshot is formal-thin owner | `broker_material_rows` passed to `_formal_thin_broker_section()` | conflicting absent raw memo fixture |
| Preserve all admitted broker rows | full broker tuple; no formal-medium selector/cap/dedupe | exact source-order assertion |
| Preserve named and unnamed attribution | generic labels normalized to unnamed author | named and generic forecast fixtures |
| One citation formula | row global refs plus annual/baseline offset | visible `[^5]`-`[^7]` and source assertions |
| Fail closed on no rows | row formatter fallback | empty snapshot with conflicting single-institution memo |
| Remove second owner | deleted raw memo renderer, author lookup, max-ref helper, and broker offset | runtime hygiene test and source grep |
| Preserve formal-medium/external behavior | selector and external narrative code unchanged | focused, reporter, and full suites |

## Runtime Ledger

Against `77dd423`:

| File | Added | Removed | Net |
|---|---:|---:|---:|
| `deep_analysis_material_snapshot.py` | 6 | 0 | +6 |
| `deep_analysis_renderer.py` | 33 | 78 | -45 |
| **Runtime total** | **39** | **78** | **-39** |

The result meets the design target of a 20-40 line runtime reduction.

## Final Verification

- focused: `170 passed`
- reporter: `1264 passed, 6 skipped`
- full: `2863 passed, 10 skipped`
- `tools/ci_grep_gates.sh`: all gates passed
- `git diff --check`: clean
- offline smoke: Black Sesame Markdown and HTML generated under
  `/tmp/testsnow_offline_smoke`

## Self-Review

Pass 1 found and fixed generic attribution duplication and explicitly locked
the accepted-but-empty fail-closed behavior before implementation.

Pass 2 checked the final diff, citation normalization, selector ownership, and
runtime budget. A suspected string citation-key regression was disproved by
the existing `_merged_citations()` path; the redundant immediate-pass test was
removed and the merge was simplified without changing behavior.

Existing user changes to broker notes, legacy report files, and the plan packet
were preserved and not staged, reverted, or edited by this batch.
