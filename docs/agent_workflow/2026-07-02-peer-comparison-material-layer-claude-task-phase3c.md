# 2026-07-02 Peer Comparison Material Layer — Phase 3c Claude Task

## Goal

Integrate the Phase 3b peer comparison material pack into `KnowledgeSynthesizer` prompts for 4.1/4.2 only, using deterministic hard filtering before prompt construction.

This is the first phase that touches LLM prompt inputs. Keep the change narrow, heavily tested, and do not alter scoring/risk/technical logic.

## Prior State

Committed prerequisites:

- Phase 3a commit: `1758c6e feat: wire config-first peer comparison inputs`
- Phase 3b commit: `078f745 feat: add peer comparison material gates`

Phase 3b already provides:

- `scripts/utils/peer_comparison_material.py`
  - `build_peer_comparison_material(...)`
  - `filter_peer_rows_for_prompt(material)`
- `ctx["peer_comparison_material"]`
- `reports/<stock>_<date>_peer_comparison_material.json`
- quality gates for unsupported peer/superlative claims

## Scope

Allowed to modify:

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `tests/utils/test_knowledge_synthesizer.py`
- `tests/reporter/test_report_quality.py` only if an existing peer gate needs a narrow regression fixture
- `docs/agent_workflow/2026-07-02-peer-comparison-material-layer-phase3c-claude-notes.md`

Do not modify:

