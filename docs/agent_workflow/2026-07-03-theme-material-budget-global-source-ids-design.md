# Theme Material Budget With Global Source IDs Design

Date: 2026-07-03

## Verdict

Proceed with a narrow replacement-oriented V2.

This phase fixes the routing and citation foundation for 4.1-4.4 without adding another large material layer. The goal is to replace duplicated theme filtering and local source numbering inside `KnowledgeSynthesizer`, not to build a new peer-business comparison system.

## Problem

The current pipeline has three coupled issues:

1. `KnowledgeSynthesizer.synthesize()` filters items by theme, then `_build_prompt()` filters the same item list again.
2. `_build_prompt()` renders each theme's filtered sources with local numbering starting at `[1]`.
3. `SynthesisSkill._fill_citation_metadata()` later resolves citations against the global `items[ref_id - 1]` list.

That means an LLM citation such as `[^2]` can refer to the second item in a theme-local prompt while metadata hydration treats it as the second item in the global source list. This is exactly the kind of hidden mismatch that can make source-boundary checks look green while citations point at the wrong evidence.

Separately:

- `synthesis_skills.py` currently drops raw `fundflow` items when `fundflow_material_pack` exists, leaving 4.3 without citable funding sources.
- `curated_external_viewpoint_narrative.py` supports `reasoning_cards` downstream, but the default producer prompt only requires `paragraphs`, so 4.4 still compresses long external reasoning into short paragraphs.

## Goals

1. Build one material budget per synthesis run inside `KnowledgeSynthesizer`.
2. Store source eligibility as global one-based source ids.
3. Render prompt sources with the same global ids used by citation hydration.
4. Keep existing packs as non-citable appendices.
5. Preserve real fundflow source rows when a fundflow pack is available.
6. Make 4.4 narrative producer emit `reasoning_cards`.
7. Keep runtime code net increase under 250 lines.

## Non-Goals

- Do not add `section_materials.py` or a new sidecar.
- Do not expand `SynthesisSkill` into another section-routing owner.
- Do not add a `peer_business_comparison_pack`.
- Do not move social/Zhihu/Xueqiu material into canonical 4.1-4.3.
- Do not add more warning families to `report_quality.py`.
- Do not infer reasoning cards from paragraphs in the renderer.
- Do not implement multi-hop industry chain reasoning.

## Design

### 1. Single Routing Owner

`KnowledgeSynthesizer` becomes the only owner of canonical theme routing for LLM prompt sources.

`SynthesisSkill` continues to pass:

```python
all_data = {
    "items": items,
    "stock_config": stock_config,
    "formal_financial_fact_pack": fact_pack,
    "formal_financial_explanation_pack": explanation_pack,
    "peer_comparison_material": peer_material,
    "fundflow_material_pack": fundflow_pack,
}
```

It must not construct 4.1/4.2/4.3 section materials.

### 2. Theme Material Budget

Add an internal method:

```python
def _build_theme_material_budget(
    self,
    stock_name: str,
    items: list[SynthesisItem],
    all_data: dict,
) -> dict:
    ...
```

The returned shape is internal and compact:

```python
{
    "schema": "theme_material_budget.v1",
    "source_ref_base": "items_global_1_based",
    "themes": {
        "industry_logic": {
            "source_refs": [2, 5, 8],
            "supply_chain_state": {
                "has_operating_variable": False,
                "matched_terms": [],
            },
        },
        "fundamentals": {
            "source_refs": [1, 3, 4],
            "appendices": [
                "formal_financial_explanation_pack",
                "formal_financial_fact_pack",
                "peer_metrics_only",
            ],
        },
        "valuation_debate": {
            "source_refs": [3, 4],
            "appendices": ["peer_metrics_only"],
        },
        "funding_sentiment": {
            "source_refs": [9, 10],
            "requires": "fundflow_or_position_or_trading_sentiment",
            "skip_reason": "",
        },
        "events_catalysts": {
            "source_refs": [1, 6, 7],
        },
    },
}
```

Only ids are stored. The budget does not duplicate source text.

### 3. Prompt Source Rows

`synthesize()` should build the budget once:

```python
budget = self._build_theme_material_budget(stock_name, items, all_data)
```

For each theme:

```python
source_refs = budget["themes"][theme_key]["source_refs"]
source_rows = [(ref_id, items[ref_id - 1]) for ref_id in source_refs]
```

`_build_prompt()` receives `source_rows` and must not call `_filter_items_for_theme()` again.

Prompt source lines use global ids:

