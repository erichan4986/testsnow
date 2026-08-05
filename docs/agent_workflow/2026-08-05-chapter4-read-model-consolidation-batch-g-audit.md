# Chapter 4 Read-Model Consolidation Batch G Audit

## Verdict

`implementation_candidate`

The Chapter 4 pipeline has one canonical selection owner in
`deep_analysis_material_snapshot.py`, but `DeepAnalysisRenderer` still keeps
two compatibility-shaped projection paths. A narrow consolidation can remove
roughly 130-180 runtime lines without changing annual, broker, external, LLM,
scoring, target-price, risk, or recommendation semantics.

This audit is read-only with respect to runtime and tests.

## Current Ownership Map

1. `SynthesisSkill` produces `annual_report_memo`, `broker_research_memo`, and
   `deep_analysis_display`.
2. `build_deep_analysis_material_snapshot()` adapts those three inputs into
   `MaterialRow` plus one global snapshot citation namespace.
3. `select_annual_display_rows()`, `_select_broker_display_rows()`, and
   `select_incremental_external_display_rows()` own Chapter 4 admission.
4. `build_chapter4_view_model()` packages the selected rows for
   `formal_medium`.
5. `DeepAnalysisRenderer` formats the read model, but
   `formal_thin_external_rich` repeats selector orchestration and renders the
   broker memo through a separate dict-based path.

## Findings

### G1. Annual portrait and grouping have a second renderer owner

`_annual_material_profile_section()` converts already selected `MaterialRow`
objects back into memo-shaped dictionaries and calls
`_annual_report_business_profile_section()`. The latter repeats:

- role grouping;
- portrait fallback selection and scoring;
- visible-body normalization;
- visible-text deduplication;
- suspicious-zero filtering.

The canonical snapshot selector already assigns `editorial_slot="portrait"`,
applies role budgets, rejects display noise, and deduplicates annual rows.

Implementation direction: render preselected `MaterialRow` objects directly.
Keep only formatting concerns in the renderer: headings, compact display text,
title prefix for financial rows, refs, and final visible-text dedupe.

Expected removable surface:

- `_annual_report_business_profile_section()`;
- `_annual_rows_by_group()`;
- `_annual_row_text_key()`;
- `_select_annual_portrait_row()`;
- `_is_suspicious_zero_annual_row()` if the public selector regression tests
  prove suspicious-zero rejection before rendering.

Estimated net runtime reduction: 75-105 lines.

### G2. Formal-thin broker rendering bypasses MaterialRow

`formal_thin_external_rich` builds a full snapshot and uses snapshot rows for
annual/external material, but reads `broker_research_memo` again through
`_broker_research_memo_section()`. It therefore needs separate annual, broker,
and external offsets plus `_max_snapshot_ref()`.

Implementation direction: use the snapshot's broker `MaterialRow` objects and
the existing attributed broker formatter. Snapshot refs are already global;
all Chapter 4 rows should use the single baseline-to-snapshot offset.

The thin profile must retain the single-institution disclosure when the broker
memo status is `single_institution`.

Expected removable surface:

- `_broker_research_memo_section()`;
- `_material_snapshot()`;
- `_max_snapshot_ref()`;
- thin-only broker offset bookkeeping and raw memo reads.

Estimated net runtime reduction: 45-65 lines.

### G3. One deterministic dead helper remains

`DeepAnalysisRenderer._truncate_title()` has no runtime, test, preview, or tool
caller. It can be deleted with a hygiene assertion.

Estimated net runtime reduction: 6 lines.

### G4. External narrative adapters are not duplicate owners

`_external_topic_narrative_paragraph()` and
`_external_verified_rows_paragraph()` only adapt two row shapes into
`_external_evidence_paragraph()`. Admission, owner-delta filtering, source
order, and cross-source deduplication remain in the snapshot. Retain these
format adapters.

### G5. `synthesis_skills.py` is large but not a deletion candidate in G1

The audit found no zero-call synthesis block. Its annual memo cleaner overlaps
producer/material-pack cleanup, but it also protects the in-memory-card path.
Removing it is a report-content behavior change, not a mechanical cleanup.

Defer that work to a separate memo pass-through task with three-stock report
comparison. Do not split `synthesis_skills.py` merely to move lines between
files.

## Locked Boundaries

Allowed runtime scope for a future G1 implementation:

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`

Allowed tests:

- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/test_runtime_hygiene.py`

Do not modify:

- `synthesis_skills.py` or annual/broker/external producers;
- report profiles or pipeline order;
- LLM prompts or synthesis behavior;
- scoring, technical analysis, target price, risk, or recommendation logic;
- data, knowledge, reports, or configuration.

## Failure Modes And Tests

| Failure mode | Visible regression | Required guard |
|---|---|---|
| annual portrait is reselected or lost | weak first row or missing one-line portrait | selector-owned portrait tests plus public render test |
| hidden annual rows reappear | Chapter 4.1 returns to material-dump output | role-budget and exact output-count tests |
| formal-thin refs are renumbered | external refs change from the full snapshot offset | existing full-snapshot `[^5]` / `[^6]` tests |
| broker refs use local memo IDs | citations point to annual or external source | thin profile broker citation identity test |
| single-institution warning disappears | one broker is presented as consensus | thin profile disclosure test |
| external owner filtering changes | duplicate annual/external fact reappears | existing owner-filter and narrative tests |
| formal-rich behavior changes | old 4.1-4.4 path differs | formal-rich renderer regression suite |

## Verification Baseline

- Focused snapshot/renderer/synthesis suite: `257 passed`.
- Current full-repository verification at Batch F close: `2858 passed, 10 skipped`.
- CI grep gates and offline Black Sesame smoke passed at Batch F close.

Future implementation gates:

1. focused snapshot/renderer tests;
2. reporter downstream suite;
3. full repository suite;
4. `bash tools/ci_grep_gates.sh`;
5. `git diff --check`;
6. Black Sesame offline smoke;
7. runtime net reduction target at least 110 lines; stop if the replacement
   grows runtime or requires a third projection path.

## Deferred Items

- Annual memo cleanup/pass-through unification in `SynthesisSkill`.
- Extending `Chapter4ViewModel` to every profile if doing so changes profile
  labels, broker admission, or citation semantics.
- Historical workflow-document cleanup.
- User-owned broker note refreshes, old reports, and plan-packet artifacts.

## Recommendation

Implement G1 as a Level 3 narrow refactor after design review. The safest
sequence is annual direct rendering, formal-thin broker unification, dead-helper
removal, then full verification. Do not combine the deferred synthesis cleanup
with this batch.
