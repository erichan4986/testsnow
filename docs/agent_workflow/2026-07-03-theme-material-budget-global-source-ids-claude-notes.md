# Theme Material Budget with Global Source IDs — Implementation Notes

Date: 2026-07-03

## Files Changed

Runtime:

- `scripts/utils/source_direct_relevance.py` — added shared `OPERATING_VARIABLE_TERMS` constant.
- `scripts/utils/report_quality.py` — imports `OPERATING_VARIABLE_TERMS` from `source_direct_relevance.py`; removed local duplicate definition.
- `scripts/utils/knowledge_synthesizer.py` — added `_build_theme_material_budget()`, replaced double filtering with precomputed `source_rows`, switched prompt source numbering to global ids, made appendix ordering budget-driven, added supply-chain disclosure-insufficient guard.
- `scripts/utils/report_skills/synthesis_skills.py` — `_build_synthesis_items()` now keeps raw `fundflow` rows when `fundflow_material_pack` has rows.
- `scripts/utils/curated_external_viewpoint_narrative.py` — `_default_prompt()` requires `reasoning_cards`; `heuristic_narrative_composer()` emits `reasoning_cards`.

Tests:

- `tests/utils/test_knowledge_synthesizer.py` — updated existing `_build_prompt()` callers to the new signature/budget path; added 7 focused tests for the new behavior.
- `tests/reporter/test_synthesis_skills.py` — updated existing fundflow test for the new preservation behavior; added `test_fundflow_pack_keeps_citable_fundflow_sources`.
- `tests/utils/test_curated_external_viewpoint_narrative.py` — added 2 focused tests for reasoning-cards producer schema.

## Runtime Net Line Estimate

From `git diff --stat` across runtime files:

- `knowledge_synthesizer.py`: +189 / -? (net addition is the bulk)
- `curated_external_viewpoint_narrative.py`: +58 / -?
- `report_quality.py`: +23 / -?
- `synthesis_skills.py`: +8 / -?
- `source_direct_relevance.py`: +16 / -0

Aggregate: **~170 net added runtime lines** (well under the 250-line hard stop).

## Requirement-Test Matrix

| Requirement | Test |
|-------------|------|
| Global source-id budget in `KnowledgeSynthesizer` | `test_theme_budget_uses_global_source_refs` |
| `_build_prompt()` no longer refilters | `test_build_prompt_uses_precomputed_source_rows_without_refiltering` |
| Fundflow items isolated to `funding_sentiment` | `test_budget_routes_fundflow_items_only_to_funding_sentiment` |
| Raw fundflow sources preserved when pack exists | `test_fundflow_pack_keeps_citable_fundflow_sources` |
| Financial announcements do not create funding refs | `test_no_fundflow_no_funding_sentiment_even_with_financial_announcements` |
| Events/catalysts render when funding missing | `test_events_catalysts_can_render_when_funding_missing` |
| Fundamentals appendix order: explanation → fact → peer | `test_fundamentals_prompt_orders_explanation_before_fact_pack` |
| Supply-chain guard without operating variables | `test_supply_chain_state_blocks_generic_position_without_operating_variables` |
| 4.4 default prompt requires `reasoning_cards` | `test_default_viewpoint_narrative_prompt_requires_reasoning_cards` |
| Heuristic composer emits `reasoning_cards` | `test_heuristic_narrative_composer_emits_reasoning_cards` |

## Test Results

Focused tests:

```bash
python3 -m pytest tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py tests/utils/test_curated_external_viewpoint_narrative.py tests/reporter/test_report_quality.py -q
# 181 passed in 2.93s
```

Broader relevant suite:

```bash
python3 -m pytest tests/utils/test_periodic_report_explanation_pack.py tests/reporter/test_periodic_report_fulltext_intake_skill.py tests/utils/test_curated_external_viewpoint_narrative.py tests/reporter/test_synthesis_skills.py tests/reporter/test_deep_analysis_renderer.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_report_quality.py tests/utils/test_fundflow_material.py tests/reporter/test_technical_skills_contract.py tests/utils/test_source_adapter.py -q
# 250 passed in 3.21s
```

Gates:

```bash
bash tools/ci_grep_gates.sh
# ci_grep_gates: all gates passed
```

```bash
git diff --check
# no output (clean)
```

## Blockers / Warnings / Deviations

- No renderer changes were made. `deep_analysis_renderer.py` was not touched.
- No new runtime modules or sidecars were added.
- No new `report_quality` warning families were added.
- No full report generation was run; no external websites were accessed; no Chrome/CDP/Playwright was started; `reports/` was not modified.
- Minor deviation: `_build_prompt()` retains a convenience fallback that accepts a bare `List[SynthesisItem]` as the third argument and converts it to `source_rows` with 1-based global ids. This keeps existing non-filtering tests passing without calling `_filter_items_for_theme()`. Filtering behavior tests explicitly build the budget and pass precomputed `source_rows`.

## Under 250 Runtime Lines?

Yes. Net runtime increase is approximately **170 lines**, below the 250-line hard stop.
