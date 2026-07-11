# Annual Producer v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the overlapping eight-type annual narrative-card producer with one uncapped five-family, source-unit-owned producer and carry its completeness boundary safely through Chapter 4.

**Architecture:** Materialize punctuation-preserving SourceUnit records once, assemble each unit into at most one candidate bundle, and resolve that bundle to one canonical family. Persist v2 notes, build an uncapped annual pack, and propagate `argument_family` plus `argument_complete` directly through annual memo and MaterialRow; only complete annual rows may enter formal-medium 4.4. Batch A installs the canonical path and temporary read-only v1 adapter while deleting old caps/taxonomies; Batch B refreshes notes, removes the adapter and residual compatibility code, and proves the final line reduction.

**Tech Stack:** Python 3, plain dictionaries/dataclasses, pathlib, deterministic regex/text processing, pytest, Markdown report quality/source-boundary gates.

---

## Locked References

- Design: `docs/agent_workflow/2026-07-11-annual-producer-v2-design.md`
- Round 1: `docs/agent_workflow/2026-07-11-annual-producer-v2-claude-review-round1-notes.md`
- Round 2: `docs/agent_workflow/2026-07-11-annual-producer-v2-claude-review-round2-notes.md`
- Pre-v2 runtime baseline: `33be46f`
- Implementation notes:
  `docs/agent_workflow/2026-07-11-annual-producer-v2-claude-notes.md`

## Scope and Stops

Allowed runtime files:

- Create `scripts/utils/annual_argument_schema.py`
- Modify `scripts/utils/periodic_report_narrative_evidence_cards.py`
- Modify `scripts/utils/periodic_report_narrative_card_note_writer.py`
- Modify `scripts/utils/annual_report_material_pack.py`
- Modify `scripts/utils/periodic_report_narrative_card_synthesis_items.py`
- Modify `scripts/utils/report_skills/synthesis_skills.py`
- Modify `scripts/utils/deep_analysis_material_snapshot.py`
- Modify `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- Modify the exact test files listed under Tasks 1–9

Forbidden:

- scoring, target price, risk scoring, technical analysis, recommendation,
  executive summary, collection, browser/CDP, Xueqiu, LLM prompts, or External
  Producer changes;
- stock- or industry-specific classification rules;
- a second candidate selector or sparse fallback selector;
- silent count truncation in the canonical annual path;
- reverting or committing pre-existing report, broker-note, sidecar, or packet
  worktree changes.

Stop immediately when:

- Batch A runtime net addition exceeds `+100` lines against `33be46f`;
- distinct baseline fact anchors disappear without an accepted rejection reason;
- v1-adapted or `argument_complete=false` annual material reaches 4.4;
- citation/source-boundary/business-path regression appears;
- implementation needs a file outside the allowed scope.

## File Responsibilities

| File | Responsibility after v2 |
| --- | --- |
| `annual_argument_schema.py` | Versions, five families/labels, SourceUnit/card validation, temporary adapter, sort key |
| `periodic_report_narrative_evidence_cards.py` | One source-unit-first producer, generic noise gates, anchors, resolver, admission/dedupe diagnostics |
| `periodic_report_narrative_card_note_writer.py` | Flat v2 frontmatter, source excerpt, SourceUnit JSON body, refresh metadata |
| `annual_report_material_pack.py` | Read/adapt/dedupe/order every admitted card without business count caps |
| `periodic_report_narrative_card_synthesis_items.py` | Slice the uncapped pack only for optional LLM display context |
| `synthesis_skills.py` | Build uncapped annual memo rows with direct family/completeness fields |
| `deep_analysis_material_snapshot.py` | Carry direct annual roles/completeness and build safe formal-medium sections |
| `deep_analysis_renderer.py` | Map canonical families to labels and render every admitted annual row |

## Batch A

### Task 1: Add the canonical schema owner

**Files:**
- Create: `scripts/utils/annual_argument_schema.py`
- Create: `tests/utils/test_annual_argument_schema.py`

- [ ] **Step 1: Write failing schema and adapter tests**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from annual_argument_schema import (
    CANONICAL_FAMILIES,
    CARD_SCHEMA_VERSION,
    ENVELOPE_SCHEMA_VERSION,
    SELECTION_VERSION,
    adapt_v1_card,
    validate_card_v2,
)


def test_versions_and_families_are_locked():
    assert CARD_SCHEMA_VERSION == "periodic_report_narrative_evidence_card.v2"
    assert ENVELOPE_SCHEMA_VERSION == "periodic_report_narrative_evidence_cards.v2"
    assert SELECTION_VERSION == "annual_argument_selection.v2"
    assert CANONICAL_FAMILIES == (
        "business_structure",
        "operating_progress",
        "market_competition_outlook",
        "technology_product_progress",
        "financial_quality_explanation",
    )


def test_v1_adapter_is_atomic_and_uses_legacy_proxy_unit():
    card = adapt_v1_card({
        "card_id": "legacy:1",
        "card_type": "rd_product_progress",
        "source_block_id": "rd-0",
        "source_excerpt": "A2000芯片已进入客户验证阶段。",
        "quality_score": 3,
    })
    assert card["argument_family"] == "technology_product_progress"
    assert card["argument_complete"] is False
    assert ":legacy:" in card["source_unit_ids"][0]
    assert card["source_units"][0]["text"] == card["source_excerpt"]
    assert validate_card_v2(card) == ()


def test_validation_rejects_unknown_family_and_mismatched_units():
    card = adapt_v1_card({
        "card_id": "legacy:2",
        "card_type": "business_model",
        "source_block_id": "business-0",
        "source_excerpt": "公司主营高速光模块。",
    })
    card["argument_family"] = "old_display_role"
    card["source_unit_ids"] = ["wrong"]
    errors = validate_card_v2(card)
    assert "invalid_argument_family" in errors
    assert "source_unit_ids_mismatch" in errors
```

