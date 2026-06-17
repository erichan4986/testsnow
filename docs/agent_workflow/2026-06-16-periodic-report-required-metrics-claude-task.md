# Claude Task: Periodic Report Required Metrics

Date: 2026-06-16

## Goal

Implement deterministic required operating metrics for the experimental full-text periodic-report analysis path.

The concrete defect: Yingjixin 2025 annual-report fulltext output omitted mandatory product gross-margin and inventory metrics even though the report text and evidence blocks contained them.

The fix must make these hard metrics deterministic and visible before LLM narrative.

## Read First

- `docs/agent_workflow/2026-06-16-periodic-report-required-metrics-design.md`
- Focus on:
  - `## Codex R2 Design Revision`
  - `## Round 2 Feedback`
  - `## Codex Final Implementation Deltas`
- Existing helpers:
  - `scripts/utils/periodic_report_evidence_pack.py`
  - `scripts/utils/periodic_report_fulltext_llm_analysis.py`
- Existing tests:
  - `tests/utils/test_periodic_report_evidence_pack.py`
  - `tests/utils/test_periodic_report_fulltext_llm_analysis.py`

## Allowed Files

- `scripts/utils/periodic_report_fulltext_llm_analysis.py`
- New helper: `scripts/utils/periodic_report_required_metrics.py`
- `tests/utils/test_periodic_report_fulltext_llm_analysis.py`
- New tests: `tests/utils/test_periodic_report_required_metrics.py`
- Notes file: `docs/agent_workflow/2026-06-16-periodic-report-required-metrics-claude-notes.md`

