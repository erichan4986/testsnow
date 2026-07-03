# Batch 1.5 + D Implementation Notes

## Scope

Implemented only the safe first slice:

- Batch 1.5 config completion for 复旦微电 / 中际旭创 / 圣邦股份.
- Batch D header config-first fallback.
- Batch D deep-analysis renderer controlled fallback for 4.1 / 4.2 / 4.3.

No Direct-Only filtering, financial fact pack, unit normalization, quality gates, LLM prompt, scoring, technical, Xueqiu, Chrome/CDP, or report-entry changes were made.

## Files Changed

| File | Change |
|---|---|
| `config/stocks.json` | Added `industry`, `competitors`, `peer_codes`, `product_exposure_terms` for pilot/regression stocks as needed. |
| `scripts/utils/report_skills/assembly_skills.py` | Header now reads `stock_config` first and falls back to `INDUSTRY_MAP/COMPETITOR_MAP`. |
| `scripts/utils/reporter/sections/deep_analysis_renderer.py` | 4.1 / 4.2 / 4.3 headings always render; empty sections use controlled fallback text. |
| `tests/reporter/test_stock_reporter_source_intake_config.py` | Added config coverage for direct relevance fields. |
| `tests/reporter/test_assembly_skills.py` | Added stock_config priority, constants fallback, and double-missing fallback tests. |
| `tests/reporter/test_deep_analysis_renderer.py` | Added controlled fallback tests for empty/mixed 4.1-4.3 inputs. |

## Requirement-Test Matrix

| Requirement | Test / Verification |
|---|---|
| 复旦微电 has direct product exposure and excludes MLCC | `test_fudan_microelectronics_config_present_and_wired` |
| 中际旭创 / 圣邦股份 have direct relevance config | `test_pilot_stocks_have_direct_relevance_config` |
| Header prefers `stock_config` over constants | `test_header_prefers_stock_config_industry_and_competitors` |
| Header falls back to constants | `test_header_falls_back_to_constants_when_stock_config_missing` |
| Unknown stock header renders dashes | `test_header_renders_dash_when_config_and_constants_missing` |
| Empty 4.1 / 4.2 / 4.3 still render controlled fallback | `test_deep_analysis_renders_controlled_fallbacks_for_empty_sections` |
| Funding-only 4.3 gets catalyst fallback | `test_deep_analysis_funding_only_renders_events_fallback` |
| Events-only 4.3 gets funding fallback | `test_deep_analysis_events_only_renders_funding_fallback` |
| 4.4 behavior remains unchanged | Existing curated external 4.4 renderer tests remained green in the focused suite. |

## Red / Green

Initial focused test run after writing tests failed as expected:

- Missing `product_exposure_terms` for 复旦微电.
- Missing `industry` for 中际旭创.
- Header ignored `stock_config`.
- DeepAnalysisRenderer omitted empty 4.1/4.3 and lacked mixed 4.3 fallback text.

After implementation, focused tests passed.

## Test Commands

```text
python3 -m pytest tests/reporter/test_stock_reporter_source_intake_config.py tests/reporter/test_assembly_skills.py tests/reporter/test_deep_analysis_renderer.py -q
# 87 passed
```

```text
bash tools/ci_grep_gates.sh
# ci_grep_gates: all gates passed
```

```text
git diff --check
# clean
```

```text
python3 -m json.tool config/stocks.json
# valid JSON
```

## 4.4 Display-Only Status

Unchanged. The implementation only changes 4.1-4.3 fallback rendering and header/config plumbing. Existing curated external 4.4 tests stayed green.

## Blockers / Deviations

- Blockers: none.
- Deviations: none.
- Report entry was not run, per task scope.

## Git Status Snapshot

Expected modified files:

- `config/stocks.json`
- `scripts/utils/report_skills/assembly_skills.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `tests/reporter/test_assembly_skills.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_stock_reporter_source_intake_config.py`

Expected untracked workflow docs and natural `reports/` output remain present.