- [ ] **Step 2: Run tests and verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -m pytest tests/utils/test_annual_argument_schema.py -q -p no:cacheprovider
```

Expected: collection fails because `annual_argument_schema` does not exist.

- [ ] **Step 3: Implement the schema owner**

Use these public constants and validators:

```python
CARD_SCHEMA_VERSION = "periodic_report_narrative_evidence_card.v2"
ENVELOPE_SCHEMA_VERSION = "periodic_report_narrative_evidence_cards.v2"
SELECTION_VERSION = "annual_argument_selection.v2"

CANONICAL_FAMILIES = (
    "business_structure",
    "operating_progress",
    "market_competition_outlook",
    "technology_product_progress",
    "financial_quality_explanation",
)

FAMILY_LABELS = {
    "business_structure": "业务结构",
    "operating_progress": "经营变化",
    "market_competition_outlook": "管理层判断与行业展望",
    "technology_product_progress": "技术与产品进展",
    "financial_quality_explanation": "财务质量与变化原因",
}


def validate_source_unit(unit: dict) -> tuple[str, ...]:
    errors = []
    required = ("unit_id", "block_id", "ordinal", "start_pos", "end_pos", "text")
    if any(unit.get(key) in (None, "") for key in required):
        errors.append("missing_source_unit_field")
    if not isinstance(unit.get("ordinal"), int):
        errors.append("invalid_source_unit_ordinal")
    if not isinstance(unit.get("start_pos"), int) or not isinstance(unit.get("end_pos"), int):
        errors.append("invalid_source_unit_position")
    elif unit["start_pos"] < 0 or unit["end_pos"] <= unit["start_pos"]:
        errors.append("invalid_source_unit_range")
    return tuple(errors)


def validate_card_v2(card: dict) -> tuple[str, ...]:
    errors = []
    required = (
        "schema_version", "selection_version", "card_id", "argument_family",
        "argument_complete", "title", "source_block_id", "source_unit_ids",
        "source_units", "source_excerpt", "fact_anchors", "secondary_signals",
        "score_parts", "quality_score", "selection_reason", "source_type",
        "source_credit", "report_year", "report_type",
    )
    if any(card.get(key) is None for key in required):
        errors.append("missing_card_field")
    if card.get("argument_family") not in CANONICAL_FAMILIES:
        errors.append("invalid_argument_family")
    units = card.get("source_units") or []
    ids = [unit.get("unit_id") for unit in units if isinstance(unit, dict)]
    if ids != list(card.get("source_unit_ids") or []):
        errors.append("source_unit_ids_mismatch")
    errors.extend(error for unit in units for error in validate_source_unit(unit))
    positions = [
        (unit["ordinal"], unit["start_pos"], unit["end_pos"])
        for unit in units if not validate_source_unit(unit)
    ]
    if positions != sorted(positions):
        errors.append("non_monotonic_source_units")
    if any(left[2] > right[1] for left, right in zip(positions, positions[1:])):
        errors.append("overlapping_source_units")
    return tuple(dict.fromkeys(errors))
```

Implement `adapt_v1_card` with the locked eight-to-five mapping. For
`margin_competitiveness`, select `financial_quality_explanation` only when the
excerpt contains a financial metric and causal token; otherwise select
`market_competition_outlook`. The adapter creates one proxy unit, forces
`argument_complete=False`, uses `selection_reason="legacy_v1_adapter"`, and
never writes files.

- [ ] **Step 4: Run schema tests and verify GREEN**

- [ ] **Step 5: Commit Task 1**

```bash
git add scripts/utils/annual_argument_schema.py tests/utils/test_annual_argument_schema.py
git commit -m "feat: add annual argument v2 schema"
```

### Task 2: Replace the producer with one SourceUnit-first selector

**Files:**
- Modify: `scripts/utils/periodic_report_narrative_evidence_cards.py`
- Modify: `tests/utils/test_periodic_report_narrative_evidence_cards.py`

- [ ] **Step 1: Add v2 RED tests before changing old assertions**

Add focused tests for all five families plus these contracts:

Extend the producer test import to include `_materialize_source_units` and
`_candidate_invariant_errors`; import `CANONICAL_FAMILIES` from
`annual_argument_schema`.

```python
def _build_cards(text: str, usage: str) -> dict:
    return build_periodic_report_narrative_evidence_cards(
        stock_code="000001",
        stock_name="测试股",
        report_year=2025,
        report_type="annual",
        evidence_pack={"blocks": [{
            "id": f"{usage}-0",
            "usage": usage,
            "text": text,
        }]},
    )


@pytest.mark.parametrize(("usage", "text", "family"), (
    ("business_overview", "公司主营高速光模块并服务云数据中心客户。", "business_structure"),
    ("segment_table", "报告期内高速光模块销量同比增长30%。", "operating_progress"),
    ("management_market_view", "管理层认为AI需求将推动行业景气延续。", "market_competition_outlook"),
    ("rd_product_progress", "A2000芯片已通过认证并进入客户验证。", "technology_product_progress"),
    ("profitability_commentary", "毛利率同比提升2个百分点，主要系产品结构改善。", "financial_quality_explanation"),
))
def test_each_candidate_resolves_to_one_canonical_family(usage, text, family):
    result = _build_cards(text, usage)
    assert [card["argument_family"] for card in result["cards"]] == [family]


