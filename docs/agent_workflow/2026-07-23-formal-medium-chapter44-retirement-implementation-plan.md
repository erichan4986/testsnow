# Formal-Medium Chapter 4.4 Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the generic, non-evidentiary Chapter 4.4 projection from new `formal_medium` reports while preserving all material rows, citations, `formal_thin_external_rich`, and the sourced `formal_rich` legacy 4.4 addendum.

**Architecture:** Shrink the formal-medium `Chapter4ViewModel` to the three source-owned sections that carry actual material, then delete the renderer method that converted reused row titles into generic price-direction prose. The snapshot remains the full material store; only the display read-model and renderer projection become smaller.

**Tech Stack:** Python 3, frozen dataclasses, pytest, Markdown renderer, repository grep/quality gates.

---

## File Map

- Modify `scripts/utils/deep_analysis_material_snapshot.py`: remove formal-medium 4.4 admission and its three dedicated selectors.
- Modify `scripts/utils/reporter/sections/deep_analysis_renderer.py`: stop rendering formal-medium 4.4 and remove its fixed template method.
- Modify `tests/utils/test_deep_analysis_material_snapshot.py`: lock the three-section view-model contract and migrate mixed tests without losing 4.3/citation coverage.
- Modify `tests/reporter/test_deep_analysis_renderer.py`: verify the public formal-medium render path omits 4.4 while formal-thin and formal-rich retain their existing contracts.
- Do not modify quality checkers, profile routing, producers, canonical packs, scoring, targets, risk, technical analysis, recommendation, prompts, data, knowledge, or reports.

## Task 1: Make the View-Model Contract Fail First

**Files:**
- Modify: `tests/utils/test_deep_analysis_material_snapshot.py:266-306`
- Modify: `tests/utils/test_deep_analysis_material_snapshot.py:540-572`
- Modify: `tests/utils/test_deep_analysis_material_snapshot.py:970-1021`
- Modify: `tests/utils/test_deep_analysis_material_snapshot.py:1138-1166`
- Modify: `tests/utils/test_deep_analysis_material_snapshot.py:1235-1300`

- [ ] **Step 1: Migrate the narrative-filtering mixed test**

Rename `test_view_model_filters_hidden_narrative_arguments_and_keeps_price_path_rows_unchanged` to `test_view_model_filters_hidden_narrative_arguments_and_keeps_visible_citations` and replace its price-path assertion with visible-section invariants:

```python
    projected = with_memo.section("4.3").narratives[0]
    assert [part.argument_key for part in projected.parts] == ["visible"]
    assert projected.parts[0].relation == "first"
    assert with_memo.section("4.3").rows == without_memo.section("4.3").rows
    assert set(with_memo.citations) == {2}
```

- [ ] **Step 2: Preserve the owner-delta body assertion in 4.3**

Rename `test_view_model_projects_owner_equivalent_parts_without_changing_price_path_rows` to `test_view_model_projects_owner_delta_parts_without_rewriting_external_row_body`. Replace the 4.4 lookup with:

```python
    projected_row = view_model.section("4.3").rows[0]
    assert projected_row.body == duplicate + update
```

Keep the existing assertions that only `update` remains in the narrative and that the annual citation remains `(1,)`.

- [ ] **Step 3: Preserve rejected-external diagnostics without 4.4**

Rename `test_formal_medium_rejected_external_row_stays_out_of_4_3_and_4_4` to `test_formal_medium_rejected_external_row_stays_out_of_4_3`. Delete only this assertion:

```python
    assert all(row.source_layer != "external" for row in view_model.section("4.4").rows)
```

Keep the empty 4.3 assertion and exact rejection diagnostics assertion.

- [ ] **Step 4: Delete tests owned exclusively by the retired projection**

Delete these four complete tests; they specify no behavior used outside formal-medium 4.4:

```text
test_formal_medium_price_path_falls_back_to_cited_generic_broker_assumption
test_formal_medium_price_path_generic_broker_fallback_never_uses_risk_row
test_formal_medium_price_path_uses_strict_selected_role_priority
test_incomplete_selected_annual_rows_enter_price_path_after_complete_rows_are_exhausted
```

- [ ] **Step 5: Lock the three-section public view-model contract**

In `test_formal_medium_view_model_unifies_source_layers_and_visible_citations`, change the section expectation and preserve all layer/credit/eligibility assertions:

```python
    assert [section.section_id for section in view_model.sections] == ["4.1", "4.2", "4.3"]
    with pytest.raises(KeyError):
        view_model.section("4.4")
```

Remove the old `4.4` layer assertion. Compute the citation contract from both visible rows and narrative parts:

```python
    visible_refs = {
        ref
        for section in view_model.sections
        for row in section.rows
        for ref in row.citation_refs
    } | {
        ref
        for section in view_model.sections
        for narrative in section.narratives
        for part in narrative.parts
        for ref in part.citation_refs
    }
    assert visible_refs == set(view_model.citations)
```

