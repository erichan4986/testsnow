# Report Terminal Citations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development and executing-plans task-by-task.

**Goal:** Keep inline citation markers in place, remove all section-local source lists, and place the unchanged
global citation appendix after risk and before the legal footer.

**Architecture:** `DeepAnalysisRenderer` remains the citation-content owner. `ReportAssemblySkill` detaches
only its exact terminal appendix and controls placement. `report_prose_quality.py` resolves 4.4 inline refs
against the terminal table so the existing duplicate-source warning survives the layout change.

**Tech Stack:** Python, pytest, existing Markdown renderers and deterministic report-quality checks.

---

## File Map

Runtime:

- `scripts/utils/reporter/sections/deep_analysis_renderer.py`: remove local source-list rendering and dead state.
- `scripts/utils/report_skills/assembly_skills.py`: detach, validate, and place the sole global appendix.
- `scripts/utils/report_prose_quality.py`: preserve 4.4 duplicate-source audit with terminal references.

Tests:

- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_assembly_skills.py`
- `tests/reporter/test_report_prose_quality.py`

Notes:

- `docs/agent_workflow/2026-07-23-report-terminal-citations-codex-notes.md`

## Task 1: Remove Section-Local Source Lists

- [x] Add renderer tests proving legacy synthesis, annual/broker memo, and curated external addendum retain
  inline `[^n]` markers and one global citation table but never render `本节引用来源`.
- [x] Run focused new tests and confirm RED because current legacy/addendum paths emit local lists.
- [x] Delete `_append_section_citations()`, all local-list call sites, local-only `used` accumulators,
  `include_section_citations` parameters, and the local-only `display_refs` return. Keep global citation
  merging, offsets, aliasing, visible filtering, and formatting unchanged.
- [x] Re-run `test_deep_analysis_renderer.py` until GREEN.

## Task 2: Move The Global Appendix In Assembly

- [x] Add assembly tests for:
  - exact body/appendix identity;
  - order `risk < citations < footer`;
  - no-citation output;
  - duplicate headings raising;
  - non-deep global heading raising;
  - residual local-list marker raising;
  - reserved executive-summary ref retained without renumbering.
- [x] Run new assembly tests and confirm RED because no detachment owner exists.
- [x] Add `_detach_global_citation_section(markdown)` using exact line-heading matches. Zero matches returns
  unchanged text plus an empty appendix; one match returns unchanged body/appendix slices; multiple matches
  raise `ValueError`.
- [x] In `_assemble_markdown()`, detach only the deep section, reject citation headings from other renderers,
  reject local-list markers, append the appendix after all renderers, then append the existing footer.
- [x] Re-run `test_assembly_skills.py` until GREEN.

## Task 3: Preserve The 4.4 Duplicate-Source Warning

- [x] Add prose tests proving:
  - two terminal refs with the same URL trigger `duplicate_4_4_citation_source`;
  - two no-URL global rows with the same normalized source/author/title trigger it;
  - repeated use of one ref does not trigger it;
  - an unrelated duplicate source not referenced by 4.4 does not trigger it;
  - historical local-list fixtures still work.
- [x] Run new prose tests and confirm RED because the checker currently reads only local 4.4 source rows.
- [x] Extend `_check_duplicate_4_4_citations()` with the full report text. Prefer historical local citation
  rows when present; otherwise resolve unique 4.4 refs from the exact global appendix. Normalize both plain
  and pipe/bold global row formats before URL or source/author/title identity counting.
- [x] Re-run `test_report_prose_quality.py` until GREEN.

## Task 4: Refactor And Verify

- [x] Run the three focused modules together.
- [x] Run report-quality and source-boundary suites, plus the Phase 2.3A technical focused suite.
- [x] Measure the three runtime files against the pre-task worktree state; stop above net `+60`.
- [x] Run the full offline suite, `bash tools/ci_grep_gates.sh`, and `git diff --check`.
- [x] Write notes with RED/GREEN evidence, runtime numstat, scope audit, and deferred report-generation gate.
- [x] Do not generate formal reports or commit; both code batches will be accepted together afterward.

## Plan Self-Review

- All citation-content decisions remain in `DeepAnalysisRenderer`.
- Assembly controls placement only and fails closed on competing owners.
- The prose checker preserves its warning rather than changing report acceptance semantics.
- Every modified behavior has a RED test before runtime edits.
- No technical, scoring, target, risk, recommendation, Chapter 4 content, source selection, or prompt owner is
  modified.