def test_ambiguous_progress_emits_one_family_with_secondary_signal():
    result = _build_cards(
        "公司主营车规芯片，A2000已通过认证并进入客户验证阶段。",
        "product_capacity_profile",
    )
    assert len(result["cards"]) == 1
    card = result["cards"][0]
    assert card["argument_family"] == "technology_product_progress"
    assert "business_structure" in card["secondary_signals"]


def test_atomic_fact_is_kept_but_not_complete():
    result = _build_cards("A2000芯片已进入客户验证阶段。", "rd_product_progress")
    assert result["cards"][0]["argument_complete"] is False


def test_source_units_are_monotonic_source_substrings():
    text = "公司主营高速光模块。报告期内800G产品收入同比增长。"
    cleaned, units = _materialize_source_units("business-0", text)
    assert [unit["ordinal"] for unit in units] == [0, 1]
    for unit in units:
        assert cleaned[unit["start_pos"]:unit["end_pos"]] == unit["text"]
    result = _build_cards(text, "business_overview")
    assert all("card_type" not in card for card in result["cards"])
    assert all(
        unit["unit_id"] in {source["unit_id"] for source in units}
        for card in result["cards"] for unit in card["source_units"]
    )


def test_more_than_twelve_distinct_cards_survive():
    blocks = [{
        "id": f"operation-{index}",
        "usage": "segment_table",
        "text": f"报告期内产品P{index}实现批量交付，客户C{index}采购量同比增长{index + 1}%。",
    } for index in range(14)]
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="688385", stock_name="复旦微电", report_year=2025,
        report_type="annual", evidence_pack={"blocks": blocks},
    )
    assert len(result["cards"]) == 14


def test_sparse_atomic_unit_uses_normal_admission_path():
    result = _build_cards("公司主营电池计量芯片。", "business_overview")
    assert [card["argument_family"] for card in result["cards"]] == ["business_structure"]
    assert result["diagnostics"]["admission_invariant_violation"] is False


def test_admitted_source_unit_is_owned_once():
    result = _build_cards(
        "公司主营高速光模块。报告期内1.6T产品进入客户验证。",
        "product_capacity_profile",
    )
    ids = [
        unit_id
        for card in result["cards"]
        for unit_id in card["source_unit_ids"]
    ]
    assert len(ids) == len(set(ids))


def test_same_block_distinct_assertions_form_non_overlapping_cards():
    result = _build_cards(
        "公司主营高速光模块并服务云数据中心客户。报告期内1.6T产品进入客户验证。",
        "product_capacity_profile",
    )
    assert {card["argument_family"] for card in result["cards"]} == {
        "business_structure", "technology_product_progress",
    }
    unit_sets = [set(card["source_unit_ids"]) for card in result["cards"]]
    assert unit_sets[0].isdisjoint(unit_sets[1])


def test_similar_wording_with_distinct_products_and_periods_survives():
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="000001", stock_name="测试股", report_year=2025,
        report_type="annual", evidence_pack={"blocks": [
            {"id": "p1", "usage": "segment_table", "text": "2024年产品P1销量同比增长10%。"},
            {"id": "p2", "usage": "segment_table", "text": "2025年产品P2销量同比增长10%。"},
        ]},
    )
    assert len(result["cards"]) == 2


def test_complete_argument_scores_above_atomic_fact():
    result = build_periodic_report_narrative_evidence_cards(
        stock_code="000001", stock_name="测试股", report_year=2025,
        report_type="annual", evidence_pack={"blocks": [
            {"id": "rd-atomic", "usage": "rd_product_progress", "text": "A2000芯片进入客户验证。"},
            {"id": "rd-complete", "usage": "rd_product_progress", "text": "A2000X采用7nm工艺并完成算法适配，因此进入客户验证阶段。"},
        ]},
    )
    by_block = {card["source_block_id"]: card for card in result["cards"]}
    assert by_block["rd-complete"]["argument_complete"] is True
    assert by_block["rd-complete"]["quality_score"] > by_block["rd-atomic"]["quality_score"]


def test_diagnostics_and_candidate_invariant_contract_are_stable():
    result = _build_cards("公司主营电池计量芯片。", "business_overview")
    required = {
        "source_blocks_seen", "source_units_seen", "usable_units",
        "candidates_by_family", "admitted_by_family",
        "argument_complete_counts", "rejection_counts", "missing_families",
        "candidate_explosion", "candidate_explosion_block_ids",
        "admission_invariant_violation", "v1_adapter_use_count", "cards",
    }
    assert required <= set(result["diagnostics"])
    errors = _candidate_invariant_errors(
        [{"source_unit_ids": ["u0"]}, {"source_unit_ids": ["u0"]}],
        usable_unit_count=1,
    )
    assert "candidate_count_exceeds_usable_units" in errors
    assert "reused_source_units" in errors
