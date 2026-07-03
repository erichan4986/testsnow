# Batch C Notes — Formal Financial Fact Pack

## Goal

Fix the pipeline cause behind 4.2 writing missing/incorrect financial facts:

- prevent official filing facts from being displayed as misleading small `万元` amounts in report-facing core facts;
- feed formal revenue/profit/cash-flow facts into the 4.2 synthesis prompt only;
- keep computation-oriented normalized values unchanged so derived risk metrics continue to work.

## Changes

- `scripts/utils/periodic_report_structured_facts.py`
  - Added `display_value` for `periodic_report_filing_fact` rows.
  - `filing_facts_to_core_facts()` now prefers `display_value` for report-facing data.
  - Normalized values remain in `万元`; display values render as `亿元`.

- `scripts/utils/report_skills/synthesis_skills.py`
  - Builds `formal_financial_fact_pack.v1` from `periodic_report_filing_core_facts`.
  - Passes the pack into `KnowledgeSynthesizer`.
  - Stores the pack on `ctx["formal_financial_fact_pack"]` when facts exist.

- `scripts/utils/knowledge_synthesizer.py`
  - Accepts `formal_financial_fact_pack`.
  - Appends it only to the `fundamentals` prompt, corresponding to final report section 4.2.
  - The appendix says it is not a new citation source and must not generate new `[^n]` IDs.

## Prompt Sample

```text
正式财务事实包（仅供4.2使用，非新增引用）

使用规则：
- 这些数字来自公告/年报结构化事实，可用于修正 4.2 的营收、利润、现金流基础表述。
- 不得为本附录生成新的 [^n] 引用编号；引用仍使用正文信息来源中的公告/年报来源。
- 若本附录已有营业收入或归母净利润，不得写“未提供营收/利润数据”。
- 订单、客户、费用率、指引等未在本附录出现的指标，可以保持“未披露/未提供”。

- 营业收入: 39.82亿元（2025年annual，periodic_report_filing_fact）
- 归母净利润: 2.32亿元（2025年annual，periodic_report_filing_fact）
```

## Requirement-Test Matrix

| Requirement | Test |
| --- | --- |
| Large filing facts display as `亿元` in core facts | `tests/utils/test_periodic_report_structured_facts.py::test_core_facts_display_large_financial_amounts_in_yi_unit` |
| Formal financial fact pack appears only in 4.2/fundamentals prompt | `tests/utils/test_knowledge_synthesizer.py::test_financial_fact_pack_is_appended_only_to_fundamentals_prompt` |
| SynthesisSkill passes the fact pack to KnowledgeSynthesizer | `tests/reporter/test_synthesis_skills.py::test_synthesis_skill_passes_formal_financial_fact_pack_to_synthesizer` |
| Existing periodic report, synthesis, source filtering, renderer and quality gates remain green | Focused suites below |

## Verification

- `python3 -m pytest tests/utils/test_periodic_report_structured_facts.py tests/utils/test_knowledge_synthesizer.py tests/reporter/test_synthesis_skills.py -q`  
  Result: `119 passed`
- `python3 -m pytest tests/reporter/test_report_quality.py tests/reporter/test_stock_reporter_source_intake_config.py tests/reporter/test_assembly_skills.py tests/reporter/test_deep_analysis_renderer.py tests/utils/test_source_direct_relevance.py -q`  
  Result: `122 passed`
- `python3 -m pytest tests/utils/test_periodic_report_required_financial_metrics.py tests/utils/test_periodic_report_structured_facts.py -q`  
  Result: `35 passed`
- `python3 -m pytest tests/reporter/test_synthesis_skills.py tests/utils/test_knowledge_synthesizer.py -q`  
  Result: `108 passed`
- `bash tools/ci_grep_gates.sh`  
  Result: `ci_grep_gates: all gates passed`
- `git diff --check`  
  Result: clean

## Deviations

- Did not regenerate `reports/复旦微电_20260702.md`; this batch fixes pipeline behavior and tests. A natural report rerun should be done after Batch E or final batch aggregation.
- Did not alter scoring, technical indicators, source collection, or 4.4 display-only logic.
