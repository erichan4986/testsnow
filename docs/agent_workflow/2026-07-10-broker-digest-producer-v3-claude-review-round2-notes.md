verdict: ok

summary:
The revised design closes every Round 1 item by assigning explicit ownership,
listing the exact legacy helpers to replace, splitting work into two bounded
batches, and adding the missing test contracts. It no longer treats missing
implementation as a design blocker; instead each Round 1 finding is now a
concrete Batch A or Batch B deliverable with a hard stop at +100 net runtime
lines per batch. The source-boundary invariants remain intact, and the formal
report acceptance step is correctly scoped as a local post-implementation check
rather than a CI gate.

round1_closure:
  - id: B1
    status: closed
    evidence: |
      Design §8 now explicitly states that `_render_note()` writes both
      `excerpt_cleaner_version: broker_ocr_v2` and
      `selection_version: broker_digest_v3`, and that
      `_has_current_diagnostics_note_shape()` requires the current selection
      version. It also clarifies that `_is_legacy_broker_digest_note()` continues
      to archive old notes while a current-schema note missing only
      `selection_version` is refreshed in place.

  - id: B2
    status: closed
    evidence: |
      Design §9 splits implementation into Batch A and Batch B, lists the exact
      legacy helpers each batch replaces, and states hard stop conditions of +100
      net runtime lines per batch. Invariants §2 also bind runtime growth per
      batch.

  - id: M1
    status: closed
    evidence: |
      Batch A deliverables include "boundary-safe excerpt construction with no
      final `[:900]` slicing." Design §6.1 preserves the terminal-punctuation and
      bounded-extension rules. This is now an explicit Batch A replacement task.

  - id: M2
    status: closed
    evidence: |
      Batch A deliverables include "explicit score parts and total score" and
      "diagnostics that explain selected, skipped, and rejected candidates." The
      replacement list includes `_diagnostic_entry`, and §5/§7 define the six
      score parts.

  - id: M3
    status: closed
    evidence: |
      Batch B deliverables include "card-family claim/evidence admission." Design
      §6.2 defines the claim+evidence requirement for each family, and §11 adds
      one claim-without-evidence rejection test per family.

  - id: M4
    status: closed
    evidence: |
      Batch A deliverables include "severe OCR/numeric-damage rejection," and
      §11 requires a test proving severe damage produces a `rejected` diagnostic
      rather than merely a lower score.

  - id: M5
    status: closed
    evidence: |
      Batch B deliverables include "source-unit semantic roles" and
      "complementary unit selection in source order." The replacement list
      includes `_select_section_candidates`, and §11 requires source-substring
      assertions for every selected unit.

  - id: M6
    status: closed
    evidence: |
      Batch B deliverables include "the same complete-unit rules for no-heading
      fallback," and the replacement list includes `_fallback_excerpt`. §11 adds
      coherent single-unit and no-heading fallback tests.

  - id: M7
    status: closed
    evidence: |
      Covered by the same §8 contract as B1: `_render_note()` now writes
      `selection_version`, and the freshness check keys on it instead of relying
      solely on `excerpt_cleaner_version`.

remaining_blockers: []

remaining_must_fix: []

budget_assessment:
  batch_a: |
    Acceptable. The four legacy helpers to replace currently occupy ~50 runtime
    lines. The design allows at most 130 replacement lines, targeting a net delta
    of +80 and hard-stopping at +100. This is tight but explicit and measurable.
    The stop condition in §13 means implementation must pause if the delta
    exceeds +100 lines.
  batch_b: |
    Acceptable. The seven legacy helpers to replace currently occupy ~100 runtime
    lines. The design targets no more than +80 net runtime lines and hard-stops
    at +100. The "if a third selection path is needed, implementation stops"
    clause in §9.2 is an important guardrail.

recommended_next_step:
Approve the design and begin Batch A implementation. Before starting Batch B,
verify that Batch A passes its focused tests, stays within the +100 net runtime
line limit, and that the new `selection_version` stale-note refresh works as
specified.