```

- [ ] **Step 2: Run only the new tests and verify RED**

Expected: v1 schema/card types, missing SourceUnits, duplicate multi-family
output, and count truncation cause failures.

- [ ] **Step 3: Implement one source-unit-first producer**

Delete `_CARD_TYPES`, `_USAGE_TO_CARD_TYPES`, `_CARD_TYPE_MARKERS`,
`_dedupe_scope`, `_candidate_card_type_sort_index`, `_truncate_cards`, and
`_select_diverse_cards`. Retain generic noise helpers that are independent of
old card types.

Materialize units with punctuation-preserving offsets:

```python
def _materialize_source_units(block_id: str, text: str) -> tuple[str, list[dict]]:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    units = []
    for ordinal, match in enumerate(re.finditer(r".+?(?:[。；;！？!?]|$)", cleaned)):
        value = match.group(0).strip()
        if not value:
            continue
        start = cleaned.find(value, match.start(), match.end())
        units.append({
            "unit_id": f"{block_id}:u{ordinal}",
            "block_id": block_id,
            "ordinal": ordinal,
            "start_pos": start,
            "end_pos": start + len(value),
            "text": value,
        })
    return cleaned, units
```

The candidate loop iterates usable units once in source order, appends only
contiguous units belonging to the same argument, advances past consumed units,
and calls one `resolve_argument_family(bundle, usage_hint)`. The resolver uses
this fixed precedence: financial cause, named product progress, report-period
operating change, management market judgment, business scope. Usage is a weak
fallback only; all other matched families become `secondary_signals`.

Build `source_excerpt` from the exact cleaned-block slice beginning at the first
unit's `start_pos` and ending at the last unit's `end_pos`; never join rewritten
sentences or truncate a clause.

Admission accepts anchored, self-contained atomic facts. Emit the diagnostics
keys from design Section 13. Before returning, fail closed if candidate/card
count exceeds usable-unit count or an admitted unit is reused. Keep this check in
one `_candidate_invariant_errors(candidates, usable_unit_count)` helper used by
both the producer and its focused invariant test.

- [ ] **Step 4: Migrate existing producer tests without weakening noise gates**

Use this assertion mapping:

| Old output | V2 output |
| --- | --- |
| `business_model` | `business_structure` |
| `operation_update` | `operating_progress` |
| management/outlook pair | one `market_competition_outlook` |
| technology/R&D pair | one `technology_product_progress` |
| financial margin/note | `financial_quality_explanation` |
| competitive-only margin | `market_competition_outlook` |
| cap tests | all distinct cards survive |

Keep all table, OCR, audit, policy, checkbox, page-marker, risk, and HK
Traditional-Chinese rejection fixtures. Replace two-type expectations with one
family plus `secondary_signals`; do not delete those fixtures in Batch A.

- [ ] **Step 5: Run producer tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -m pytest tests/utils/test_annual_argument_schema.py tests/utils/test_periodic_report_narrative_evidence_cards.py -q -p no:cacheprovider
```

- [ ] **Step 6: Check cumulative runtime delta**

```bash
git diff --numstat 33be46f -- scripts/utils/annual_argument_schema.py scripts/utils/periodic_report_narrative_evidence_cards.py
```

Stop if cumulative Batch A runtime net addition exceeds `+100`.

- [ ] **Step 7: Commit Task 2**

```bash
git add scripts/utils/periodic_report_narrative_evidence_cards.py tests/utils/test_periodic_report_narrative_evidence_cards.py
git commit -m "feat: build annual argument cards from source units"
```

### Task 3: Persist v2 notes and build one uncapped pack

**Files:**
- Modify: `scripts/utils/periodic_report_narrative_card_note_writer.py`
- Modify: `scripts/utils/annual_report_material_pack.py`
- Modify: `scripts/utils/periodic_report_narrative_card_synthesis_items.py`
- Modify: `tests/utils/test_periodic_report_narrative_card_note_writer.py`
- Modify: `tests/utils/test_annual_report_material_pack.py`
- Modify: `tests/utils/test_periodic_report_narrative_card_synthesis_items.py`

- [ ] **Step 1: Write RED tests**

Require flat v2 frontmatter plus SourceUnit JSON body, v2-over-v1 preference,
14-card pack retention, and three-item optional display slicing:

```python
import json


def _write_v2_note(
    base, *, index=0, family="business_structure",
    excerpt="公司主营高速光模块。", block_id=None,
):
    block_id = block_id or f"business-{index}"
    unit = {
        "unit_id": f"{block_id}:u0", "block_id": block_id, "ordinal": 0,
        "start_pos": 0, "end_pos": len(excerpt), "text": excerpt,
    }
    path = _cards_dir(base) / f"2025-annual-{family}-{index}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "source_type: periodic_report_narrative_evidence\n"
        f"card_id: periodic:000001:2025:annual:narrative:{family}:{index}\n"
        "schema_version: periodic_report_narrative_evidence_card.v2\n"
        "selection_version: annual_argument_selection.v2\n"
        f"argument_family: {family}\n"
        "argument_complete: false\n"
        "report_year: 2025\nreport_type: annual\nsource_credit: 75\n"
        f"source_block_id: {block_id}\n"
        f"source_unit_ids:\n  - {block_id}:u0\n"
        "knowledge_eligible: false\nsynthesis_eligible: false\n---\n\n"
        "## Narrative Evidence\n\n"
        f"> {excerpt}\n\n"
        "## Source Units\n\n```json\n"
        + json.dumps([unit], ensure_ascii=False, sort_keys=True, indent=2)
        + "\n```\n",
        encoding="utf-8",
    )
    return path


