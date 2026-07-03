# Batch B Direct-Only Source Relevance Implementation Notes

## Scope

Implemented Batch B only:

- Added deterministic direct-only source relevance classification.
- Wired `stock_config` from `SynthesisSkill` into `KnowledgeSynthesizer`.
- Applied direct-only filtering to 4.1 / 4.2 canonical theme prompts when `stock_config` is available.

No report entry was run. No financial fact pack, unit normalization, scoring, technical analysis, source collection, Xueqiu/CDP/Playwright, or generated report edits were made.

## Files Changed

| File | Change |
|---|---|
| `scripts/utils/source_direct_relevance.py` | New helper for `company_direct` / `direct_product` / `direct_peer` / `sector_background` classification and theme filtering. |
| `scripts/utils/knowledge_synthesizer.py` | Accepts optional `stock_config`; applies direct-only filtering to 4.1/4.2 prompts when config is present. |
| `scripts/utils/report_skills/synthesis_skills.py` | Passes `ctx["stock_config"]` into synthesizer `all_data`. |
| `tests/utils/test_source_direct_relevance.py` | New direct relevance unit tests. |
| `tests/utils/test_knowledge_synthesizer.py` | Added prompt filtering tests and updated spy signatures for `stock_config`. |
| `tests/reporter/test_synthesis_skills.py` | Added pipeline wiring test for `stock_config`. |

## Behavior

- MLCC sector/background material for 复旦微电 is filtered out of 4.1/4.2 when it explicitly says the company does not directly involve MLCC.
- Direct product material such as FPGA / MCU / EEPROM remains eligible.
- Direct peer material such as 紫光国微 / 安路科技 remains eligible for 4.1/4.2.
- If `product_exposure_terms` is missing, de-genericized `stock_config.keywords` can be used as fallback.
- Generic keywords such as `半导体` and `芯片` are not enough to keep a source item.
- No direct-only filtering is applied to legacy `_build_prompt()` calls without `stock_config`, preserving existing test compatibility.

## Red / Green

Initial focused test run failed because `source_direct_relevance.py` did not exist.

After adding the helper, one prompt test still failed: the MLCC item contained the word `FPGA` in a negated sentence and was incorrectly rescued as direct product. The classifier now treats `MLCC + 不直接涉及/无直接关系` as explicit unrelated-theme evidence and blocks it before product matching.

## Verification

```text
python3 -m pytest tests/utils/test_source_direct_relevance.py tests/utils/test_knowledge_synthesizer.py::test_industry_logic_prompt_filters_out_non_direct_sector_background_with_stock_config tests/utils/test_knowledge_synthesizer.py::test_fundamentals_prompt_uses_keywords_fallback_without_generic_terms tests/reporter/test_synthesis_skills.py::test_synthesis_skill_passes_stock_config_to_synthesizer -q
# 7 passed
```

```text
python3 -m pytest tests/utils/test_source_direct_relevance.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py -q
# 110 passed
```

```text
python3 -m pytest tests/reporter/test_report_quality.py tests/reporter/test_stock_reporter_source_intake_config.py tests/reporter/test_assembly_skills.py tests/reporter/test_deep_analysis_renderer.py -q
# 118 passed
```

```text
bash tools/ci_grep_gates.sh
# ci_grep_gates: all gates passed
```

```text
git diff --check
# clean
```

## Prompt Sample

Focused prompt test confirms the 4.1 prompt for 复旦微电:

- excludes `AI服务器带动 MLCC 需求增长`;
- excludes the negated `MLCC 技术路线` text;
- keeps `FPGA 行业研究报告`;
- keeps `紫光国微竞争格局`.

This verifies the LLM no longer receives the MLCC background item for canonical 4.1/4.2 synthesis under stock-config-aware runs.

## Blockers / Deviations

- Blockers: none.
- Deviations: none.
- Remaining work: Batch C financial fact pack and upstream unit normalization.
