# Chapter 4 Deterministic Editorial Projection Implementation Plan

> **For agentic workers:** execute the tasks in order, keeping every batch test-first.

**Goal:** Make formal-medium and formal-thin Chapter 4 render a deterministic, citation-safe editorial projection of complete material rows.

**Architecture:** `deep_analysis_material_snapshot.py` owns admission, row budgets, external projection choice, and 4.4 row selection. `deep_analysis_renderer.py` only formats already-selected rows. The quality gate validates visible Preview paragraph pairs, and Source Intake receives an independent display switch.

**Tech stack:** Python dataclasses, pytest, Markdown renderers.

---

### Task 1: MaterialSnapshot editorial selection

**Files:**
- Modify: `scripts/utils/deep_analysis_material_snapshot.py`
- Test: `tests/utils/test_deep_analysis_material_snapshot.py`

- [ ] Write failing tests for annual role budgets, unique portrait reservation, old `annual_selected_count` compatibility, broker attribution-first selection, first eligible external projection, exact external dedupe, and 4.4 title filtering before role priority.
- [ ] Run only those new tests. They must fail because the current snapshot returns uncapped annual/broker rows, combines external projections, and selects 4.4 rows before title filtering.
- [ ] Add `editorial_slot` to `MaterialRow`; apply annual ranking/budgets inside `select_annual_display_rows()` while preserving the admission/dedupe diagnostic meaning.
- [ ] Add shared exact external display-key and first-eligible-projection helpers. Each projection must be independently body/citation eligible and deduped before selection.
- [ ] Move broker display budgets into `build_chapter4_view_model()`: five non-risk rows with attribution diversity first, two risk rows, exact-body display dedupe.
- [ ] Add one exact informative-title predicate and choose 4.4 annual/broker/external rows only after it filters visible rows. Return no row for a layer without a valid title.
- [ ] Re-run the focused snapshot tests; they must pass.

### Task 2: Renderer projection and citations

**Files:**
- Modify: `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- Test: `tests/reporter/test_deep_analysis_renderer.py`

- [ ] Write failing formal-medium/formal-thin tests for paragraph-form 4.1, no local Chapter 4 source lists, attributed broker paragraphs without `机构共识`, all independent eligible external rows, and 4.4 label-and-condition-only output.
- [ ] Add a failing formal-thin fixture where the highest annual snapshot ref is hidden by budget; broker/external markers must retain the full-snapshot offsets.
- [ ] Run these tests and confirm they fail against the old slices, local citation lists, portrait re-selection, and body repetition.
- [ ] Render annual rows directly from selected `MaterialRow` values, honoring `editorial_slot="portrait"`; do not invoke a renderer-local annual selector.
- [ ] Format 4.2 as attributed institution paragraphs. Remove `_broker_consensus_sentence()` and only emit an optional `机构关注重点` block from non-generic selected titles.
- [ ] Render the selected external projection as standalone bold title plus ordinary cited paragraph; remove all external display slices. Keep formal-thin offsets based on the full snapshot already constructed by the entry path.
- [ ] Render 4.4 with at most three short layer/variable/citation/condition paragraphs. Do not repeat evidence bodies. Use the fixed fallback when no selected 4.4 row remains.
- [ ] Remove local `本节引用来源` lists only from the new formal-medium/formal-thin paths. Keep formal-rich legacy output unchanged.
- [ ] Re-run the focused renderer tests; they must pass.

### Task 3: Quality gate and Source Intake display switch

**Files:**
- Modify: `scripts/utils/report_quality.py`
- Modify: `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`
- Modify: `scripts/previews/periodic_report_fulltext_preview.py`
- Test: `tests/reporter/test_report_quality.py`
- Test: `tests/reporter/test_source_intake_evidence_renderer.py`
- Test: `tests/reporter/test_periodic_report_fulltext_preview_script.py`

- [ ] Write failing quality tests for every new-layout Preview title/paragraph pair: missing footnote, later-pair missing footnote, bullet/table/heading pseudo-paragraph, valid `[^10]`, legacy local-list output, and material-empty fallback.
- [ ] Write failing Source Intake tests for default hidden section, nested `render_section`, top-level true/false override precedence, and preview `--source-intake-section` restoration.
- [ ] Run the new tests and confirm they fail because the existing gate requires a local source list and the renderer always displays enabled Source Intake.
- [ ] Implement the pair scanner only inside the profile-aware 4.3 Preview body; preserve the legacy source-list branch.
- [ ] Add the display-only Source Intake gate; preview must pass its explicit top-level override without mutating material context.
- [ ] Re-run focused quality and Source Intake tests; they must pass.

### Task 4: Regression and budget verification

**Files:**
- Verify only: the files above and their tests

- [ ] Run `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/utils/test_deep_analysis_material_snapshot.py tests/reporter/test_deep_analysis_renderer.py tests/reporter/test_report_quality.py tests/reporter/test_source_intake_evidence_renderer.py tests/reporter/test_periodic_report_fulltext_preview_script.py -q -p no:cacheprovider`.
- [ ] Run `bash tools/ci_grep_gates.sh` and `git diff --check`.
- [ ] Measure runtime-only numstat for the five allowed runtime files. Stop if net runtime growth exceeds `+140`.
- [ ] Do not generate reports, access the network, touch data/knowledge/reports, commit, or push.
