# Annual Coverage Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover annual-report narrative coverage without changing the v2 card schema boundary, renderer wording, scoring, LLM, or collection paths.

**Architecture:** The evidence pack remains the one bounded upstream input, but uses a 48-block cap and reserves one narrative block per populated canonical family before normal priority filling. The producer remains the only card selector and reads envelope document style for two narrow admission rules. The material pack keeps v1 adaptation only when exact SourceUnit coverage cannot prove a legacy fact survives in v2.

**Tech Stack:** Python 3, standard-library `re`, pytest, existing local annual-report caches. No new dependencies or network access.

---

## Scope Guardrails

Allowed runtime files:

- `scripts/utils/annual_argument_schema.py`
- `scripts/utils/periodic_report_evidence_pack.py`
- `scripts/utils/periodic_report_narrative_evidence_cards.py`
- `scripts/utils/annual_report_material_pack.py`

Allowed test files:

- `tests/utils/test_annual_argument_schema.py`
- `tests/utils/test_periodic_report_evidence_pack.py`
- `tests/utils/test_periodic_report_narrative_evidence_cards.py`
- `tests/utils/test_annual_report_material_pack.py`

Do not modify scoring, target price, risk, technical analysis, recommendation, `KnowledgeSynthesizer`, renderer wording, profile routing, collection, config, or prompts. Do not delete/archive legacy Knowledge notes. Do not access network, Xueqiu, Chrome, or CDP.

Measure combined runtime delta against commit `aa7bdd9`. The target is at most +80 net lines. Stop at +100 net lines; tests, docs, and generated local notes do not count.

## File Responsibilities

| File | Responsibility after this work |
| --- | --- |
| `annual_argument_schema.py` | Sole owner of usage-to-family metadata, source normalization, and concrete-anchor detection. |
| `periodic_report_evidence_pack.py` | Envelope style and at-most-48 deterministic block allocation. |
| `periodic_report_narrative_evidence_cards.py` | The sole v2 card selector, with bounded A-share/HK admission rules. |
| `annual_report_material_pack.py` | Exact v1-to-v2 SourceUnit coverage classification and diagnostics. |

### Task 1: Centralize Usage Metadata and Source Semantics

**Files:**
- Modify: `scripts/utils/annual_argument_schema.py`
- Test: `tests/utils/test_annual_argument_schema.py`

- [ ] **Step 1: Write failing compatibility tests**

Add this complete fixture and tests:

```python
EXPECTED_USAGE_FAMILIES = {
    "business_overview": "business_structure",
    "business_model": "business_structure",
    "product_capacity_profile": "business_structure",
    "sales_certification_model": "business_structure",
    "hk_business_overview": "business_structure",
    "hk_customer_ecosystem": "business_structure",
    "segment_table": "operating_progress",
    "production_sales_inventory_table": "operating_progress",
    "management_strategy": "operating_progress",
    "management_market_view": "market_competition_outlook",
    "industry_outlook": "market_competition_outlook",
    "market_demand_outlook": "market_competition_outlook",
    "competitive_position": "market_competition_outlook",
    "future_strategy": "market_competition_outlook",
    "hk_market_outlook": "market_competition_outlook",
    "rd_product_progress": "technology_product_progress",
    "rd_table": "technology_product_progress",
    "rd_investment_table": "technology_product_progress",
    "hk_product_progress": "technology_product_progress",
    "profitability_commentary": "financial_quality_explanation",
    "hk_financial_commentary": "financial_quality_explanation",
    "cash_flow_capex_table": "financial_quality_explanation",
    "asset_impairment_note": "financial_quality_explanation",
    "ar_aging_note": "financial_quality_explanation",
    "inventory_note": "financial_quality_explanation",
    "audit_key_matters": "financial_quality_explanation",
    "government_grant_note": "financial_quality_explanation",
    "financial_assets_note": "financial_quality_explanation",
    "goodwill_note": "financial_quality_explanation",
}

def test_usage_metadata_replaces_the_former_producer_fallback_map():
    assert {
        usage: canonical_family_for_usage(usage)
        for usage in EXPECTED_USAGE_FAMILIES
    } == EXPECTED_USAGE_FAMILIES
    assert set(USAGE_FAMILY_METADATA) == set(EXPECTED_USAGE_FAMILIES)
    assert canonical_family_for_usage("unmapped_usage") is None
    assert is_high_value_narrative_usage("business_overview")
    assert not is_high_value_narrative_usage("segment_table")

def test_shared_normalization_and_anchor_gate_are_deterministic():
    assert normalize_annual_source_text("  2025 年\n客户付款形式变更。 ") == "2025 年 客户付款形式变更。"
    assert has_concrete_annual_anchor("2025 年客户付款形式变更为电汇。")
    assert has_concrete_annual_anchor("SESAMEX 平台提供机器人方案。")
    assert not has_concrete_annual_anchor("持续提升核心竞争力。")
```