def test_pack_is_uncapped_but_display_items_are_budgeted(tmp_path):
    for index in range(14):
        _write_v2_note(tmp_path, index=index, family="operating_progress")
    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)
    items = load_periodic_narrative_card_synthesis_items(
        stock_name="测试股", base_dir=tmp_path, max_cards=3, use_pack=True,
    )
    assert len(pack["selected_narrative_cards"]) == 14
    assert len(items) == 3


def test_v2_note_shadows_same_source_v1_note(tmp_path):
    _write_note(tmp_path, body_excerpt="公司主营高速光模块。")
    _write_v2_note(
        tmp_path,
        excerpt="公司主营高速光模块。",
        block_id="market_demand_outlook-0",
    )
    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)
    assert len(pack["selected_narrative_cards"]) == 1
    assert pack["diagnostics"]["v1_adapter_use_count"] == 0
```

- [ ] **Step 2: Run note/pack/loader tests and verify RED**

- [ ] **Step 3: Implement v2 note serialization**

Frontmatter contains flat schema, selection, family, completeness, unit-id,
anchor, signal, score, and guardrail fields. Store nested units in the body:

```python
source_units_json = json.dumps(
    card["source_units"], ensure_ascii=False, sort_keys=True, indent=2,
)
body.extend(["## Source Units", "", "```json", source_units_json, "```", ""])

selection_json = json.dumps(
    {"score_parts": card["score_parts"], "selection_reason": card["selection_reason"]},
    ensure_ascii=False,
    sort_keys=True,
    indent=2,
)
body.extend([
    "## Selection Diagnostics", "", "```json", selection_json, "```", "",
])
```

Use `argument_family` in filenames. Preserve path escape, stock identity,
dry-run, hash, and deterministic refresh behavior.

In `test_periodic_report_narrative_card_note_writer.py`, replace its `_card`
fixture with a complete v2 card containing one SourceUnit and add a writer test
that asserts `selection_version`, `argument_family`, `argument_complete`, and
`## Source Units` are present while `card_type` is absent.

```python
def test_writer_persists_v2_family_and_source_units(tmp_path):
    plan = write_periodic_report_narrative_card_notes(
        "中际旭创", "300308", _pack([_card()]), tmp_path,
    )
    text = Path(plan.written[0]["planned_path"]).read_text(encoding="utf-8")
    assert "selection_version: annual_argument_selection.v2" in text
    assert "argument_family: business_structure" in text
    assert "argument_complete: false" in text
    assert "## Source Units" in text
    assert "## Selection Diagnostics" in text
    assert "card_type:" not in text
```

- [ ] **Step 4: Make the material pack uncapped and v2-first**

Replace record `card_type` with `argument_family` and carry completeness,
versions, units, anchors, and diagnostics. Parse both `## Source Units` and
`## Selection Diagnostics` JSON blocks. Adapt only unshadowed v1 notes.
Delete old high-value/other type lists, old title maps, `_select_records`, count
parameters, round-robin, second fill, and budget-exhausted diagnostics. Return
all admitted records in deterministic family/quality/source order.

- [ ] **Step 5: Isolate the LLM display budget**

When `use_pack=True`, build the uncapped pack without count parameters, convert
all records, then return `items[:max_cards]`. Remove `per_type_limit` from the
loader signature. This slice must not mutate or rebuild the pack.

- [ ] **Step 6: Run tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -m pytest tests/utils/test_periodic_report_narrative_card_note_writer.py tests/utils/test_annual_report_material_pack.py tests/utils/test_periodic_report_narrative_card_synthesis_items.py -q -p no:cacheprovider
```

- [ ] **Step 7: Commit Task 3**

```bash
git add scripts/utils/periodic_report_narrative_card_note_writer.py scripts/utils/annual_report_material_pack.py scripts/utils/periodic_report_narrative_card_synthesis_items.py tests/utils/test_periodic_report_narrative_card_note_writer.py tests/utils/test_annual_report_material_pack.py tests/utils/test_periodic_report_narrative_card_synthesis_items.py
git commit -m "feat: persist uncapped annual argument material"
```

### Task 4: Propagate family and completeness through annual memo

**Files:**
- Modify: `scripts/utils/report_skills/synthesis_skills.py`
- Modify: `tests/reporter/test_synthesis_skills.py`

- [ ] **Step 1: Write RED memo and context-budget tests**

Build a pack with 14 v2 cards and assert:

```python
memo = SynthesisSkill._build_annual_report_memo(ctx)
rows = memo["sections"]["annual_report_explanation"]
narrative_rows = [
    row for row in rows
    if row.get("source_type") == "periodic_report_narrative_evidence"
]
assert len(narrative_rows) == 14
assert {row["display_group"] for row in narrative_rows} <= set(CANONICAL_FAMILIES)
assert all("argument_complete" in row for row in narrative_rows)
assert not any(row["display_group"] in {
    "product_business", "operation_update", "management_view",
    "competitiveness_rd", "financial_explanation",
} for row in narrative_rows)
```

Set `periodic_narrative_cards_max_display_items=3` and separately assert that
the annual material pack and memo still contain all 14 cards.

- [ ] **Step 2: Run focused synthesis tests and verify RED**

Expected: only eight cards enter memo and old `card_group` values remain.

- [ ] **Step 3: Simplify `_build_annual_report_memo`**

Remove `valid_cards[:8]` and `card_group`. `_annual_row` carries `source_type`,
`argument_family`, `display_group`, and `argument_complete`. Narrative rows copy
those fields directly. Formal financial facts/explanations receive
`display_group="financial_quality_explanation"` and
`argument_complete=False`. Update `has_product` to use canonical families.

Change `_eligible_periodic_narrative_card_items` so it passes only the optional
display count to the loader; no count reaches `build_annual_report_material_pack`.

- [ ] **Step 4: Run synthesis tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -m pytest tests/reporter/test_synthesis_skills.py -q -p no:cacheprovider
```

