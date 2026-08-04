# External Producer v4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Replace the v3/v3.1 external-material pipeline with a clean v4 source-document, scope-resolution and pack path while preserving the report display envelope.

**Architecture:** Source input becomes immutable paragraph-preserving `ExternalSourceDocument` records. Exact units and deterministic scope are derived once, then v4 cards, ID-only selection and an ID-only narrative plan are built from those units. The report consumes a stable display envelope through the existing `MaterialSnapshot` adapter.

**Tech Stack:** Python standard library, existing pytest suite, JSON packs.

---

## Baseline

- Runtime baseline: current dirty `1dbcdc4` worktree, recorded with `git diff --numstat 1dbcdc4 -- scripts/utils` before Batch A.
- Existing focused suite: `176 passed`.
- Do not touch scoring, target price, technical analysis, report recommendations, source providers, data, reports or canonical pack JSON until Batch C.
- No report-time LLM call and no v3/v3.1 compatibility reader.

## File Map

| File | Responsibility |
|---|---|
| `scripts/utils/external_source_document.py` | canonical document/block creation and validation |
| `scripts/utils/external_evidence.py` | exact unitization, taxonomy and deterministic admission |
| `scripts/utils/external_scope.py` | target/peer/industry provenance and validation |
| `scripts/utils/external_pack.py` | v4 cards, selection contract, reader/writer, citations |
| `scripts/utils/external_narrative_plan.py` | ID-only narrative-plan validation and fallback ordering |
| `scripts/utils/curated_external_full_body_viewpoint_claims.py` | thin offline orchestration and sole LLM boundary |
| `scripts/utils/curated_external_display.py` | stable display envelope adapter |
| `scripts/utils/deep_analysis_material_snapshot.py` | v4 envelope-to-view-model adapter |

## Task 1: Canonical Source Documents

**Files:**

- Create: `scripts/utils/external_source_document.py`
- Create: `tests/utils/test_external_source_document.py`
- Modify: `scripts/utils/curated_external_full_body_viewpoint_claims.py`
- Modify: `tests/utils/test_curated_external_full_body_viewpoint_claims.py`

- [ ] Write failing tests:

```python
def test_document_preserves_paragraph_blocks_and_exact_offsets():
    document = build_external_source_document(_packet("标题\n\n测试股表示订单增长。\n\n行业供给仍紧张。"))
    assert [block["text"] for block in document["blocks"]] == ["标题", "测试股表示订单增长。", "行业供给仍紧张。"]
    assert document["blocks"][1]["start"] < document["blocks"][1]["end"]


def test_comparative_one_block_document_fails_boundary_quality():
    document = build_external_source_document(_packet("测试股与同业对比：" + "内容" * 700))
    assert document["boundary_status"] == "scope_input_degraded"
```

- [ ] Verify RED using the two tests above.
- [ ] Implement `build_external_source_document()`, `validate_external_source_document()` and source packet conversion.
- [ ] Verify GREEN with `test_external_source_document.py` and the existing full-body tests.

## Task 2: Exact Units, Taxonomy and Scope Resolver

**Files:**

- Create: `scripts/utils/external_evidence.py`
- Create: `scripts/utils/external_scope.py`
- Create: `tests/utils/test_external_evidence.py`
- Create: `tests/utils/test_external_scope.py`

- [ ] Write failing scope tests:

```python
def test_target_centric_company_continuation_uses_document_anchor():
    units = resolve_scope(_target_document("测试股公告指出。\n\n公司已接到全年订单。"), "测试股")
    assert units[-1]["scope_provenance"]["origin"] == "target_document_context"


def test_industry_sentence_does_not_inherit_target_owner():
    units = resolve_scope(_target_document("测试股订单增长。\n\n2027年行业仍面临产能紧张。"), "测试股")
    assert units[-1]["scope_provenance"]["origin"] == "industry_context"


def test_comparative_block_returns_to_primary_owner_after_inline_contrast():
    units = resolve_scope(_comparative_document(), "测试股")
    assert [unit["scope_provenance"]["origin"] for unit in units] == [
        "explicit_peer", "explicit_target", "explicit_peer",
    ]


def test_negative_and_constraint_conclusions_are_argument_complete():
    assert argument_status("测试股表示不存在故意压低股价。") == "admitted"
    assert argument_status("公司表示上游设备采购没有明显瓶颈。") == "admitted"
```

- [ ] Verify RED.
- [ ] Implement block-aware unitization, one taxonomy owner, deterministic document-local entity inventory and provenance reconstruction.
- [ ] Verify GREEN and add forged offset/provenance rejection tests.

## Task 3: v4 Pack and ID-only Selection

**Files:**