## Forbidden Files

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/**`
- `scripts/utils/reporter/**`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/periodic_report_extractor.py`
- `scripts/utils/periodic_report_llm_analysis.py`
- `scripts/utils/periodic_report_llm_analysis_v2.py`
- `config/**`
- `knowledge/**`
- `reports/**`
- `data/raw/**`

If implementation requires changing a forbidden file, stop and report why.

## Required Behavior

### 1. New deterministic metrics helper

Create `scripts/utils/periodic_report_required_metrics.py`.

It should expose:

```python
build_required_business_metrics(evidence_pack: dict, raw_text: str | None = None) -> dict
```

It must consume `build_periodic_report_evidence_pack(text)` blocks first. It may use bounded raw-text fallback only when evidence-pack blocks contain no relevant tables.

Relevant evidence-pack block usages:

- `segment_margin_table`
- `region_table`
- `segment_table`
- `production_sales_inventory_table`
- `customer_supplier_table`
- `supplier_concentration_table`

Return schema:

```python
{
    "schema_version": "periodic_report_required_metrics.v1",
    "source_pack_schema_version": "periodic_report_evidence_pack.v1",
    "segment_rows": [...],
    "region_rows": [...],
    "sales_mode_rows": [...],
    "inventory_rows": [...],
    "customer_concentration": {...},
    "supplier_concentration": {...},
    "tables": {...},
    "normalized_values": [...],
}
```

Follow row schemas and normalization rules in the design.

### 2. Prompt integration

Update `build_periodic_report_fulltext_prompt()` to accept:

```python
required_metrics: dict | None = None
```

Inject deterministic metrics into prompt as context only.

Do not add `required_business_metrics` to the LLM output schema.

Prompt must explicitly forbid evidence-pack ids in `judgment.evidence_refs`:

```text
禁止在 judgment.evidence_refs 中引用 segment_margin_table-0、production_sales_inventory_table-0、
customer_supplier_table-0 等 evidence-pack id。judgment.evidence_refs 只能使用 fulltext 块 id，
例如 fulltext-2-0、fulltext-2-3。
```

### 3. Validator integration

Update `validate_periodic_report_fulltext_output()` to accept:

```python
required_metrics: dict | None = None
```

Do not weaken no-fabrication globally.

Only allow exact normalized metric value matching:

- If `_check_fidelity()` fails due Jina spacing/unit normalization, a numeric token may pass only if its canonical form appears in `required_metrics["normalized_values"]`.
- Labels alone must not pass.
- Unknown refs such as `segment_margin_table-0` must still be rejected.

If this is too risky to implement cleanly, keep validator strict and document that LLM judgments may still drop metrics; deterministic renderer still solves visibility. Do not add a broad bypass.

### 4. Renderer integration

Update:

```python
render_periodic_report_fulltext_markdown(
    analysis: Dict[str, Any],
    *,
    required_metrics: Dict[str, Any] | None = None,
) -> str
```

Keep one-argument call backward-compatible.

Markdown order:

1. metadata block;
2. disclaimer;
3. `## 必备经营指标摘录`;
4. metrics tables;
5. six LLM sections.

If metrics are absent:

```markdown
## 必备经营指标摘录

未识别到可稳定结构化的分产品、库存、客户或供应商指标。
```

### 5. Empty fulltext analysis bug

If touching `periodic_report_fulltext_llm_analysis.py`, fix `_empty_fulltext_analysis()` if it returns the wrong schema or legacy fields. Keep the fix minimal and tested if practical.

## Required Tests

Use compact fixtures copied from `/tmp/yingjixin_2025_annual_jina.txt` and `/tmp/zhongjian_2025_annual_jina.txt`. Do not depend on `/tmp` files.

Add focused tests for:

1. `test_required_metrics_consumes_evidence_pack_blocks`
2. `test_extracts_yingjixin_segment_margin_rows_from_evidence_block`
3. `test_extracts_yingjixin_inventory_rows_from_evidence_block`
4. `test_extracts_yingjixin_customer_supplier_concentration_from_evidence_block`
5. `test_region_and_sales_mode_rows_for_yingjixin`
6. `test_required_metrics_preserve_original_units_and_normalized_values`
7. `test_normalized_values_canonical_form`
8. `test_required_metrics_handles_jina_spaced_numbers`
9. `test_required_metrics_handles_broken_product_names`
10. `test_required_metrics_table_presence_when_header_found_but_no_rows`
11. `test_table_presence_row_block_id_consistency`
12. `test_source_excerpt_bounded`
13. `test_prompt_injects_required_metrics_but_does_not_add_output_schema_field`
14. `test_validator_rejects_evidence_pack_id_in_judgment_refs`
15. `test_validator_rejects_fabricated_metric_value_not_in_required_metrics`
16. `test_renderer_prints_required_metrics_before_company_profile`
17. `test_renderer_empty_required_metrics_state`
18. `test_raw_text_fallback_extracts_metrics`
19. `test_zhongjian_required_metrics_regression`

## Yingjixin Acceptance Criteria

The deterministic metrics output and rendered Markdown must include:

- 电源管理类收入 `1,062,041,234.54` or `106,204.12 万元`, revenue YoY `12.44%`, gross margin `34.47%`, gross-margin change `+2.64pct`, inventory growth `51.80%`.
- 电池管理类收入 `202,758,468.19` or `20,275.85 万元`, revenue YoY `72.39%`, gross margin `38.83%`, gross-margin change `-1.72pct`, inventory growth `618.99%`.
- 数模混合 SoC 类收入 `337,194,197.68` or `33,719.42 万元`, revenue YoY `-0.83%`, gross margin `31.17%`, gross-margin change `-4.84pct`, inventory growth `61.04%`.
- 国内销售 `156,161.40 万元`, `+15.11%`; 国外销售 `4,050.44 万元`, `-11.30%`.
- 经销收入 `138,790.37 万元`, `+15.67%`; 直销收入 `21,421.47 万元`, `+5.83%`.
- 前五名客户销售额 `49,019.50 万元`,占比 `30.46%`; 第一大客户 `10,835.52 万元`,占比 `6.73%`.
- 前五名供应商采购额 `97,080.28 万元`,占比 `73.45%`; 第一大供应商 `43,030.34 万元`,占比 `32.56%`.

## Tests to Run

Focused:

```bash
python3 -m pytest tests/utils/test_periodic_report_required_metrics.py tests/utils/test_periodic_report_fulltext_llm_analysis.py -q
```

Related regression:

```bash
python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_llm_analysis.py tests/utils/test_periodic_report_llm_analysis_v2.py tests/utils/test_periodic_report_fulltext_llm_analysis.py -q
```

Do not run live LLM or network tests.

## Notes Output

Write implementation notes to:

`docs/agent_workflow/2026-06-16-periodic-report-required-metrics-claude-notes.md`

Include:

- files changed;
- tests run and results;
- whether Yingjixin required metrics are extracted;
- whether Zhongjian regression passes;
- any deviations;
- blockers.

## Stop Conditions

Stop and report if:

- you need to modify forbidden files;
- robust extraction requires industry-specific product keywords;
- validator changes require broad fidelity bypass;
- tests reveal unrelated broad failures;
- implementation needs network, LLM, Chrome/CDP, or report generation.
