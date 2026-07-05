# Claude Task — Theme Material Budget With Global Source IDs

You are Claude Code working in `/Users/erichan/testsnow`.

## Goal

Implement the narrow V2 replacement:

- build one global source-id theme material budget inside `KnowledgeSynthesizer`;
- remove double filtering and local source renumbering;
- preserve raw fundflow rows when a fundflow pack exists;
- make 4.4 narrative producer require and emit `reasoning_cards`;
- keep runtime net increase under 250 lines.

## Read First

- `docs/agent_workflow/2026-07-03-theme-material-budget-global-source-ids-design.md`
- `docs/agent_workflow/2026-07-03-theme-material-budget-global-source-ids-design-delta.md`
- `docs/agent_workflow/2026-07-03-theme-material-budget-global-source-ids-claude-review-round1-notes.md`

## Allowed Files

Runtime:

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/curated_external_viewpoint_narrative.py`
- `scripts/utils/source_direct_relevance.py`
- `scripts/utils/report_quality.py` only to import/reuse `OPERATING_VARIABLE_TERMS`; do not add new quality rules

Tests:

- `tests/utils/test_knowledge_synthesizer.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/utils/test_curated_external_viewpoint_narrative.py`
- `tests/reporter/test_report_quality.py` only if needed for the shared term import regression

Notes:

- `docs/agent_workflow/2026-07-03-theme-material-budget-global-source-ids-claude-notes.md`

## Forbidden

- Do not add a new runtime module such as `section_materials.py`.
- Do not add a sidecar.
- Do not modify `deep_analysis_renderer.py` unless a focused test proves an existing card-rendering bug. If that happens, stop and report before editing.
- Do not add new warning families to `report_quality.py`.
- Do not implement `peer_business_comparison_pack`.
- Do not move social/Zhihu/Xueqiu/微信/精选外部 material into canonical 4.1-4.3.
- Do not run report generation.
- Do not access external websites.
- Do not start Chrome/CDP/Playwright.
- Do not modify `reports/`.

## Implementation Requirements

### 1. Global Source-ID Budget

In `KnowledgeSynthesizer`, add an internal budget builder:

```python
def _build_theme_material_budget(
    self,
    stock_name: str,
    items: list[SynthesisItem],
    all_data: dict,
) -> dict:
    ...
```

Budget shape:

```python
{
    "schema": "theme_material_budget.v1",
    "source_ref_base": "items_global_1_based",
    "themes": {
        "industry_logic": {
            "source_refs": [...],
            "supply_chain_state": {
                "has_operating_variable": bool,
                "matched_terms": [...],
            },
            "appendices": ["peer_metrics_only"],
        },
        "fundamentals": {
            "source_refs": [...],
            "appendices": [
                "formal_financial_explanation_pack",
                "formal_financial_fact_pack",
                "peer_metrics_only",
            ],
        },
        "valuation_debate": {
            "source_refs": [...],
            "appendices": ["peer_metrics_only"],
        },
        "funding_sentiment": {
            "source_refs": [...],
            "requires": "fundflow_or_position_or_trading_sentiment",
            "skip_reason": "",
            "appendices": ["fundflow_material_pack"],
        },
        "events_catalysts": {
            "source_refs": [...],
            "appendices": [],
        },
    },
}
```

Use global one-based ids: `ref_id == items index + 1`.

### 2. Replace Double Filtering

`synthesize()` should:

1. build the budget once;
2. read `budget["themes"][theme_key]["source_refs"]`;
3. build `source_rows = [(ref_id, items[ref_id - 1]), ...]`;
4. pass `source_rows` and the theme budget into `_synthesize_theme()` / `_build_prompt()`.

`_build_prompt()` must not call `_filter_items_for_theme()` anymore.

Prompt source lines must use global ids:

```python
for ref_id, item in source_rows:
    source_lines.append(format_synthesis_source_line(ref_id, item))