- `scripts/utils/peer_comparison_material.py` unless a tiny bug is found in its Phase 3b API contract
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/report_quality.py` unless a Phase 3c regression test proves a necessary narrow fix
- scoring/risk/technical modules
- Xueqiu/Chrome/CDP/Playwright/fetcher code
- report markdown by hand

Natural report output from a smoke run is allowed, but do not hand-edit it.

## Required Behavior

### 1. Pass peer material into `KnowledgeSynthesizer`

In `synthesis_skills.py`, after building peer material:

```python
peer_material = build_peer_comparison_material(...)
ctx.set("peer_comparison_material", peer_material)
```

When constructing `all_data` for `KnowledgeSynthesizer.synthesize(...)`, include:

```python
all_data["peer_comparison_material"] = peer_material
```

Only pass the existing `peer_material` object; do not rebuild it inside `KnowledgeSynthesizer`.

### 2. Extend `KnowledgeSynthesizer` signatures safely

Modify:

```python
KnowledgeSynthesizer.synthesize(...)
KnowledgeSynthesizer._synthesize_theme(...)
KnowledgeSynthesizer._build_prompt(...)
```

to accept optional `peer_comparison_material`.

Keep backward compatibility:

- existing callers without peer material must continue working;
- existing tests that spy on `_build_prompt` may need optional parameter handling;
- no call should require peer material.

### 3. Prompt appendices only for 4.1/4.2

Peer appendix is allowed only for theme keys:

- `industry_logic` (final 4.1)
- `fundamentals` (final 4.2)
- `valuation_debate` (final 4.2)

Peer appendix must not be included in:

- `funding_sentiment`
- `events_catalysts`
- core fact extraction prompt
- legacy `SynthesisSkill._build_prompt(...)` path unless the tests explicitly prove it is safe
- 4.4 narrative composer
- scoring/risk engine

### 4. Hard filter before prompt construction

Use `filter_peer_rows_for_prompt(material)` before formatting any appendix.

Rules:

- rows with `confidence < 0.50` must not appear in any prompt;
- rows with `0.50 <= confidence < 0.70` may appear only as dimension/peer/source context:
  - no `comparison`
  - no `target_value`
  - no `peer_value`
  - no numeric spread
- rows with `confidence >= 0.70` may include comparison/numeric values/source refs.

This is an input filter, not just a prompt instruction.

### 5. Appendix format

Add a compact non-citable appendix after numbered sources and before claim verification / previous topic ledger.

Suggested heading:

```text
同行对比材料（正式/指标来源，非新增引用）
```

Appendix rules:

- state that it is not a new citation source and must not produce new `[^n]` citations;
- list at most 4 rows for `industry_logic`;
- list at most 3 rows for `fundamentals` and `valuation_debate`;
- include source refs as plain text, e.g. `来源: 指标:competitor_metrics`;
- for high-confidence rows, include metric/comparison compactly;
- for context-only rows, include only dimension/peer/source labels.

Example high-confidence row:

```text
- 盈利能力 | 复旦微电 vs 紫光国微 | gross_margin: 55.3% vs 52.6% | 毛利率高于紫光国微2.7% | confidence=0.85 | 来源: 指标:competitor_metrics
```

Example context-only row:

```text
- 盈利能力 | peer=紫光国微 | metric=gross_margin | context_only | confidence=0.60 | 来源: 行业资讯:...
```

### 6. Prompt wording constraints

Append a short usage rule near the appendix:

```text
使用规则：
- 只能基于 claim_eligible 行写“高于/低于/接近/优于/弱于”等相对判断。
- context_only 行只能写成“后续可跟踪的对比线索”，不能写成已确认优劣。
- 不得把同行材料写入 4.3 资金面/催化剂。
- 不得引用雪球/知乎/微信/精选外部来支撑 4.1/4.2 同行结论。
```

Do not loosen existing topic ownership constraints.

## Tests

Use TDD. Add failing tests first.

### `tests/utils/test_knowledge_synthesizer.py`

Add tests:

1. `test_peer_appendix_included_for_industry_logic`
   - build prompt for `industry_logic` with peer material;
   - assert heading appears;
   - assert high-confidence comparison appears;
   - assert source ref appears;
   - assert phrase `非新增引用` appears.

2. `test_peer_appendix_included_for_fundamentals_and_valuation_only`
   - build prompts for `fundamentals`, `valuation_debate`, `funding_sentiment`, `events_catalysts`;
   - assert appendix appears only in the first two.

3. `test_peer_appendix_hard_filters_low_confidence_rows`
   - peer material includes a row with `confidence=0.40`;
   - assert peer name/comparison from that row do not appear in prompt.

4. `test_peer_appendix_strips_context_only_comparisons`
   - peer material includes a row with `confidence=0.60`, `comparison`, `target_value`, `peer_value`;
   - assert prompt contains dimension/peer/source;
   - assert prompt does not contain `comparison`, `target_value`, `peer_value`, or numeric values.

5. `test_synthesize_passes_peer_material_to_build_prompt`
   - similar to existing `test_synthesize_passes_context_to_build_prompt`;
   - spy on `_build_prompt`;
   - assert the same peer material object is passed.

6. `test_core_fact_extraction_prompt_does_not_include_peer_appendix`
   - if easy, spy `extract_core_facts` or `_call_llm` in core fact extraction;
   - assert peer appendix heading is not in core fact extraction prompt.

### Report smoke expectations

After implementation and tests, run Fudan smoke if focused tests pass:

```bash
set -a; . ./.env; set +a
python3 scripts/run_stock_report.py --stock 复旦微电 --no-pdf
python3 scripts/check_report_quality.py reports/复旦微电_20260702.md
python3 scripts/check_report_prose_quality.py reports/复旦微电_20260702.md
python3 scripts/check_report_source_boundary.py reports/复旦微电_20260702.md
```

Inspect:

- 4.1/4.2 should now include a small amount of supported peer comparison if LLM uses it;
- 4.3 must not include peer appendix concepts unless already supported by its own formal sources;
- no peer table bloat;
- no 4.4/social leakage into 4.1/4.2.

Run one regression stock if time allows:

```bash
python3 scripts/run_stock_report.py --stock 圣邦股份 --no-pdf
python3 scripts/check_report_quality.py reports/圣邦股份_20260702.md
python3 scripts/check_report_source_boundary.py reports/圣邦股份_20260702.md
```

If running the full report is too slow, report that and provide focused tests only.

## Verification Commands

Always run:

```bash
PYTHONPATH=/Users/erichan/testsnow/scripts:/Users/erichan/testsnow/scripts/utils python3 -m pytest tests/utils/test_knowledge_synthesizer.py tests/utils/test_peer_comparison_material.py tests/reporter/test_report_quality.py -q
PYTHONPATH=/Users/erichan/testsnow/scripts:/Users/erichan/testsnow/scripts/utils python3 -m pytest tests/reporter/test_peer_config.py tests/reporter/test_data_fetcher_peers.py tests/reporter/test_data_skills.py tests/reporter/test_valuation_renderer.py tests/reporter/test_stock_reporter_source_intake_config.py -q
bash tools/ci_grep_gates.sh
git diff --check
```

## Stop Conditions

Stop and report instead of expanding scope if:

- implementation requires changing renderer structure;
- peer appendix appears in 4.3/funding/catalyst prompts;
- peer material leaks into scoring/risk/core facts;
- the report becomes dominated by peer tables;
- Fudan report fails quality gates due to false-positive peer checks;
- implementation requires new data fetching or social sources.

## Completion Notes

Write notes to:

```text
docs/agent_workflow/2026-07-02-peer-comparison-material-layer-phase3c-claude-notes.md
```

Include:

- files changed;
- requirement-test matrix;
- exact test commands/results;
- smoke report paths if run;
- whether 4.1/4.2 used peer material;
- confirmation that 4.3/4.4/scoring/risk/core facts did not receive peer appendix;
- blocker/warning/deviation;
- final `git status --short`.
