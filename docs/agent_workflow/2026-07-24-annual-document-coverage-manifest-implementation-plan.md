# Annual Document Coverage Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development and executing-plans task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a compact, deterministic document/section/block/unit coverage ledger without changing annual-report evidence or report output.

**Architecture:** A new pure module owns coverage schema, section inventory, validation, and producer finalization. The evidence builder supplies pre-limit/prioritized/selected block sets; the narrative producer adds its existing unit/card decisions. The finalized manifest is persisted inside existing producer diagnostics.

**Tech Stack:** Python standard library, existing deterministic periodic-report producers, pytest.

---

## File Map

Runtime:

- Create `scripts/utils/periodic_report_coverage_manifest.py`: schema, inventory, block lifecycle, validation, finalization.
- Modify `scripts/utils/periodic_report_evidence_pack.py`: preserve extraction stages and attach evidence-stage coverage.
- Modify `scripts/utils/periodic_report_narrative_evidence_cards.py`: finalize coverage after unit/card decisions.

Tests:

- Create `tests/utils/test_periodic_report_coverage_manifest.py`.
- Modify `tests/utils/test_periodic_report_evidence_pack.py`.
- Modify `tests/utils/test_periodic_report_narrative_evidence_cards.py`.
- Modify `tests/utils/test_periodic_report_narrative_pack_store.py` only if the existing round-trip fixture does not already prove nested diagnostics integrity.

Notes:

- Create `docs/agent_workflow/2026-07-24-annual-document-coverage-manifest-codex-notes.md`.

## Task 1: Section Inventory And Validation

- [ ] Add `test_periodic_report_coverage_manifest.py` with RED tests for:
  - A-share and HKEX Markdown heading order;
  - duplicate headings retaining distinct full-hash IDs;
  - synthetic root fallback;
  - empty parent heading becoming `structural_only`;
  - explicit page marker accepted and TOC number rejected;
  - identical input identity;
  - malformed span/summary/schema rejection;
  - recursive absence of `text`, `source_excerpt`, and `source_units` fields.
- [ ] Run the new module tests and verify import/function-not-found RED.
- [ ] Create constants and APIs:

```python
SCHEMA_VERSION = "annual_document_coverage_manifest.v1"
COORDINATE_SPACE = "periodic_report_cleaned_text.v1"

def build_periodic_report_coverage_manifest(
    cleaned_text: str, *, report_type: str, document_style: str,
    extracted_candidates: list[dict], prioritized_candidates: list[dict],
    selected_blocks: list[dict],
) -> dict: ...

def validate_periodic_report_coverage_manifest(manifest: object) -> tuple[str, ...]: ...

def unavailable_periodic_report_coverage_manifest(
    *, report_type: str = "", document_style: str = "", reason: str,
) -> dict: ...
```

- [ ] Implement source-visible heading inventory, structural-only detection, optional proven pages, full hashes, and summary recomputation.
- [ ] Run Task 1 tests to GREEN and refactor without adding source text to output.

## Task 2: Block Lifecycle And Producer Finalization

- [ ] Add RED tests proving:
  - exact duplicate candidates collapse with `candidate_occurrences`;
  - selected, usage-limited, and capacity-omitted dispositions differ;
  - maximal-overlap section mapping is deterministic;
  - evidence-stage sections use `selected_for_review`;
  - selected/rejected units finalize blocks as `card_selected`/`reviewed_no_card`;
  - omitted blocks remain `not_reviewed`;
  - section states and summary counts recompute after finalization;
  - unknown card IDs and malformed upstream manifests return unavailable rather than altering cards.
- [ ] Run Task 2 tests and verify missing-finalizer/incorrect-state RED.
- [ ] Add:

```python
def finalize_periodic_report_coverage_manifest(
    manifest: object, *, source_unit_decisions: list[dict], cards: list[dict],
    report_type: str = "", document_style: str = "",
) -> dict: ...
```

- [ ] Join only by exact `evidence_block_id`/`source_block_id`, derive producer dispositions, update section states, recompute summary, and validate.
- [ ] Run Task 2 tests to GREEN.

## Task 3: Evidence-Pack Integration

- [ ] Add RED integration tests proving:
  - every selected evidence block appears as `selected_for_producer` with the same `evidence_block_id`;
  - an over-cap candidate appears as `omitted_capacity`;
  - family reservation and the returned `blocks` list are identical to the pre-change selector result;
  - empty input includes an unavailable manifest.
- [ ] Run the focused integration tests and verify missing-manifest RED.
- [ ] In `build_periodic_report_evidence_pack()` retain `extracted_candidates`, `prioritized_candidates`, and `selected_blocks` as separate local lists, build and validate coverage, then trim and return selected blocks unchanged plus `coverage_manifest`.
- [ ] Update `_empty_pack()` with canonical unavailable coverage.
- [ ] Re-run the entire evidence-pack test module to GREEN.

## Task 4: Narrative Producer And Storage Integration

- [ ] Add RED producer tests proving:
  - coverage is finalized under `diagnostics["coverage_manifest"]`;
  - selected and rejected units produce exact parent-block states;
  - hand-built evidence packs without coverage emit `upstream_missing` but keep the same cards;
  - malformed coverage emits `upstream_invalid` but keeps the same cards.
- [ ] Run focused producer tests and verify missing diagnostic/finalization RED.
- [ ] Finalize the upstream manifest only after invariant handling and final card decisions. Do not change `cards`, `candidate_cards`, or existing diagnostics.
- [ ] Add or update one pack-store round-trip test proving the nested manifest survives write/load and integrity validation.
- [ ] Run producer, pack-store, material-pack, and synthesis-item suites to GREEN.

## Task 5: Acceptance And Compression

- [ ] Measure runtime numstat against `c406f77`; stop above net `+260`.
- [ ] Run the focused modules together.
- [ ] Run local-cache coverage against HKEX Black Sesame and at least one A-share cache available in the main repository, without network access or Knowledge writes.
- [ ] Inspect manifest counts, unresolved sections, page status, and absence of raw excerpts.
- [ ] Run report-quality/source-boundary suites, full offline pytest, `bash tools/ci_grep_gates.sh`, and `git diff --check`.
- [ ] Perform implementation self-review for false-complete states, cap behavior, card identity, storage bloat, and scope; fix any finding and rerun affected tests.
- [ ] Write Codex notes with RED/GREEN evidence, runtime numstat, local-cache observations, warnings, and next-batch implications.
- [ ] Commit only after all acceptance gates pass.

## Plan Self-Review

- Every design requirement maps to a specific RED test.
- The manifest owns no source selection or display behavior.
- Evidence and producer stages have distinct states.
- Existing pack storage persists diagnostics without a schema migration.
- Missing or malformed upstream coverage cannot change cards.
- No placeholders, report changes, LLM calls, or network work are required.
