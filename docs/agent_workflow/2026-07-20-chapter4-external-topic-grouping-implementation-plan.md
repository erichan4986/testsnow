# Chapter 4 External Topic Grouping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Group Chapter 4.3 external observations by topic inside strict target and peer/industry scopes.

**Architecture:** Keep the existing MaterialRow selection and citation allocation unchanged. Add one stable renderer grouping helper and render each scope/topic heading once while attaching existing row references to every paragraph.

**Tech Stack:** Python, Markdown, pytest.

---

### Task 1: Lock The Grouping Contract

**Files:**
- Test: `tests/reporter/test_deep_analysis_renderer.py`

- [ ] Add a failing test with interleaved target technology/financial rows and a
  peer technology row.
- [ ] Assert canonical topic order, one target technology heading, a second peer
  technology heading after the peer disclaimer, stable row order, and complete
  inline citations.
- [ ] Run the focused test and confirm RED on repeated/interleaved headings.

### Task 2: Implement Stable Scope And Topic Grouping

**Files:**
- Modify: `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- Test: `tests/reporter/test_deep_analysis_renderer.py`

- [ ] Add a canonical display-title order and a stable grouping helper.
- [ ] Replace per-row heading/framing emission in
  `_formal_medium_external_variable_map()` with scope-level framing and grouped
  row projection.
- [ ] Keep existing paragraph citation attachment and evidence-status branches.
- [ ] Run focused renderer, source-boundary, report-quality, and prose tests.

### Task 3: Verify Reports Without Regenerating Sources

- [ ] Run the full test suite, CI grep gates, and `git diff --check`.
- [ ] Regenerate the two existing reports only after code-level gates are green.
- [ ] Confirm 4.3 groups are contiguous, all visible references resolve, and no
  target/peer scope crossing occurs.