- [ ] **Step 6: Run the RED contract tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_deep_analysis_material_snapshot.py::test_view_model_filters_hidden_narrative_arguments_and_keeps_visible_citations \
  tests/utils/test_deep_analysis_material_snapshot.py::test_view_model_projects_owner_delta_parts_without_rewriting_external_row_body \
  tests/utils/test_deep_analysis_material_snapshot.py::test_formal_medium_rejected_external_row_stays_out_of_4_3 \
  tests/utils/test_deep_analysis_material_snapshot.py::test_formal_medium_view_model_unifies_source_layers_and_visible_citations \
  -q -p no:cacheprovider
```

Expected: the first three migrated tests pass; the public section-contract test fails because runtime still exposes `4.4`.

## Task 2: Remove the View-Model Projection and Dead Selectors

**Files:**
- Modify: `scripts/utils/deep_analysis_material_snapshot.py:355-410`
- Modify: `scripts/utils/deep_analysis_material_snapshot.py:586-616`

- [ ] **Step 1: Remove formal-medium 4.4 construction**

Delete the `_select_price_path_rows(...)` call and build only these sections:

```python
    sections = (
        Chapter4Section("4.1", "官方材料确认：业务与财务基座", annual_rows),
        Chapter4Section("4.2", "机构观点与盈利假设", broker_rows),
        Chapter4Section(
            "4.3",
            "外部观察与待验证变量（Preview，不参与评分）",
            external_rows,
            "以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；不参与评分、风险评分或目标价。",
            external_narratives,
        ),
    )
```

- [ ] **Step 2: Remove the stale hidden-section diagnostic assumption**

Change:

```python
visible_rows_count=sum(len(section.rows) for section in sections[:3])
```

to:

```python
visible_rows_count=sum(len(section.rows) for section in sections)
```

- [ ] **Step 3: Delete dedicated price-path helpers**

Delete the complete definitions of:

```text
_select_price_path_rows
_select_price_row
_generic_broker_price_row
```

Do not delete `_NON_INFORMATIVE_VARIABLE_TITLES`, `is_informative_variable_title`, `MaterialRow.argument_complete`, or `dataclasses.replace`; they still have non-4.4 consumers.

- [ ] **Step 4: Run the snapshot suite GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_deep_analysis_material_snapshot.py \
  -q -p no:cacheprovider
```

Expected: all snapshot tests pass.

- [ ] **Step 5: Audit dead symbols**

Run:

```bash
rg -n "_select_price_path_rows|_select_price_row|_generic_broker_price_row|section\(\"4\.4\"\)" \
  scripts/utils/deep_analysis_material_snapshot.py \
  tests/utils/test_deep_analysis_material_snapshot.py
```

Expected: no matches.

## Task 3: Make the Public Renderer Contract Fail First

**Files:**
- Modify: `tests/reporter/test_deep_analysis_renderer.py`

- [ ] **Step 1: Add a public-render formal-medium fixture**

Add this test near the existing profile-routing renderer tests:

```python
def test_formal_medium_public_render_ends_after_external_variables():
    renderer = DeepAnalysisRenderer()
    rows = (
        MaterialRow(
            "annual:1", "主营业务", "annual", "formal_fact", (1,), ("annual:1",),
            title="主营业务", body="公司主营业务为芯片设计。",
            render_role="business_structure", source_credit="official",
        ),
        MaterialRow(
            "broker:1", "增长假设", "broker", "professional_analysis", (2,), ("broker:1",),
            title="增长假设", body="研报预计产品放量。", render_role="broker_assumption",
            attribution="测试证券", source_credit="professional",
        ),
        MaterialRow(
            "external:1", "验证变量", "external", "external_observation", (3,), ("external:1",),
            title="客户验证", body="外部材料称客户验证节奏仍需观察。",
            render_role="external_variable", source_credit="external_low_credit",
        ),
    )
    snapshot = MaterialSnapshot(
        "deep_analysis_material_snapshot.v1", rows,
        {1: {"source": "公司年报"}, 2: {"source": "券商研报"}, 3: {"source": "外部观察"}}, {},
    )
    view_model = build_chapter4_view_model(snapshot, "formal_medium")
    result = renderer.render({
        "stock_name": "测试股",
        "deep_analysis_evidence_profile": {"profile": "formal_medium"},
        "synthesis": {"industry_logic": "正式材料基线。", "citations": {}},
        "core_facts": [],
        "deep_analysis_material_snapshot": snapshot,
        "chapter4_view_model": view_model,
    })

    assert "### 4.1 官方材料确认：业务与财务基座" in result
    assert "### 4.2 机构观点与盈利假设" in result
    assert "### 4.3 外部观察与待验证变量（Preview，不参与评分）" in result
    assert "### 4.4" not in result
    assert "官方确认：" not in result
    assert "机构假设：" not in result
    assert "外部待验证：" not in result
    assert "若机构关于需求、产品放量或盈利弹性的假设兑现" not in result
```

