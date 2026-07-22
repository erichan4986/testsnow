# Chapter 4 Sentence-Level Owner Delta Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hide only owner-equivalent target narrative units from Chapter 4.3 while retaining newer, richer, negative, relational and peer/industry facts.

**Architecture:** `select_external_topic_narratives()` remains the sole display selector. It validates complete plan coverage, performs existing cross-source deduplication, then conservatively compares target parts with visible annual/broker owner units. An empty narrative is an intentional suppression sentinel; the renderer skips that topic without triggering raw-row fallback.

**Tech Stack:** Python standard library, immutable dataclasses, pytest.

---

## File Map

| File | Responsibility |
|---|---|
| `scripts/utils/deep_analysis_material_snapshot.py` | owner fact comparison and narrative projection |
| `scripts/utils/reporter/sections/deep_analysis_renderer.py` | profile wiring and empty-sentinel rendering |
| `tests/utils/test_deep_analysis_material_snapshot.py` | equivalence, preservation, coverage and scope contracts |
| `tests/reporter/test_deep_analysis_renderer.py` | fallback suppression and formal-thin citation-offset contracts |

## Task 1: Conservative Owner Equivalence

**Files:**

- Modify: `tests/utils/test_deep_analysis_material_snapshot.py`
- Modify: `scripts/utils/deep_analysis_material_snapshot.py`

- [ ] Add a failing test where one target narrative contains an exact owner-equivalent part and a new-period part. Assert the equivalent part is removed and the 2026H1 part remains.
- [ ] Add failing table-driven cases proving these parts remain: same number/different metric, same product/new stage, different polarity, new partner relation and richer external text.
- [ ] Run the new tests and confirm they fail because `select_external_topic_narratives()` does not accept `owner_rows`.
- [ ] Add private helpers for owner-unit splitting, metric/time/polarity/relation protection and conservative exact/containment/high-similarity comparison.
- [ ] Refactor the existing financial metric lookup into one shared helper used by both external-source deduplication and owner comparison.
- [ ] Run the Task 1 tests and the full snapshot test file; confirm GREEN.

## Task 2: Projection Scope, Coverage and Empty Sentinel

**Files:**

- Modify: `tests/utils/test_deep_analysis_material_snapshot.py`
- Modify: `scripts/utils/deep_analysis_material_snapshot.py`

- [ ] Add a failing test proving an all-equivalent target topic returns a validated `ExternalTopicNarrative(parts=())` sentinel instead of disappearing.
- [ ] Add a failing peer/industry test proving owner comparison is bypassed.
- [ ] Keep the existing incomplete-plan test and assert filtering cannot make incomplete coverage valid.
- [ ] Extend `select_external_topic_narratives(narratives, rows, owner_rows=())`: validate exact coverage first, dedupe sources second, filter only target parts third, and retain empty sentinels.
- [ ] Pass `(*annual_rows, *broker_rows)` from `build_chapter4_view_model()` without changing the original external rows used by `_select_price_path_rows()`.
- [ ] Run snapshot tests and confirm GREEN.

## Task 3: Renderer Fallback and Formal-Thin Offset

**Files:**

- Modify: `tests/reporter/test_deep_analysis_renderer.py`
- Modify: `scripts/utils/reporter/sections/deep_analysis_renderer.py`

- [ ] Add a failing renderer test with an empty narrative sentinel and matching verified row. Assert no topic heading, no row text and no raw fallback are emitted.
- [ ] Extend the existing formal-thin offset fixture with two external refs: hide the earlier owner-equivalent ref and retain the later new-period ref. Assert the later citation keeps its full-snapshot number and the hidden citation definition is absent.
- [ ] Run both tests and confirm RED.
- [ ] Pass the existing formal-thin annual/broker owner collection into `select_external_topic_narratives()`.
- [ ] Resolve a matching narrative before writing a topic heading; skip an empty sentinel, render a non-empty narrative and fallback only when no narrative object exists.
- [ ] Run renderer tests and confirm GREEN.

## Task 4: Refactor and Verification

**Files:**

- Modify only the four files above if cleanup is needed.

- [ ] Remove duplicated normalization/metric parsing introduced during GREEN while preserving behavior.
- [ ] Measure runtime numstat from `cc254a8`; target net `+70`, hard stop `+100` across the two runtime files.
- [ ] Run focused tests:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_deep_analysis_material_snapshot.py \
  tests/reporter/test_deep_analysis_renderer.py -q -p no:cacheprovider
```

- [ ] Run downstream quality/source/prose tests.
- [ ] Run the default offline full suite.
- [ ] Run `bash tools/ci_grep_gates.sh` and `git diff --check`.
- [ ] Write implementation notes with RED/GREEN evidence, runtime numstat, requirement-test matrix and any deviations.

## Stop Conditions

- Runtime net increase exceeds `+100` lines.
- A change is required outside the two runtime and two test files, except workflow notes.
- Any canonical pack, producer, taxonomy, quality gate, scoring, technical, target, risk, recommendation or LLM behavior would need to change.
- Formal-thin citation numbering, 4.4 material selection or target/peer partition changes.