- [ ] **Step 5: Commit Task 4**

```bash
git add scripts/utils/report_skills/synthesis_skills.py tests/reporter/test_synthesis_skills.py
git commit -m "refactor: propagate annual argument families"
```

### Task 5: Enforce 4.4 completeness and remove renderer caps

**Files:**
- Modify: `scripts/utils/deep_analysis_material_snapshot.py`
- Modify: `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- Modify: `tests/utils/test_deep_analysis_material_snapshot.py`
- Modify: `tests/reporter/test_deep_analysis_renderer.py`

- [ ] **Step 1: Write RED snapshot tests**

```python
def _snapshot_with_annual_row(argument_complete: bool) -> MaterialSnapshot:
    row = MaterialRow(
        row_id="annual:complete" if argument_complete else "annual:atomic",
        text="业务结构：公司主营高速光模块。",
        source_layer="annual",
        claim_status="formal_explanation",
        citation_refs=(1,),
        source_ref_ids=("annual:1",),
        title="业务结构",
        body="公司主营高速光模块。",
        render_role="business_structure",
        argument_complete=argument_complete,
    )
    return MaterialSnapshot(
        schema="deep_analysis_material_snapshot.v1",
        rows=(row,),
        citations={1: {"source": "公司年报", "title": "2025年年度报告"}},
        diagnostics={},
    )


def test_atomic_annual_row_is_4_1_only():
    snapshot = _snapshot_with_annual_row(argument_complete=False)
    view = build_chapter4_view_model(snapshot, "formal_medium")
    assert snapshot.rows[0] in view.section("4.1").rows
    assert snapshot.rows[0] not in view.section("4.4").rows


def test_complete_annual_row_may_enter_4_4():
    snapshot = _snapshot_with_annual_row(argument_complete=True)
    view = build_chapter4_view_model(snapshot, "formal_medium")
    assert snapshot.rows[0] in view.section("4.4").rows
```

Construct test rows with `render_role="business_structure"`, official
citations, and otherwise identical content.

- [ ] **Step 2: Write RED renderer tests**

Build an annual memo with five distinct `business_structure` rows. Assert all
five render in formal-medium 4.1 and formal-thin 4.1, canonical Chinese labels
appear, old machine roles do not, and formal-rich keeps its legacy routing.

- [ ] **Step 3: Run focused tests and verify RED**

Expected: `MaterialRow` lacks completeness, 4.4 accepts an atomic row, and the
shared annual profile renderer emits only two business rows.

- [ ] **Step 4: Implement direct role/completeness projection**

Add `argument_complete: bool = False` to `MaterialRow`. `_annual_rows` copies the
memo boolean and direct canonical `display_group`. Delete
`classify_annual_render_role` and every renderer import/call. Broker and external
roles remain unchanged.

In `build_chapter4_view_model`, choose an annual `price_path_rows` candidate only
from rows where `argument_complete is True`; do not fall back to the first atomic
annual row. Broker/external behavior stays unchanged.

- [ ] **Step 5: Render every admitted annual row**

Use `FAMILY_LABELS` in formal-medium and formal-thin. Portrait selection may
consume one business row once, but delete `row_limit` and `rows[:row_limit]`.
Keep deterministic dedupe, citation tracking, and formal-rich routing.

- [ ] **Step 6: Run snapshot/renderer tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -m pytest tests/utils/test_deep_analysis_material_snapshot.py tests/reporter/test_deep_analysis_renderer.py -q -p no:cacheprovider
```

- [ ] **Step 7: Commit Task 5**

```bash
git add scripts/utils/deep_analysis_material_snapshot.py scripts/utils/reporter/sections/deep_analysis_renderer.py tests/utils/test_deep_analysis_material_snapshot.py tests/reporter/test_deep_analysis_renderer.py
git commit -m "refactor: enforce annual chapter 4 boundaries"
```

### Task 6: Batch A regression, budget, and real-material gate

**Files:**
- Modify: `tests/reporter/test_report_quality.py`
- Modify: `tests/reporter/test_report_source_boundary.py`
- Create: `docs/agent_workflow/2026-07-11-annual-producer-v2-claude-notes.md`

- [ ] **Step 1: Add missing integration assertions**

Use an in-memory formal-medium context containing annual v2, broker, and
external rows. Assert all annual citations resolve, annual rows stay
`scoring_eligible=False` and `risk_score_eligible=False`, external/social tokens
do not enter 4.1, more than 12 annual rows survive rendered 4.1, and snapshot /
view-model building leaves scoring, target, risk, technical, recommendation, and
executive-summary input fields byte-for-byte unchanged.

