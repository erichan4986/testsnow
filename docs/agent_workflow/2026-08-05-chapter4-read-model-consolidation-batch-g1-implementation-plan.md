# Chapter 4 Read-Model Consolidation Batch G1 Implementation Plan

> **For agentic workers:** Implement inline with strict RED/GREEN checkpoints.

**Goal:** Make the material snapshot selector the only owner of annual Chapter
4 admission and portrait selection, while preserving broker output and citation
identity and removing duplicate renderer plumbing.

**Architecture:** Annual `MaterialRow` objects are admitted and assigned an
editorial slot in `deep_analysis_material_snapshot.py`; the renderer only
groups and formats those selected rows. The formal-thin broker memo path and
full-snapshot citation offset formula remain unchanged.

**Tech Stack:** Python 3, dataclasses, pytest.

---

### Task 1: Lock Broker And Citation Compatibility

**Files:**
- Test: `tests/reporter/test_deep_analysis_renderer.py`

- [ ] Add a characterization test covering broker section, forecast, risk,
  single-institution disclosure, and references in formal-thin output.
- [ ] Run that test and confirm it is green before runtime changes.
- [ ] Retain existing full-snapshot citation-offset regression tests.

### Task 2: Move Suspicious Zero Admission To Snapshot

**Files:**
- Modify: `scripts/utils/deep_analysis_material_snapshot.py`
- Test: `tests/utils/test_deep_analysis_material_snapshot.py`

- [ ] Add a failing selector test proving a suspicious zero `formal_fact` is
  rejected while a `formal_explanation` containing the same literal remains.
- [ ] Assert diagnostic reason `suspicious_zero_financial_fact`.
- [ ] Run the test and verify the expected failure.
- [ ] Add the narrow admission guard and verify the test turns green.

### Task 3: Render Selected Annual Rows Directly

**Files:**
- Modify: `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- Test: `tests/reporter/test_deep_analysis_renderer.py`

- [ ] Add a failing public-contract test proving rows without
  `editorial_slot="portrait"` do not receive a renderer-selected portrait.
- [ ] Add/retain a test proving the selected portrait renders once.
- [ ] Replace memo-shaped annual projection with direct `MaterialRow` grouping.
- [ ] Delete renderer annual admission, grouping, and portrait compatibility
  helpers after the focused tests pass.

### Task 4: Remove Deterministic Dead Plumbing

**Files:**
- Modify: `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- Test: `tests/reporter/test_deep_analysis_renderer.py`
- Test: `tests/test_runtime_hygiene.py`

- [ ] Update direct formatter calls for signatures without unused citation
  maps.
- [ ] Remove `annual_material_citations` and the unused thin-body curated
  display argument.
- [ ] Inline the single snapshot wrapper call and delete `_truncate_title()`.
- [ ] Add hygiene assertions for deleted renderer compatibility methods.

### Task 5: Verification And Runtime Ledger

**Files:**
- Create: `docs/agent_workflow/2026-08-05-chapter4-read-model-consolidation-batch-g1-implementation-notes.md`

- [ ] Run the three focused test files.
- [ ] Run `tests/reporter`, then the complete suite.
- [ ] Run CI grep gates and `git diff --check`.
- [ ] Run the offline black-sesame smoke command.
- [ ] Measure runtime numstat for the two runtime files and stop if net
  reduction is below 65 lines.
- [ ] Record changed files, RED/GREEN evidence, tests, citation regression,
  runtime ledger, blocker/warning/deviation, and untouched dirty files.