- [ ] **Step 2: Run RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/utils/test_annual_argument_schema.py -q -p no:cacheprovider
```

Expected: imports for the new metadata/helpers fail.

- [ ] **Step 3: Implement the schema-owned contract**

Add `USAGE_FAMILY_METADATA` with every key in `EXPECTED_USAGE_FAMILIES` and a `reserve` boolean. The only true reserve usages are:

```python
HIGH_VALUE_NARRATIVE_USAGES = {
    "business_overview", "business_model", "product_capacity_profile",
    "sales_certification_model", "hk_business_overview", "hk_customer_ecosystem",
    "management_strategy", "management_market_view", "industry_outlook",
    "market_demand_outlook", "competitive_position", "future_strategy",
    "hk_market_outlook", "rd_product_progress", "hk_product_progress",
    "profitability_commentary", "hk_financial_commentary",
}
```

Add these public functions:

```python
def canonical_family_for_usage(usage: str) -> str | None:
    metadata = USAGE_FAMILY_METADATA.get(str(usage or "").strip())
    return metadata["family"] if metadata else None

def is_high_value_narrative_usage(usage: str) -> bool:
    metadata = USAGE_FAMILY_METADATA.get(str(usage or "").strip())
    return bool(metadata and metadata["reserve"])

def normalize_annual_source_text(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()
```

Implement `has_concrete_annual_anchor(text)` using only generic date/metric, Latin product/platform identifier, and business/product/customer/application/technology/financial-cause forms. Keep v1 adapter behavior unchanged.

- [ ] **Step 4: Run GREEN and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/utils/test_annual_argument_schema.py -q -p no:cacheprovider
git add scripts/utils/annual_argument_schema.py tests/utils/test_annual_argument_schema.py
git commit -m "feat: centralize annual usage metadata"
```

### Task 2: Add Document Style and Family-Reserved Evidence Allocation

**Files:**
- Modify: `scripts/utils/periodic_report_evidence_pack.py`
- Test: `tests/utils/test_periodic_report_evidence_pack.py`

- [ ] **Step 1: Write failing evidence-pack tests**

Add these tests and update the existing cap expectation from 30 to 48:

```python
def test_document_style_is_envelope_only_and_conservative():
    assert build_periodic_report_evidence_pack(
        "管理层讨论与分析\n公司主营业务为测试产品。", report_type="annual"
    )["document_style"] == "a_share_annual"
    assert build_periodic_report_evidence_pack(
        "管理層討論及分析\n本集團業務回顧。", report_type="annual"
    )["document_style"] == "hkex_annual"
    assert build_periodic_report_evidence_pack(
        "季度经营摘要。", report_type="quarterly"
    )["document_style"] == "unknown"

def test_family_reserve_keeps_low_priority_business_narrative():
    blocks = [
        {"id": f"financial_summary_table-{i}", "usage": "financial_summary_table",
         "section": "财务", "title": "财务",
         "text": "营业收入 100 亿元，净利润 10 亿元。",
         "source_span": {"start": i, "end": i + 1}}
        for i in range(48)
    ] + [{
        "id": "business_overview-0", "usage": "business_overview",
        "section": "主营业务", "title": "主营业务",
        "text": "公司主要从事高端光通信收发模块的研发、生产及销售。",
        "source_span": {"start": 99, "end": 100},
    }]
    selected = _select_bounded_blocks(blocks)
    assert len(selected) == 48
    assert any(block["id"] == "business_overview-0" for block in selected)
    assert any(block["usage"] == "financial_summary_table" for block in selected)

def test_structural_usage_cannot_consume_a_family_reserve_slot():
    blocks = [{"id": "segment_table-0", "usage": "segment_table",
               "section": "表", "title": "表",
               "text": "分产品 营业收入 营业成本 毛利率。",
               "source_span": {"start": 0, "end": 1}}]
    assert _reserved_narrative_blocks(blocks) == []
```

- [ ] **Step 2: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py -q -p no:cacheprovider
```

Expected: style/allocation helpers do not exist and old cap assertions fail.

- [ ] **Step 3: Implement the style and allocation helpers**

Set `_MAX_BLOCKS = 48`. Keep `_dedupe_and_prioritize_blocks()` as the only dedupe/priority source, then call `_select_bounded_blocks()` before trimming:

```python
def _document_style(text: str, report_type: str) -> str:
    if _looks_like_hk_report(text):
        return "hkex_annual"
    annual = report_type in {"annual", "annual_report"}
    if annual and any(token in text for token in (
        "管理层讨论与分析", "报告期内公司", "年度报告全文",
    )):
        return "a_share_annual"
    return "unknown"

def _reserved_narrative_blocks(blocks: list[dict]) -> list[dict]:
    reserved = []
    for family in CANONICAL_FAMILIES:
        for block in blocks:
            if canonical_family_for_usage(block.get("usage")) != family:
                continue
            if not is_high_value_narrative_usage(block.get("usage")):
                continue
            if _has_complete_narrative_clause(block.get("text", "")):
                reserved.append(block)
                break
    return reserved

def _select_bounded_blocks(blocks: list[dict]) -> list[dict]:
    selected_ids = {block["id"] for block in _reserved_narrative_blocks(blocks)}
    for block in blocks:
        if len(selected_ids) >= _MAX_BLOCKS:
            break
        selected_ids.add(block["id"])
    return [block for block in blocks if block["id"] in selected_ids]
```

`_has_complete_narrative_clause()` requires a sentence/semicolon clause of at least 24 non-whitespace characters. Return `document_style` from normal and empty envelope paths. Keep `periodic_report_evidence_pack.v1` unchanged because this is additive envelope metadata.

- [ ] **Step 4: Run GREEN and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py -q -p no:cacheprovider
git add scripts/utils/periodic_report_evidence_pack.py tests/utils/test_periodic_report_evidence_pack.py
git commit -m "feat: reserve annual narrative evidence coverage"
```

### Task 3: Add Style-Gated Producer Admission

**Files:**
- Modify: `scripts/utils/periodic_report_narrative_evidence_cards.py`
- Test: `tests/utils/test_periodic_report_narrative_evidence_cards.py`

- [ ] **Step 1: Write failing source-boundary and HK tests**

```python
def test_a_share_checkbox_tail_keeps_one_complete_financial_source_substring():
    pack = {"document_style": "a_share_annual", "blocks": [{
        "id": "cash_flow_capex_table-0", "usage": "cash_flow_capex_table",
        "text": "经营活动现金流量净额变动情况 √适用 □不适用 2025年第四季度客户付款形式由航信变动为电汇，主要系经营活动现金流量净额增加所致。",
    }]}
    cards = build_periodic_report_narrative_evidence_cards(
        stock_code="300777", stock_name="测试股", report_year=2025,
        report_type="annual", evidence_pack=pack,
    )["cards"]
    assert [card["source_excerpt"] for card in cards] == [
        "2025年第四季度客户付款形式由航信变动为电汇，主要系经营活动现金流量净额增加所致。"
    ]

def test_a_share_multiple_marker_unit_remains_rejected():
    pack = {"document_style": "a_share_annual", "blocks": [{
        "id": "cash_flow_capex_table-0", "usage": "cash_flow_capex_table",
        "text": "事项一 √适用 □不适用 事项二 √适用 □不适用 经营现金流增加所致。",
    }]}
    assert not build_periodic_report_narrative_evidence_cards(
        stock_code="300777", stock_name="测试股", report_year=2025,
        report_type="annual", evidence_pack=pack,
    )["cards"]

def test_hkex_implicit_subject_requires_anchor_predicate_and_style():
    block = {"id": "hk_business_overview-0", "usage": "hk_business_overview",
             "text": "SESAMEX机器人平台为智能汽车及机器人客户提供全栈自进化全脑智能解决方案。"}
    hk = build_periodic_report_narrative_evidence_cards(
        stock_code="02533", stock_name="测试港股", report_year=2025,
        report_type="annual", evidence_pack={"document_style": "hkex_annual", "blocks": [block]},
    )["cards"]
    unknown = build_periodic_report_narrative_evidence_cards(
        stock_code="02533", stock_name="测试港股", report_year=2025,
        report_type="annual", evidence_pack={"document_style": "unknown", "blocks": [block]},
    )["cards"]
    assert len(hk) == 1 and hk[0]["argument_family"] == "business_structure"
    assert unknown == []
```

Also add a standalone `SESAMEX平台。` negative fixture.

- [ ] **Step 2: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/utils/test_periodic_report_narrative_evidence_cards.py -q -p no:cacheprovider
```

Expected: marker-tail and HK implicit-subject tests fail against current admission.

- [ ] **Step 3: Implement without a second selector**

Import `canonical_family_for_usage`, `normalize_annual_source_text`, and `has_concrete_annual_anchor`; delete local `_USAGE_FALLBACKS`. Make `_materialize_source_units()` use the shared normalizer.

Read `document_style = evidence_pack.get("document_style", "unknown")` once. Before `_noise_reason()`, replace a marker unit only through this bounded helper:

```python
def _extract_a_share_causal_tail(unit: dict, usage_hint: str, document_style: str, cleaned_block: str) -> dict | None:
    if document_style != "a_share_annual":
        return None
    runs = list(_CHECKBOX_MARKER_RUN_RE.finditer(unit["text"]))
    if len(runs) != 1:
        return None
    tail = unit["text"][runs[0].end():].strip()
    family = canonical_family_for_usage(usage_hint)
    if family not in {"operating_progress", "technology_product_progress", "financial_quality_explanation"}:
        return None
    if not tail or _CHECKBOX_MARKER_RUN_RE.search(tail):
        return None
    if not tail.endswith(("。", "；", ";", "！", "？", "!", "?")):
        return None
    if not has_concrete_annual_anchor(tail) or _noise_reason(tail, source_block_text=tail):
        return None
    start = cleaned_block.find(tail, unit["start_pos"], unit["end_pos"])
    return None if start < 0 else {**unit, "start_pos": start, "end_pos": start + len(tail), "text": tail}
```

The original unit remains on the normal rejection path if this returns `None`. Make `_usage_fallback_family()` call `canonical_family_for_usage()` but retain existing product-progress safeguards. Extend `_is_self_contained_atomic_fact()` with keyword-only `document_style` and `usage_hint`; HK relaxation is valid only for `hkex_annual`, `hk_business_overview|hk_customer_ecosystem|hk_product_progress`, plus named structural anchor and contextual predicate in the same unit.

- [ ] **Step 4: Run GREEN and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/utils/test_periodic_report_narrative_evidence_cards.py -q -p no:cacheprovider
git add scripts/utils/periodic_report_narrative_evidence_cards.py tests/utils/test_periodic_report_narrative_evidence_cards.py
git commit -m "fix: preserve annual narrative source boundaries"
```

### Task 4: Add Exact Legacy SourceUnit Coverage Audit

**Files:**
- Modify: `scripts/utils/annual_report_material_pack.py`
- Test: `tests/utils/test_annual_report_material_pack.py`

- [ ] **Step 1: Write failing coverage tests**

Use existing `_write_note()` and `_write_v2_note()` helpers to prove both cases:

```python
def test_split_v2_source_units_cover_one_legacy_long_excerpt(tmp_path: Path):
    legacy = "公司拥有38大类6800余款可供销售产品。信号链类模拟芯片覆盖各类运算放大器。"
    _write_note(tmp_path, body_excerpt=legacy, filename="legacy.md")
    _write_v2_note(
        tmp_path, filename="v2.md", card_id="v2:products",
        source_block_id="market_demand_outlook-0", source_excerpt=legacy,
        source_units=[
            {"unit_id": "market_demand_outlook-0:u0", "block_id": "market_demand_outlook-0", "ordinal": 0, "start_pos": 0, "end_pos": 21, "text": "公司拥有38大类6800余款可供销售产品。"},
            {"unit_id": "market_demand_outlook-0:u1", "block_id": "market_demand_outlook-0", "ordinal": 1, "start_pos": 21, "end_pos": len(legacy), "text": "信号链类模拟芯片覆盖各类运算放大器。"},
        ],
    )
    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)
    assert pack["diagnostics"]["v1_unit_covered_count"] == 1
    assert pack["diagnostics"]["v1_adapter_use_count"] == 0

def test_missing_legacy_fact_remains_adapted_with_recovery_diagnostic(tmp_path: Path):
    legacy = "公司主营业务为高端光通信收发模块的研发、生产及销售。"
    _write_note(tmp_path, body_excerpt=legacy, filename="legacy.md")
    _write_v2_note(tmp_path, filename="v2.md", card_id="v2:other",
                   source_block_id="market_demand_outlook-0",
                   source_excerpt="行业需求保持增长。")
    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)
    assert pack["diagnostics"]["v1_needs_recovery_count"] == 1
    assert pack["diagnostics"]["v1_adapter_use_count"] == 1
    assert "高端光通信收发模块" in pack["diagnostics"]["v1_recovery_examples"][0]["fragment"]
```

Assert the legacy note path still exists after building the pack.

- [ ] **Step 2: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/utils/test_annual_report_material_pack.py -q -p no:cacheprovider
```

Expected: new diagnostics do not exist and old exact-only shadow behavior fails the split-unit test.

- [ ] **Step 3: Implement the classifier**

Import `normalize_annual_source_text` and `has_concrete_annual_anchor`. Keep the old punctuation-stripping normalizer only for near-duplicate ranking; rename it `_normalize_for_similarity` if needed. Use the shared normalizer for source identity and all coverage comparisons.

```python
def _coverage_classification(legacy: _CardRecord, v2_records: list[_CardRecord]) -> tuple[str, dict]:
    if _record_identity_keys(legacy) & _v2_identity_keys(v2_records):
        return "exact_shadowed", {}
    fragments = _meaningful_legacy_fragments(legacy.excerpt)
    proof = _cover_fragments_with_units(fragments, legacy.source_block_id, v2_records)
    if proof is not None:
        return "covered_by_v2_units", {"unit_ids": proof}
    return "needs_recovery", {"fragments": _uncovered_fragments(fragments, legacy.source_block_id, v2_records)}
```

`_meaningful_legacy_fragments()` uses the same sentence/semicolon terminators as SourceUnit materialization, drops short/heading/checkbox/boilerplate fragments, and requires `has_concrete_annual_anchor()`. `_cover_fragments_with_units()` only considers v2 units from the same `source_block_id`, sorts by `(ordinal, start_pos)`, and proves each fragment through one unit or a monotonic contiguous sequence. Never use Jaccard, token overlap, or semantic similarity for coverage.

In `build_annual_report_material_pack()`, suppress only `exact_shadowed` and `covered_by_v2_units`; adapt `needs_recovery` cards exactly as before. Add default diagnostics:

```python
"v1_exact_shadowed_count": 0,
"v1_unit_covered_count": 0,
"v1_needs_recovery_count": 0,
"v1_adapter_use_count": 0,
"v1_recovery_examples": [],
```

Do not write, rename, delete, or archive any note file.

- [ ] **Step 4: Run GREEN and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/utils/test_annual_report_material_pack.py -q -p no:cacheprovider
git add scripts/utils/annual_report_material_pack.py tests/utils/test_annual_report_material_pack.py
git commit -m "fix: audit annual v1 source coverage"
```

### Task 5: Verify Boundaries, Runtime Budget, and Local-Cache Recovery

**Files:**
- Create: `docs/agent_workflow/2026-07-12-annual-coverage-repair-claude-notes.md`
- Verify: the four runtime and four focused-test files above

- [ ] **Step 1: Run focused contracts**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_annual_argument_schema.py \
  tests/utils/test_periodic_report_evidence_pack.py \
  tests/utils/test_periodic_report_narrative_evidence_cards.py \
  tests/utils/test_annual_report_material_pack.py -q -p no:cacheprovider
bash tools/ci_grep_gates.sh
git diff --check
```

Expected: all pass and `git diff --check` has no output.

- [ ] **Step 2: Measure runtime delta before refresh**

```bash
git diff --numstat aa7bdd9 -- \
  scripts/utils/annual_argument_schema.py \
  scripts/utils/periodic_report_evidence_pack.py \
  scripts/utils/periodic_report_narrative_evidence_cards.py \
  scripts/utils/annual_report_material_pack.py
```

Sum additions minus deletions. If above +100, stop and return to design without refreshing notes or generating reports.

- [ ] **Step 3: Refresh local annual cards only**

For every pair below, run the existing preview with only local cache, `--write-knowledge`, and `--refresh-existing`:

```text
02533  黑芝麻智能
000661  长春高新
002050  三花智控
300777  中简科技
300661  圣邦股份
688018  乐鑫科技
300308  中际旭创
688385  复旦微电
```

Command shape:

```bash
python3 scripts/previews/periodic_report_narrative_cards_preview.py \
  --stock-code <code> --stock-name <name> \
  --report-type annual --report-year 2025 \
  --knowledge-base-dir knowledge --write-knowledge --refresh-existing
```

If only the same-machine project cache has a file, pass that explicit local path through `--cache-dir` and record it. Do not use the network.

- [ ] **Step 4: Apply the recovery gate before report generation**

For each refreshed stock, read/build the material pack and record `v1_exact_shadowed_count`, `v1_unit_covered_count`, `v1_needs_recovery_count`, and `v1_adapter_use_count`.

Acceptance requires:

- Zhongji has its main-business narrative in v2 output.
- Black Sesame has its SESAMEX/platform narrative under `hkex_annual`.
- Zhongjian has the payment-method/cash-flow suffix without a checkbox marker.
- Shengbang uses `covered_by_v2_units` for the split product note.
- Every configured stock has `v1_needs_recovery_count == 0`.

If any condition fails, stop. Do not archive v1 notes and do not generate reports.

- [ ] **Step 5: Write notes and commit only tracked implementation files**

Write the notes file with requirement-test matrix, runtime delta, local-cache results, deviations, and `Batch B allowed: yes | no`.

```bash
git add \
  scripts/utils/annual_argument_schema.py \
  scripts/utils/periodic_report_evidence_pack.py \
  scripts/utils/periodic_report_narrative_evidence_cards.py \
  scripts/utils/annual_report_material_pack.py \
  tests/utils/test_annual_argument_schema.py \
  tests/utils/test_periodic_report_evidence_pack.py \
  tests/utils/test_periodic_report_narrative_evidence_cards.py \
  tests/utils/test_annual_report_material_pack.py \
  docs/agent_workflow/2026-07-12-annual-coverage-repair-claude-notes.md
git commit -m "fix: repair annual narrative coverage"
```

Do not stage generated Knowledge notes, previews, reports, raw inputs, or other pre-existing worktree changes.