```

### 3. Strict Theme Isolation

Fundflow/funding items:

- may enter `funding_sentiment`;
- must not enter `events_catalysts`;
- must not enter 4.1/4.2 themes.

Events/catalysts:

- should continue to render formal company events even when funding data is missing.

If `funding_sentiment` has no eligible fundflow/position/trading-sentiment refs, skip it with the existing insufficient-material behavior or a controlled empty result. Do not let financial announcements substitute as funding evidence.

### 4. Shared Operating Variable Terms

Move the operating-variable term tuple from `report_quality.py` into `source_direct_relevance.py` as:

```python
OPERATING_VARIABLE_TERMS = (
    "供应商", "客户", "产能", "供需", "库存", "存货",
    "订单", "价格", "交期", "采购", "备货", "交付", "产量",
)
```

Then:

- `report_quality.py` imports this constant and keeps existing behavior.
- `KnowledgeSynthesizer` uses this constant for `supply_chain_state`.

### 5. Appendix Ordering From Budget

`_build_prompt()` must append non-citable packs according to `theme_budget["appendices"]`.

For `fundamentals`, ensure explanation pack appears before fact pack.

### 6. Fundflow Raw Source Preservation

In `SynthesisSkill._build_synthesis_items()`:

- if `fundflow_material_pack` has rows, pass `stock_raw.get("fundflow", [])` into `adapt_all()`;
- if it has no rows, current conservative behavior may exclude raw fundflow rows.

The budget should still be the final authority for whether those rows enter `funding_sentiment`.

### 7. 4.4 Reasoning Cards Producer

In `curated_external_viewpoint_narrative.py`:

- update `_default_prompt()` to require JSON with both `paragraphs` and `reasoning_cards`;
- update `heuristic_narrative_composer()` so it emits `reasoning_cards` instead of paragraph-only output when possible;
- do not infer cards in the renderer.

`reasoning_cards` entries should use existing normalizer-compatible fields:

```json
{
  "claim_id": "...",
  "display_topic": "...",
  "claim": "...",
  "source_excerpt": "...",
  "reasoning_steps": ["..."],
  "numbers_used": ["..."],
  "assumptions": ["..."],
  "counterpoints": ["..."],
  "verification_need": "..."
}
```

## Required Tests

Add focused tests. Names can vary, but coverage must include:

1. `test_theme_budget_uses_global_source_refs`
   - Build sparse global items.
   - Verify a theme source line uses the global id, not local `[1]`.

2. `test_build_prompt_uses_precomputed_source_rows_without_refiltering`
   - Monkeypatch or fixture `_filter_items_for_theme`.
   - Verify `_build_prompt()` no longer calls it.

3. `test_budget_routes_fundflow_items_only_to_funding_sentiment`
   - Fundflow source appears in funding theme refs.
   - It does not appear in events/catalysts or 4.1/4.2 refs.

4. `test_fundflow_pack_keeps_citable_fundflow_sources`
   - With fundflow pack rows, `_build_synthesis_items()` keeps raw fundflow items as citable sources.

5. `test_no_fundflow_no_funding_sentiment_even_with_financial_announcements`
   - Financial announcements must not produce funding source refs.

6. `test_events_catalysts_can_render_when_funding_missing`
   - Formal company event refs remain available when funding refs are empty.

7. `test_fundamentals_prompt_orders_explanation_before_fact_pack`
   - Explanation appendix appears before fact appendix.

8. `test_supply_chain_state_blocks_generic_position_without_operating_variables`
   - No operating terms -> `has_operating_variable` false and prompt includes a disclosure-insufficient instruction.

9. `test_default_viewpoint_narrative_prompt_requires_reasoning_cards`
   - Default prompt schema contains `reasoning_cards`.

10. `test_heuristic_narrative_composer_emits_reasoning_cards`
   - Heuristic composer output includes non-empty `reasoning_cards` for usable claims.

## Verification Commands

Run focused tests:

```bash
python3 -m pytest tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py tests/utils/test_curated_external_viewpoint_narrative.py tests/reporter/test_report_quality.py -q
```

Run the current broader relevant suite:

```bash
python3 -m pytest tests/utils/test_periodic_report_explanation_pack.py tests/reporter/test_periodic_report_fulltext_intake_skill.py tests/utils/test_curated_external_viewpoint_narrative.py tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_report_quality.py tests/utils/test_fundflow_material.py tests/reporter/test_technical_skills_contract.py tests/utils/test_source_adapter.py -q
```

Run gates:

```bash
bash tools/ci_grep_gates.sh
git diff --check
```

Do not run a full report in this task.

## Notes Output

Write:

`docs/agent_workflow/2026-07-03-theme-material-budget-global-source-ids-claude-notes.md`

Include:

- files changed;
- runtime net line estimate;
- requirement-test matrix;
- test results;
- gates results;
- blocker/warning/deviation;
- whether implementation stayed below 250 runtime lines.

## Stop Conditions

Stop and report if:

- runtime net increase appears likely to exceed 250 lines;
- implementation needs a new runtime module;
- implementation needs renderer changes;
- implementation needs new report_quality warning families;
- tests reveal external/social material entering canonical 4.1-4.3;
- prompt source numbering remains local per theme;
- full report generation or network access becomes necessary.
