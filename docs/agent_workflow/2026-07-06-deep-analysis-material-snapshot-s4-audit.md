# Deep Analysis MaterialSnapshot S4 Deletion Audit

Date: 2026-07-06

## Verdict

Do not delete renderer citation helpers in this pass.

S1-S3 are validated by focused tests and the dual-stock smoke report, but the
remaining helpers still serve active compatibility paths:

- `formal_medium` / `formal_rich` legacy 4.4 external addendum;
- non-annual-broker `formal_thin_external_rich` fallback layout used by tests
  and still accepted by report-quality/source-boundary gates;
- per-section local citation source lists.

Deleting these helpers now would be a behavior change, not a safe slimming step.

## Smoke Gate Status

Latest dual-stock verification after the citation hygiene fix:

- `复旦微电`: `formal_thin_external_rich`,
  `annual_broker_external_checklist`, quality/source-boundary pass.
- `中际旭创`: `formal_medium`, legacy 4.1/4.2/4.3 plus 4.4, quality/source-boundary pass.
- Citation hygiene: body refs and global `## 引用来源` refs match for both
  reports; missing and unused refs are zero.

## Helper Audit

| Helper / variable | Current active use | S4 decision |
| --- | --- | --- |
| `annual_citation_offset` | Offsets annual memo body refs after baseline citations. Snapshot currently supplies allocation counts, but renderer still passes the offset to `_annual_report_memo_section()`. | Keep. Remove only after annual memo rows render directly from snapshot rows or row-level ref maps. |
| `broker_citation_offset` | Same for broker memo sections, forecast ranges, and risks. | Keep. Forecast/risk citation contract still depends on visible body offsets. |
| `curated_citation_offset` | Legacy 4.4 addendum offset for `formal_rich` / `formal_medium`. | Keep. The Zhongji smoke report still uses legacy 4.4. |
| `_offset_citations()` | Used by annual/broker per-section source lists, legacy 4.4 narrative/grouped addendum, and snapshot global citation merge. | Keep. Too many active callers. |
| `_merged_citations()` | Used by non-snapshot global citation path for legacy profiles and old formal-thin fallback. | Keep until legacy 4.4 and old formal-thin fallback migrate or are explicitly removed. |
| `_used_formal_thin_external_citations()` | Used only when `formal_thin_external_rich` does not have the annual-broker layout. | Keep for now. It is a compatibility path; deleting requires retiring old formal-thin layout tests/gates. |
| `_curated_external_used_refs_from_rows()` / `_curated_external_used_refs_from_grouped_rows()` / `_curated_external_display_ref_map()` | Used by legacy 4.4 narrative/grouped addendum to dedupe/remap visible external citations. | Keep. These are still required for `formal_medium` / `formal_rich` 4.4. |
| `_visible_citations_only()` | New final safety filter for global citation hygiene. | Keep. It prevents stale citations and backs the new quality gate. |

## Safe Cleanup Candidates Deferred

These are plausible future deletions, but each needs a separate behavior change:

1. Retire non-annual-broker `formal_thin_external_rich` layout.
   - Then `_verification_checklist_section()` and
     `_used_formal_thin_external_citations()` become stronger deletion
     candidates.
   - Required first: update renderer tests, report-quality gates, and
     source-boundary gates so the annual-broker layout is the only supported
     formal-thin layout.

2. Migrate legacy 4.4 addendum rendering to `MaterialSnapshot` row maps.
   - Then `_curated_external_*` ref collection/remap helpers can be revisited.
   - Required first: preserve current citation dedupe behavior for
     narrative/grouped 4.4 paragraphs.

3. Render annual/broker memo rows directly from snapshot rows.
   - Then annual/broker offsets can be simplified or removed.
   - Required first: prove body text remains text-equivalent for formal-thin
     annual memo and broker memo reports.

## Current S4 Stop Decision

Stop deletion here.

The codebase is safer with the current helpers than with a premature removal.
The meaningful slimming opportunity is not mechanical deletion, but a future
design choice:

- either retire old formal-thin fallback entirely;
- or migrate legacy 4.4 to the same snapshot-driven citation contract.