- Create: `scripts/utils/external_pack.py`
- Create: `tests/utils/test_external_pack.py`
- Modify: `scripts/utils/curated_external_full_body_viewpoint_claims.py`
- Modify: `tests/utils/test_curated_external_full_body_viewpoint_claims.py`

- [ ] Write failing pack tests:

```python
def test_pack_embeds_documents_and_rejects_forged_unit_offset():
    pack = build_external_argument_pack_v4(...)
    assert pack["schema_version"] == "curated_external_argument_pack.v4"
    assert read_external_argument_pack_v4(pack)["status"] == "ok"
    pack["cards"][0]["evidence_units"][0]["end"] += 1
    assert read_external_argument_pack_v4(pack)["status"] == "invalid"


def test_one_unit_has_one_card_owner_even_when_multiple_families_match():
    pack = build_external_argument_pack_v4(...)
    ids = [unit["unit_id"] for card in pack["cards"] for unit in card["evidence_units"]]
    assert len(ids) == len(set(ids))
```

- [ ] Verify RED.
- [ ] Implement v4 cards, explicit target/peer relation grouping, source/block bounded selection batches and strict reader/writer.
- [ ] Preserve citations and existing display-envelope fields at the adapter boundary.
- [ ] Verify GREEN.

## Task 4: ID-only Narrative Plan and Display Adapter

**Files:**

- Create: `scripts/utils/external_narrative_plan.py`
- Create: `tests/utils/test_external_narrative_plan.py`
- Modify: `scripts/utils/curated_external_display.py`
- Modify: `scripts/utils/deep_analysis_material_snapshot.py`
- Modify: `tests/utils/test_curated_external_display.py`
- Modify: `tests/utils/test_deep_analysis_material_snapshot.py`

- [ ] Write failing tests:

```python
def test_narrative_plan_rejects_prose_and_relation_fields():
    assert validate_narrative_plan(pack, {"groups": [{"text": "新结论"}]})["status"] == "invalid"


def test_v4_display_keeps_legacy_envelope_keys_without_projection_accessor():
    result = build_curated_external_argument_display(path, expected_stock_name="测试股")
    assert {"citations", "_curated_external_argument_cards", "_curated_external_topic_narratives"} <= set(result["display"])
```

- [ ] Verify RED.
- [ ] Implement ID-only paragraph order, neutral connector fallback and v4 display envelope adapter.
- [ ] Replace snapshot use of `external_display_text()` with validated canonical unit text.
- [ ] Verify GREEN with renderer regression tests.

## Task 5: Cutover and Deletion

**Files:**

- Delete: `scripts/utils/curated_external_display_projection.py`
- Delete: `scripts/utils/curated_external_topic_narrative.py`
- Delete or replace: `scripts/utils/curated_external_argument_cards.py`
- Delete corresponding obsolete tests after public-contract replacements are green.
- Modify: callers/imports in `scripts/utils/report_skills/synthesis_skills.py`, `scripts/utils/evidence_freshness.py`, `scripts/utils/reporter/sections/deep_analysis_renderer.py` only if runtime search proves an import remains.

- [ ] Add a runtime call-graph test that rejects v3/v3.1 schema literals and imports of deleted modules.
- [ ] Run RED to prove legacy references exist.
- [ ] Remove legacy projection/narrative/reader paths and update direct callers to v4 public APIs.
- [ ] Run GREEN with all external tests plus source, snapshot and renderer tests.
- [ ] Record per-file added/removed/net runtime lines and confirm the named replacement set is net smaller.

## Task 6: Canonical Pack Regeneration and Report Verification

**Files:**

- Modify: `data/curated_external/argument_packs/zhongjixuchuang.json`
- Modify: `data/curated_external/argument_packs/fudan.json`
- Modify: `data/curated_external/argument_packs/heizhima.json`
- Modify: `config/stocks.json` only for v4 pack paths/schema if required.

- [ ] Build `/tmp` pilots from unedited source input first.
- [ ] Validate all three packs: exact offsets, zero reviewed target-to-peer leaks, zero reviewed peer-to-target leaks, zero high-value target unsafe units, reader/display/lint ready.
- [ ] Atomically replace all three canonical packs and config in one commit-sized change.
- [ ] Run focused tests, CI grep gates and formal report generation/quality validation for all three stocks.
- [ ] Stop before cutover if any canonical source has degraded comparative boundaries or requires manual evidence edits.

## Completion Gate

- All v4 public-contract, snapshot and renderer tests pass.
- `bash tools/ci_grep_gates.sh` and `git diff --check` pass.
- Runtime search finds one source document builder, scope resolver, taxonomy owner, pack reader and display-envelope writer.
- No v3/v3.1 schema literal, raw fallback or report-time LLM call remains in runtime.
- Three regenerated packs and reports pass their documented safety and quality gates.
