# Chapter 4 Material V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development and executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `formal_medium` Chapter 4 render from one immutable MaterialRow/ViewModel contract instead of reading annual, broker, and external payloads throughout the renderer.

**Architecture:** Extend `deep_analysis_material_snapshot.py` rather than introduce a parallel row schema. Rename the canonical row type to `MaterialRow` while keeping `EvidenceRow` as a compatibility alias. Add a deterministic `Chapter4ViewModel` builder that owns source-layer admission, role classification, attribution, and visible citations. Only the `formal_medium` renderer path consumes the view-model in this batch.

**Tech Stack:** Python dataclasses, pytest, existing report renderer and quality gates.

---

### Task 1: MaterialRow And Formal-Medium ViewModel Contract

**Files:**

- Modify: `tests/utils/test_deep_analysis_material_snapshot.py`
- Modify: `scripts/utils/deep_analysis_material_snapshot.py`

- [ ] **Step 1: Write failing contract tests**

Add tests that import `MaterialRow`, `Chapter4ViewModel`, and
`build_chapter4_view_model`, then assert:

```python
snapshot = build_deep_analysis_material_snapshot(ctx)
view_model = build_chapter4_view_model(snapshot, {"profile": "formal_medium"})

assert all(isinstance(row, MaterialRow) for row in snapshot.rows)
assert [section.section_id for section in view_model.sections] == ["4.1", "4.2", "4.3", "4.4"]
assert {row.source_layer for row in view_model.section("4.1").rows} == {"annual"}
assert {row.source_layer for row in view_model.section("4.2").rows} == {"broker"}
assert {row.source_layer for row in view_model.section("4.3").rows} == {"external"}
assert all(row.attribution for row in view_model.section("4.2").rows)
assert all(not row.scoring_eligible and not row.risk_score_eligible for row in view_model.section("4.3").rows)
```

Also assert that `view_model.citations` contains exactly refs used by admitted
rows and that building it does not mutate the input context.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/utils/test_deep_analysis_material_snapshot.py -q -p no:cacheprovider
```

Expected: import failure for the new MaterialRow/ViewModel API.

- [ ] **Step 3: Implement the minimal contract**

In `deep_analysis_material_snapshot.py`:

- define `MaterialRow` with the current `EvidenceRow` fields plus `title`,
  `body`, `render_role`, `attribution`, `source_credit`, and immutable
  diagnostics;
- set `EvidenceRow = MaterialRow` for compatibility;
- define immutable `Chapter4Section` and `Chapter4ViewModel`;
- populate normalized row metadata when adapting annual, broker, and external
  payloads;
- implement `build_chapter4_view_model(snapshot, profile)` for
  `formal_medium`;
- derive visible citations only from rows admitted to sections;
- keep all rows deep-analysis-only and non-scoring/non-risk-scoring.

- [ ] **Step 4: Run the contract tests and verify GREEN**

Run the Task 1 command. Expected: all tests pass.

### Task 2: Formal-Medium Renderer Isolation

**Files:**

- Modify: `tests/reporter/test_deep_analysis_renderer.py`
- Modify: `scripts/utils/reporter/sections/deep_analysis_renderer.py`

- [ ] **Step 1: Write failing renderer isolation tests**

Add a test that prebuilds a `Chapter4ViewModel`, stores it under
`ctx["chapter4_view_model"]`, then replaces the raw annual/broker/external
payloads with conflicting text. Assert the report renders only view-model text.

Add regression assertions that:

- `formal_rich` still renders legacy headings;
- `formal_thin_external_rich` still renders its current three-section body;
- `formal_medium` visible refs all resolve through the view-model citation map.

- [ ] **Step 2: Run focused renderer tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_deep_analysis_renderer.py \
  -q -p no:cacheprovider
```

Expected: the isolation test fails because the renderer still reads raw memo
and external display payloads.

- [ ] **Step 3: Refactor only the formal-medium path**

Change the renderer so that:

```python
snapshot = ctx.get("deep_analysis_material_snapshot") or build_deep_analysis_material_snapshot(ctx)
view_model = ctx.get("chapter4_view_model") or build_chapter4_view_model(snapshot, profile)
```

is evaluated once for `formal_medium`. Pass the view-model into
`_formal_medium_source_layer_body()` and make its 4.1-4.4 helpers consume only
`MaterialRow` sequences and `view_model.citations`.

The renderer may format and compact row text, but must not read
`annual_report_memo`, `broker_research_memo`, or `deep_analysis_display` inside
the `formal_medium` branch.

Use one citation offset for the whole Chapter 4 view-model after baseline
citations. Do not merge annual, broker, and external citation maps separately.

- [ ] **Step 4: Remove superseded formal-medium-only plumbing**

Remove parameters and branches that exist only to pass separate annual,
broker, and external offsets into `formal_medium`. Keep compatibility helpers
still used by `formal_thin_external_rich` or `formal_rich`.

- [ ] **Step 5: Run focused renderer tests and verify GREEN**

Run the Task 2 command. Expected: all renderer tests pass.

### Task 3: Contract And Source-Boundary Regression

**Files:**

- Modify only if a test exposes a real contract gap:
  `tests/reporter/test_report_quality.py`
- Modify only if a test exposes a real contract gap:
  `tests/reporter/test_report_source_boundary.py`

- [ ] **Step 1: Run quality and source-boundary tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_report_quality.py \
  tests/reporter/test_report_source_boundary.py \
  -q -p no:cacheprovider
```

Expected: pass without changing quality APIs. If a failure reveals a source
boundary regression, first add the smallest failing test and then fix the
material/view-model layer rather than adding another Markdown exception.

- [ ] **Step 2: Verify forbidden paths are untouched**

Inspect the diff and confirm there are no changes to scoring, target price,
risk scoring, technical analysis, recommendation, collection, or LLM prompt
files.

### Task 4: Full Focused Verification And Review

**Files:**

- No runtime changes unless verification finds a regression.

- [ ] **Step 1: Run the complete focused suite**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_deep_analysis_material_snapshot.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_report_quality.py \
  tests/reporter/test_report_source_boundary.py \
  tests/reporter/test_synthesis_skills.py \
  -q -p no:cacheprovider
```

- [ ] **Step 2: Run repository gates**

```bash
bash tools/ci_grep_gates.sh
git diff --check
```

- [ ] **Step 3: Audit direct reads**

Run:

```bash
rg -n "annual_report_memo|broker_research_memo|deep_analysis_display" \
  scripts/utils/reporter/sections/deep_analysis_renderer.py
```

Expected: direct reads may remain only in non-formal-medium compatibility
paths and the one material-builder call site must be evident from code flow.

- [ ] **Step 4: Review scope and complexity**

Confirm:

- no report rerun was required for this internal-contract batch;
- formal-medium renderer output remains covered by existing golden/structural
  tests;
- no new LLM memo or prompt was added;
- no unrelated dirty files were staged or modified;
- runtime growth is limited to the contract/view-model boundary and is offset
  by removal of superseded formal-medium plumbing where safe.
