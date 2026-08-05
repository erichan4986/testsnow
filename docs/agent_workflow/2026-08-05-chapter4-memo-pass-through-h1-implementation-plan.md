# Chapter 4 Memo Pass-Through H1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:test-driven-development` and execute each task in order.

**Goal:** Remove annual/broker memo intermediate schemas and project canonical
formal materials directly into the Chapter 4 snapshot without visible behavior
or profile changes.

**Architecture:** `deep_analysis_material_snapshot.py` becomes the single
formal preparation, status, row, and citation owner. `SynthesisSkill` loads
broker items once and consumes only the projection diagnostics for profile and
coverage routing.

**Tech Stack:** Python dataclasses, pytest, existing SkillContext and
MaterialSnapshot contracts.

---

## Baseline And Scope

Baseline: `e504cb9`.

Runtime files:

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/report_skills/synthesis_skills.py`

Test files:

- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/utils/test_external_v4_snapshot.py`
- `tests/test_runtime_hygiene.py`

Runtime net reduction must be at least 110 lines. Stop before H2 behavior or any
file outside the locked scope is required.

### Task 1: Direct Formal Projection Contract

- [ ] Add failing tests importing
  `build_chapter4_formal_material_diagnostics` and supplying annual
  packs/current cards plus broker `SynthesisItem` fixtures.
- [ ] Assert current-card precedence, canonical family/completeness, annual
  cleanup, exact dedupe, A/HK text, zero fact filtering, status, broker
  usable/projected separation, source-id hash, grouped mixed-order refs, and
  external offset.
- [ ] Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m pytest \
    tests/utils/test_deep_analysis_material_snapshot.py -q -p no:cacheprovider
  ```

  Expected: RED because the diagnostics API/direct ctx projection does not
  exist and snapshot still reads memo ctx keys.
- [ ] Implement private annual/broker projections, keyed citation allocation,
  formal diagnostics, and direct rows in
  `deep_analysis_material_snapshot.py`.
- [ ] Re-run the focused file and reach GREEN.

### Task 2: Synthesis Orchestration And Profile Compatibility

- [ ] Replace memo-builder tests with failing tests for preloaded broker items,
  one loader call when absent, stored empty list, unchanged profile matrix,
  unchanged coverage keys/counts, and no memo ctx writes.
- [ ] Run targeted new tests and confirm RED against memo-based orchestration.
- [ ] Import and call `build_chapter4_formal_material_diagnostics` in
  `SynthesisSkill.run()`.
- [ ] Preserve preloaded broker items; otherwise load once after refresh and
  store the result.
- [ ] Convert profile and coverage to diagnostics-only reads.
- [ ] Make freshness and optional broker display consume the stored item list.
- [ ] Delete `_annual_narrative_cards`, annual memo cleanup/guard helpers, and
  both memo builders.
- [ ] Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m pytest \
    tests/reporter/test_synthesis_skills.py \
    tests/utils/test_deep_analysis_material_snapshot.py \
    -q -p no:cacheprovider
  ```

  Expected: GREEN.

### Task 3: Consumer Fixture And Hygiene Migration

- [ ] Add RED hygiene assertions forbidding runtime memo builders, schema
  strings, and raw memo ctx reads.
- [ ] Replace renderer/external snapshot memo fixtures with canonical packs and
  broker items or prebuilt snapshots.
- [ ] Preserve single-institution disclosure and full-snapshot citation offset.
- [ ] Run:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m pytest \
    tests/reporter/test_deep_analysis_renderer.py \
    tests/utils/test_external_v4_snapshot.py \
    tests/test_runtime_hygiene.py \
    -q -p no:cacheprovider
  ```

  Expected: GREEN and no runtime memo references except compatibility output
  field names.

### Task 4: Refactor And Runtime Budget

- [ ] Remove now-unused imports and duplicate local transforms.
- [ ] Run all focused tests from Tasks 1-3.
- [ ] Measure:

  ```bash
  git diff --numstat e504cb9 -- \
    scripts/utils/deep_analysis_material_snapshot.py \
    scripts/utils/report_skills/synthesis_skills.py
  ```

- [ ] Stop if runtime net reduction is below 110 lines or if formal eligibility
  exists in more than one owner.

### Task 5: Verification And Notes

- [ ] Run reporter downstream tests and then full `pytest`.
- [ ] Run `bash tools/ci_grep_gates.sh` and `git diff --check`.
- [ ] Run deterministic local three-stock projection comparisons for 中际旭创,
  复旦微电, and 黑芝麻智能 without network/LLM/report generation. Compare
  profile, row order, visible text, source identities, and citation count to
  frozen expected fixtures.
- [ ] Write
  `docs/agent_workflow/2026-08-05-chapter4-memo-pass-through-h1-implementation-notes.md`
  with RED/GREEN evidence, requirement-test matrix, runtime numstat, test
  results, comparison results, blocker/warning/deviation, and acceptance.
- [ ] Do not commit until final Codex review accepts the real diff.