```python
for ref_id, item in source_rows:
    source_lines.append(format_synthesis_source_line(ref_id, item))
```

If the only eligible funding materials are missing, `funding_sentiment` should be skipped or given a controlled degradation prompt; it must not use financial announcements to infer fundflow.

### 4. Pack Ordering

Packs remain non-citable appendices. They must not generate new source ids.

For `fundamentals`, append in this order:

1. `formal_financial_explanation_pack`
2. `formal_financial_fact_pack`
3. `peer_comparison_material`

This makes management explanation the primary writing cue and financial figures only the anchor.

### 5. Fundflow Source Preservation

In `SynthesisSkill._build_synthesis_items()`:

- If `fundflow_material_pack` has rows, keep `stock_raw["fundflow"]` in `adapt_all()` so the prompt has citable fundflow rows.
- If no pack rows exist, do not let pseudo-fundflow raw rows enter `funding_sentiment`.

This is simpler than generating synthetic citable fundflow items.

### 6. 4.4 Reasoning Cards Producer

Change only the producer side:

- `_default_prompt()` must require both `paragraphs` and `reasoning_cards`.
- `heuristic_narrative_composer()` must emit `reasoning_cards` with the expected schema when source claims contain enough fields.

Renderer behavior should remain unchanged unless a focused test exposes a bug.

## Expected Report Impact

| Area | Expected Improvement | Limit |
| --- | --- | --- |
| 4.2 annual-report explanation | The prompt should prioritize explanations like "主要系安全与识别芯片、智能电表芯片及 FPGA 销售额增加所致" | Does not guarantee perfect prose every run |
| 4.1 product/peer comparison | Prevents false depth and keeps peer metrics citable/aligned | Does not create hard product-level peer analysis |
| 4.4 reasoning cards | New narrative JSON can display author reasoning, numbers, assumptions and counterpoints | Requires regenerating or updating narrative JSON |
| 4.1 supply-chain variables | No-evidence supply-chain prose should degrade to disclosure-insufficient language | Does not discover new supply-chain facts |
| Citations | LLM source ids and metadata hydration use the same global ids | Must be tested with sparse theme source refs |

## Failure Modes And Tests

### FM1: Local source numbering remains

Symptom: prompt for 4.1 shows `[1]` even though the source is global item 5.

Test: `test_theme_budget_uses_global_source_refs`.

### FM2: Double filtering still exists

Symptom: `_build_prompt()` silently recomputes theme items and diverges from `synthesize()`.

Test: `test_build_prompt_uses_precomputed_source_rows_without_refiltering`.

### FM3: Fundflow pack exists but no citable fundflow source

Symptom: 4.3 can cite announcements but not actual fundflow rows.

Test: `test_fundflow_pack_keeps_citable_fundflow_sources`.

### FM4: No fundflow data but financial announcements enter funding prompt

Symptom: LLM writes "营收下降压制主动买盘".

Test: `test_no_fundflow_no_funding_sentiment_even_with_financial_announcements`.

### FM5: Events/catalysts disappear when funding is missing

Symptom: 4.3 vanishes entirely instead of preserving formal event timeline.

Test: `test_events_catalysts_can_render_when_funding_missing`.

### FM6: Explanation pack loses priority

Symptom: 4.2 repeats revenue/profit tables and ignores management explanations.

Test: `test_fundamentals_prompt_orders_explanation_before_fact_pack`.

### FM7: Supply-chain prose invents unsupported specifics

Symptom: 4.1 writes specific suppliers or supply-chain position with no operating variables.

Test: `test_supply_chain_state_blocks_generic_position_without_operating_variables`.

### FM8: Producer still emits paragraph-only 4.4 JSON

Symptom: `reasoning_cards` absent in default LLM prompt or heuristic fallback.

Tests:

- `test_default_viewpoint_narrative_prompt_requires_reasoning_cards`
- `test_heuristic_narrative_composer_emits_reasoning_cards`

## Line Budget

Runtime target:

- `knowledge_synthesizer.py`: +70 to +120
- `synthesis_skills.py`: +5 to +20
- `curated_external_viewpoint_narrative.py`: +35 to +60
- `deep_analysis_renderer.py`: 0
- `report_quality.py`: 0

Hard stop: runtime net increase over 250 lines.

## Stop Conditions

Stop and redesign if any implementation requires:

- a new `section_materials.py`;
- a section-material sidecar;
- moving social/external material into canonical 4.1-4.3;
- a new peer business comparison pack;
- renderer-inferred reasoning cards;
- new report-quality rule families;
- local per-theme source renumbering;
- runtime net increase over 250 lines.
