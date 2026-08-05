# Chapter 4 Read-Model Consolidation Batch G1 Implementation Notes

> **Date**: 2026-08-05
> **Verdict**: PASS

## Modified Files

Runtime:

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`

Tests:

- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/test_runtime_hygiene.py`

Workflow records:

- Batch G audit, locked design, user-approved review waiver, implementation
  plan, and this implementation note.

## Implementation

- Moved suspicious `0.00亿元` formal-fact rejection into the annual snapshot
  selector with diagnostic reason `suspicious_zero_financial_fact`.
- Replaced the renderer's annual memo-dict round trip with direct grouping and
  formatting of preselected `MaterialRow` objects.
- Made `editorial_slot="portrait"` the only renderer-recognized portrait
  contract; removed renderer fallback selection and scoring.
- Preserved visible-text dedupe, financial title prefixes, group order, row
  refs, and Chapter 4 citation offsets.
- Preserved the formal-thin broker memo renderer because it still owns
  structured sections, forecasts, risks, and single-institution disclosure.
- Removed unused citation-map arguments, thin-body plumbing, the snapshot
  wrapper, `_truncate_title()`, and the obsolete annual compatibility helpers.

## RED / GREEN Evidence

1. Suspicious zero selector test failed because the fact was reported as
   `duplicate_financial_fact`; after moving admission to the selector it
   passed with `suspicious_zero_financial_fact` while the explanation remained.
2. Renderer ownership test failed because an unassigned row was promoted to
   `一句话画像`; after direct `MaterialRow` rendering it passed and an explicitly
   assigned portrait rendered exactly once.
3. Runtime hygiene failed on the remaining `_material_snapshot()` wrapper;
   after deterministic cleanup it passed.
4. The formal-thin broker characterization fixture was aligned with the
   existing citation-owned author contract, then remained green before and
   after runtime refactoring.

## Verification

- Focused: `165 passed`
- Reporter suite: `1261 passed, 6 skipped`
- Final full suite: `2858 passed, 10 skipped`
- Citation regression subset: `3 passed`
- `tools/ci_grep_gates.sh`: PASS
- `git diff --check`: PASS
- Offline smoke: PASS; Markdown and HTML were generated only under
  `/tmp/testsnow_offline_smoke/`.

Citation regression covered:

- single-institution broker section + forecast + risk refs;
- external evidence offset after the full annual snapshot;
- owner-filtered external evidence retaining the full-snapshot offset.

## Runtime Ledger

Relative to HEAD `9f64abb`:

| Runtime file | Added | Removed | Net |
|---|---:|---:|---:|
| `deep_analysis_material_snapshot.py` | 6 | 0 | +6 |
| `deep_analysis_renderer.py` | 41 | 184 | -143 |
| **Total** | **47** | **184** | **-137** |

The result exceeds the 65-line minimum reduction and introduces no replacement
compatibility path.

## Self-Review

- Annual admission and portrait selection now have one owner: the snapshot
  selector.
- The renderer still owns only formatting-level compaction and visible-text
  dedupe.
- Formal-rich and formal-medium routing are unchanged.
- Formal-thin broker content and citation offset formulas are unchanged.
- No producer, synthesis, profile, pipeline, prompt, scoring, technical,
  target, risk, recommendation, data, knowledge, report, or configuration file
  was modified by this batch.

## Blocker / Warning / Deviation

- **Blocker**: none.
- **Warning**: broker read-model consolidation remains deferred until
  `MaterialRow` can preserve forecast metric/period/range and risk structure
  losslessly.
- **Deviation**: none.
- Pre-existing user-owned broker-note and 20260705 report changes were left
  untouched and unstaged.