Also import `MaterialSnapshot` from `deep_analysis_material_snapshot` at the top of the test file.

- [ ] **Step 2: Strengthen formal-thin absence checks**

In both existing citation-offset tests:

```text
test_formal_thin_v3_external_evidence_keeps_full_snapshot_citation_offset
test_formal_thin_owner_filter_keeps_full_snapshot_external_citation_offset
```

add:

```python
    assert "### 4.4" not in result
```

Do not alter their current citation-number assertions.

- [ ] **Step 3: Run the public renderer test RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_deep_analysis_renderer.py::test_formal_medium_public_render_ends_after_external_variables \
  -q -p no:cacheprovider
```

Expected: FAIL with `KeyError: '4.4'` because the view-model contract has already shrunk but the renderer still performs its stale 4.4 lookup.

## Task 4: Delete the Formal-Medium Renderer Template

**Files:**
- Modify: `scripts/utils/reporter/sections/deep_analysis_renderer.py:499-553`
- Modify: `scripts/utils/reporter/sections/deep_analysis_renderer.py:786-835`

- [ ] **Step 1: End formal-medium rendering after 4.3**

Delete the block that appends the 4.4 heading, looks up `view_model.section("4.4")`, and calls `_formal_medium_price_path_section(...)`. Keep `return lines` immediately after the 4.3 fallback block.

- [ ] **Step 2: Delete the fixed-template method**

Delete the complete `DeepAnalysisRenderer._formal_medium_price_path_section` method. Do not modify `_formal_thin_external_rich_body` or `_curated_external_addendum`.

- [ ] **Step 3: Run renderer regression tests GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_deep_analysis_renderer.py \
  -q -p no:cacheprovider
```

Expected: all renderer tests pass, including the unchanged formal-rich legacy 4.4 fixtures and formal-thin citation-offset fixtures.

- [ ] **Step 4: Audit runtime ownership**

Run:

```bash
rg -n "_formal_medium_price_path_section|4\.4 上行 / 下行条件与股价推演|若机构关于需求、产品放量或盈利弹性的假设兑现" \
  scripts/utils/deep_analysis_material_snapshot.py \
  scripts/utils/reporter/sections/deep_analysis_renderer.py
```

Expected: no matches. A separate search for `4.4 外部观点与待验证变量（Preview）` must still find the formal-rich legacy addendum.

## Task 5: Verify Boundaries, Deletion Budget, and Offline Regressions

**Files:**
- No runtime edits unless a failure directly violates this plan.

- [ ] **Step 1: Run focused contracts together**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_deep_analysis_material_snapshot.py \
  tests/reporter/test_deep_analysis_renderer.py \
  -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 2: Run report-quality boundaries**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_report_quality.py \
  tests/reporter/test_report_source_boundary.py \
  tests/reporter/test_report_prose_quality.py \
  -q -p no:cacheprovider
```

Expected: PASS. Historical parser fixtures that contain old formal-medium 4.4 output remain valid.

- [ ] **Step 3: Run the full offline suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```

Expected: PASS with only existing skips.

- [ ] **Step 4: Run static gates**

Run:

```bash
bash tools/ci_grep_gates.sh
git diff --check
```

Expected: all grep gates pass and `git diff --check` emits no output.

- [ ] **Step 5: Confirm this remains a deletion batch**

Run:

```bash
git diff --numstat -- \
  scripts/utils/deep_analysis_material_snapshot.py \
  scripts/utils/reporter/sections/deep_analysis_renderer.py
```

Expected: runtime net change is negative, approximately `-85` to `-105` lines. Stop if runtime is net-positive or if any new prose-inference path was added.

- [ ] **Step 6: Record implementation results without generating reports**

Write `docs/agent_workflow/2026-07-23-formal-medium-chapter44-retirement-implementation-notes.md` with:

```text
- modified files
- RED/GREEN evidence
- focused/downstream/full/CI results
- runtime numstat
- formal-medium/formal-thin/formal-rich contract results
- blocker/warning/deviation
- fresh-report acceptance required: yes
```

Do not generate or modify `reports/`, `data/`, or `knowledge/` during implementation. Fresh Zhongji/Fudan report reruns are a separate read-only acceptance step after the code diff passes all offline gates.

## Stop Conditions

Stop and return to design if any of these occurs:

- formal-rich legacy 4.4 must change to make tests pass;
- formal-thin citation offsets must change;
- full snapshot rows or citations must be removed;
- implementation requires a prose inference engine or structured trigger synthesis;
- runtime change becomes net-positive;
- any runtime file outside the two-file allowlist must change.