- [ ] **Step 2: Run the complete focused suite**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -m pytest tests/utils/test_annual_argument_schema.py tests/utils/test_periodic_report_narrative_evidence_cards.py tests/utils/test_periodic_report_narrative_card_note_writer.py tests/utils/test_annual_report_material_pack.py tests/utils/test_periodic_report_narrative_card_synthesis_items.py tests/reporter/test_synthesis_skills.py tests/utils/test_deep_analysis_material_snapshot.py tests/reporter/test_deep_analysis_renderer.py tests/reporter/test_report_quality.py tests/reporter/test_report_source_boundary.py -q -p no:cacheprovider
```

Expected: all pass.

- [ ] **Step 3: Run static gates**

```bash
bash tools/ci_grep_gates.sh
git diff --check
```

Expected: grep gates pass and diff check has no output.

- [ ] **Step 4: Calculate Batch A runtime delta**

```bash
git diff --numstat 33be46f -- scripts/utils/annual_argument_schema.py scripts/utils/periodic_report_narrative_evidence_cards.py scripts/utils/periodic_report_narrative_card_note_writer.py scripts/utils/annual_report_material_pack.py scripts/utils/periodic_report_narrative_card_synthesis_items.py scripts/utils/report_skills/synthesis_skills.py scripts/utils/deep_analysis_material_snapshot.py scripts/utils/reporter/sections/deep_analysis_renderer.py
```

Record additions, deletions, and net. Stop above `+100`; explain a net above the
`+80` target before running reports.

- [ ] **Step 5: Run sparse local-cache acceptance**

```bash
python3 scripts/previews/periodic_report_narrative_cards_preview.py --stock-code 688325 --stock-name 赛微微电 --cache-dir data/raw/periodic_reports --report-type annual --report-year 2025 --include-json --output /tmp/赛微微电_annual_v2_preview.md --knowledge-base-dir /tmp/annual-v2-knowledge --write-knowledge --refresh-existing
```

Verify useful atomic facts survive, no family is filled with boilerplate, every
unit is a source substring, and only v2 notes are written under `/tmp`.

- [ ] **Step 6: Generate genuinely new configured reports**

Record HEAD/source mtime first, then run:

```bash
python3 scripts/run_stock_report.py --stock 复旦微电 --no-pdf
python3 scripts/run_stock_report.py --stock 中际旭创 --no-pdf
cd scripts && python3 run_黑芝麻智能.py --fast-test
```

Do not reuse stale Markdown. Record each generated path, size, and mtime, proving
report mtime is later than implementation/source mtime. Do not refresh Zhihu/LLM
material and do not access Xueqiu details or Chrome/CDP.

- [ ] **Step 7: Run report gates on every new Markdown**

For each exact Markdown path captured in Step 6, pass that path to
`scripts/check_report_quality.py`, `scripts/check_report_source_boundary.py`,
and `scripts/check_report_prose_quality.py`. Do not inspect an older same-stock
report.

Quality and source boundary must pass. Prose warnings may remain only when they
do not indicate truncation, duplication, or source leakage. Require zero
missing/unused/malformed citations and no unknown citation metadata.

- [ ] **Step 8: Write Batch A notes and checkpoint commit**

Notes must contain the requirement-test matrix, runtime delta, four-sample anchor
coverage, adapter-use counts, non-stale report evidence, gates, blocker/warning/
deviation, and `Batch B allowed: yes | no`.

```bash
git add docs/agent_workflow/2026-07-11-annual-producer-v2-claude-notes.md
git commit -m "docs: record annual producer v2 batch a"
```

Do not start Batch B unless the notes say `Batch B allowed: yes`.

## Batch B

### Task 7: Refresh notes and prove the adapter is unused

**Files:**
- Natural migration output only: `knowledge/10-Stocks/*/periodic_narrative_cards/`
- Modify: `tests/utils/test_annual_argument_schema.py`
- Modify: `tests/utils/test_annual_report_material_pack.py`
- Modify: `tests/utils/test_periodic_report_narrative_card_synthesis_items.py`

- [ ] **Step 1: Refresh configured stocks with local 2025 annual caches**

Use `periodic_report_narrative_cards_preview.py` with `--report-year 2025`,
`--report-type annual`, `--write-knowledge`, and `--refresh-existing` for these
configured code/name pairs:

```text
02533 黑芝麻智能
000661 长春高新
002050 三花智控
300777 中简科技
300661 圣邦股份
688018 乐鑫科技
300308 中际旭创
688385 复旦微电
```

Consume only `data/raw/periodic_reports` caches. Do not fetch the network.

- [ ] **Step 2: Verify v2 freshness and zero adapter use**

Every consumed active note must contain:

```text
schema_version: periodic_report_narrative_evidence_card.v2
selection_version: annual_argument_selection.v2
argument_family:
## Source Units
```

Run each stock's pack and require `v1_adapter_use_count == 0`. Move stale v1
notes to that stock's `periodic_narrative_cards/_legacy_archive/`; do not delete
them and do not touch broker-note archives.

- [ ] **Step 3: Stop if an unshadowed v1 anchor remains useful**

If any active v1 note still contributes a distinct fact anchor, stop and record
the stock, note, anchor, and producer rejection reason. Do not remove the adapter
until v2 recovers the material or review accepts the rejection.

### Task 8: Remove migration-only code and residual taxonomy

**Files:**
- Modify: `scripts/utils/annual_argument_schema.py`
- Modify: `scripts/utils/annual_report_material_pack.py`
- Modify: `scripts/utils/periodic_report_narrative_card_synthesis_items.py`
- Modify: `tests/utils/test_annual_argument_schema.py`
- Modify: `tests/utils/test_annual_report_material_pack.py`
- Modify: `tests/utils/test_periodic_report_narrative_card_synthesis_items.py`

- [ ] **Step 1: Write a RED stale-v1 rejection test**

```python
def _write_v1_note(base, *, excerpt: str):
    path = _cards_dir(base) / "2025-annual-business-model-legacy.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "source_type: periodic_report_narrative_evidence\n"
        "card_id: legacy:business:0\n"
        "schema_version: periodic_report_narrative_evidence_card.v1\n"
        "card_type: business_model\n"
        "report_year: 2025\nreport_type: annual\n"
        "source_block_id: business-0\n---\n\n"
        "## Narrative Evidence\n\n"
        f"> {excerpt}\n",
        encoding="utf-8",
    )
    return path


def test_post_migration_pack_ignores_v1_note(tmp_path):
    _write_v1_note(tmp_path, excerpt="旧材料。")
    pack = build_annual_report_material_pack(stock_name="测试股", base_dir=tmp_path)
    assert pack["selected_narrative_cards"] == []
    assert pack["diagnostics"]["legacy_notes_ignored"] == 1
```

Convert normal-loading fixtures to v2. Keep only this explicit stale-v1
rejection fixture.

- [ ] **Step 2: Remove migration-only runtime**

Delete `adapt_v1_card`, its eight-type map, proxy-unit logic, adapter-use
branches, old card-type titles, and legacy pack/loader parsing. Keep only a small
ignored-v1 diagnostic if it prevents silent stale-note use. Merge duplicate
frontmatter/scalar/card-order helpers only when behavior remains covered.

- [ ] **Step 3: Run focused tests and gates**

Run the complete Task 6 focused suite, `bash tools/ci_grep_gates.sh`, and
`git diff --check`.

- [ ] **Step 4: Audit final runtime reduction**

Compare all allowed runtime files against `33be46f`. Target net reduction is
`110–180` lines. If reduction is below `80`, stop and audit remaining old
taxonomy, title, ordering, cap, and loader helpers.

- [ ] **Step 5: Commit Batch B code**

```bash
git add scripts/utils/annual_argument_schema.py scripts/utils/annual_report_material_pack.py scripts/utils/periodic_report_narrative_card_synthesis_items.py tests/utils/test_annual_argument_schema.py tests/utils/test_annual_report_material_pack.py tests/utils/test_periodic_report_narrative_card_synthesis_items.py
git commit -m "refactor: remove annual narrative v1 compatibility"
```

### Task 9: Final real-report and source-boundary acceptance

**Files:**
- Modify: `docs/agent_workflow/2026-07-11-annual-producer-v2-claude-notes.md`
- Reports/knowledge only as natural outputs; do not stage automatically

- [ ] **Step 1: Generate genuinely new final artifacts**

After the Batch B commit, rerun the three configured report commands from Task 6
and the 赛微微电 local preview. Require every report/preview mtime to be later
than the Batch B source commit.

- [ ] **Step 2: Verify content contracts**

For all applicable samples verify:

- only five canonical annual family values; no old machine role in active data;
- distinct product, customer, period, metric, and mechanism anchors survive;
- no source unit is reused by two cards from one block;
- atomic facts appear in 4.1 but never as annual 4.4 premises;
- more than 12 valid rows survive when present;
- formal-thin and formal-medium render every admitted annual row;
- citations have zero missing, unused, malformed, or unknown entries;
- social/external sources do not leak into official 4.1;
- score, target, risk, technical, recommendation, and executive-summary inputs
  are unchanged by the migration.

- [ ] **Step 3: Run final gates**

Run report quality/source/prose checks on every new report, the complete focused
suite, `bash tools/ci_grep_gates.sh`, `git diff --check`, and markdownlint on all
new workflow notes.

- [ ] **Step 4: Finalize implementation notes**

Record commits/files, Batch A and final runtime delta, requirement-test matrix,
four-sample non-stale evidence, family/anchor counts, adapter removal and active
v1 count, all quality/source/citation/prose/CI results, blocker/warning/deviation,
and whether External Producer v2 may begin design.

- [ ] **Step 5: Commit final notes only**

```bash
git add docs/agent_workflow/2026-07-11-annual-producer-v2-claude-notes.md
git commit -m "docs: record annual producer v2 acceptance"
```

## Requirement-Test Matrix

| Requirement | Primary evidence |
| --- | --- |
| Five canonical families | Task 1 constants; Task 2 family fixtures |
| Single-family ownership | Task 2 ambiguous signal test |
| Source substring/order | Task 2 positional SourceUnit test |
| Atomic fact retention | Task 2 sparse atomic test |
| Complete argument preference | Task 2 ranking test |
| No source-unit reuse | Task 2 ownership invariant test |
| Same block, distinct arguments | Task 2 non-overlapping two-card test |
| Semantic novelty | Task 2 distinct product/period test |
| Candidate explosion | Task 2 invariant-error test |
| No canonical count cap | Tasks 2–6, >12 end-to-end |
| LLM budget isolation | Tasks 3–4 pack/item tests |
| Direct family propagation | Tasks 4–5 memo/snapshot tests |
| 4.4 completeness boundary | Task 5 atomic/complete tests |
| V1 migration/removal | Tasks 3, 7, and 8 |
| Formal-thin/formal-medium completeness | Task 5 shared renderer test |
| Citation/source hygiene | Tasks 6 and 9 report gates |
| No business-path regression | Tasks 4, 6, and 9 invariants |
| Runtime reduction | Tasks 6 and 8 line audits |

## Completion Contract

Implementation is complete only when Batch A and Batch B both pass, the v1
adapter is gone, no canonical annual count cap remains, final runtime reduction
is at least 80 lines, all four real samples pass their applicable acceptance,
and implementation notes contain evidence for every matrix row.
