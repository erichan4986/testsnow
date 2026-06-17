# Periodic Report Required Metrics Design

Date: 2026-06-16

## Status

Draft for Claude review.

## Problem

The full-text annual-report LLM experiment can produce useful narrative, but it still treats several hard annual-report metrics as optional. In the Yingjixin 2025 annual-report run, the source text and `fulltext-2-3` pack block contained:

- product revenue, revenue growth, gross margin, and gross-margin change;
- regional revenue and growth;
- direct/distributor revenue and growth;
- production/sales/inventory by product, including inventory growth;
- top-five customer and supplier sales/procurement concentration.

The LLM output omitted some of these from the main narrative, and the validator silently discarded other useful rows. This is unacceptable for periodic-report summaries: these numbers are not optional analysis color; they are the skeleton of the report.

## Goal

Make required annual/semiannual operating metrics stable and deterministic in the experimental full-text path.

This sprint should ensure that for A-share annual and semiannual reports, the output consistently includes:

1. Product/segment revenue table facts:
   - product or segment name;
   - revenue;
   - revenue YoY;
   - gross margin;
   - gross-margin change, when disclosed.
2. Sales geography and sales-mode facts:
   - domestic/overseas revenue and YoY, when disclosed;
   - distributor/direct revenue, YoY, and gross margin, when disclosed.
3. Production/sales/inventory facts:
   - product name;
   - production volume;
   - sales volume;
   - inventory volume;
   - production/sales/inventory YoY, when disclosed.
4. Customer/supplier concentration:
   - top-five customers sales and percentage;
   - largest customer sales and percentage, when disclosed;
   - top-five suppliers procurement and percentage;
   - largest supplier procurement and percentage, when disclosed;
   - whether related-party amount is disclosed.

## Non-Goals

- Do not connect this to Source Intake, evidence notes, `KnowledgeSynthesizer`, report assembly, scoring, risk scoring, or final recommendation.
- Do not change the deterministic v1 extractor or v1/v2 helper contracts unless required tests prove a helper-only dependency is needed.
- Do not use live network, Chrome/CDP, Xueqiu, or report generation in implementation tests.
- Do not invent industry-specific product keywords. The extraction must be table/header driven.

## Proposed Design

Add a small deterministic metrics layer inside the full-text experiment:

```python
required_business_metrics = {
    "schema_version": "periodic_report_required_metrics.v1",
    "segment_rows": [...],
    "region_rows": [...],
    "sales_mode_rows": [...],
    "inventory_rows": [...],
    "customer_concentration": {...},
    "supplier_concentration": {...},
    "source_block_ids": [...],
}
```

This layer should be generated from the full text or from fulltext evidence blocks before LLM analysis. It should be:

- deterministic;
- table/header driven;
- conservative: missing fields remain empty rather than inferred;
- evidence-bound: every row keeps source block id and short source excerpt/span when practical.

Then pass the structured metrics into `build_periodic_report_fulltext_prompt()` as a required section, and render them in Markdown before the LLM narrative.

The LLM should still write judgments, but it must not decide whether these hard metrics appear.

## Data Flow

1. Jina/PDF text enters `build_periodic_report_fulltext_pack()`.
2. New helper extracts `required_business_metrics` from the same text/blocks.
3. Prompt receives:
   - fulltext chunks;
   - required structured metrics;
   - instruction that `主营业务表现`, `客户与订单结构`, and `财务风险与跟踪指标` must reference relevant metrics when available.
4. Validator preserves LLM judgments, but required metrics are not subject to LLM fidelity loss.
5. Markdown renderer prints:
   - `## 必备经营指标摘录`
   - segment/product table;
   - region/sales-mode table;
   - inventory table;
   - customer/supplier concentration table;
   - then the six LLM sections.

## Extraction Rules

### Product/Segment Revenue and Gross Margin

Detect tables around A-share headings such as:

- `主营业务分行业情况`
- `主营业务分产品情况`
- `主营业务分地区情况`
- `主营业务分销售模式情况`
- table headers containing `营业收入`, `营业成本`, `毛利率`, `营业收入比上年增减`, `毛利率比上年增减`.

Rows should be parsed even when Jina inserts spaces inside words or line breaks inside product names, such as `数 模 混 合 SoC 类`.

### Inventory

Detect tables around:

- `产销量情况分析表`
- headers containing `主要产品`, `生产量`, `销售量`, `库存量`, `库存量比上年增减`.

Preserve units, e.g. `万颗`, `kg`, `吨`.

### Customers and Suppliers

Detect headings around:

- `主要销售客户及主要供应商情况`
- `前五名客户销售额`
- `公司前五名客户`
- `前五名供应商采购额`
- `公司前五名供应商`

Parse both aggregate concentration and first-row concentration when the table exists.

## Validator Changes

Do not relax no-fabrication rules globally. Instead:

- required metrics are trusted only because deterministic extraction found them in source text;
- LLM judgments may reference these metrics by evidence refs;
- if a judgment contains an extracted required metric, validator should allow it if the metric exists in `required_business_metrics`, even if raw text normalization would otherwise fail due Jina spacing.

Avoid silent loss of required metric rows. If required metrics are present but all are absent from rendered Markdown, tests should fail.

## Yingjixin Acceptance Criteria

For `/tmp/yingjixin_2025_annual_jina.txt`, the output must include at minimum:

- 电源管理类收入 `1,062,041,234.54` or `106,204.12 万元`, revenue YoY `12.44%`, gross margin `34.47%`, gross-margin change `+2.64pct`, inventory growth `51.80%`.
- 电池管理类收入 `202,758,468.19` or `20,275.85 万元`, revenue YoY `72.39%`, gross margin `38.83%`, gross-margin change `-1.72pct`, inventory growth `618.99%`.
- 数模混合 SoC 类收入 `337,194,197.68` or `33,719.42 万元`, revenue YoY `-0.83%`, gross margin `31.17%`, gross-margin change `-4.84pct`, inventory growth `61.04%`.
- 国内销售 `156,161.40 万元`, `+15.11%`; 国外销售 `4,050.44 万元`, `-11.30%`.
- 经销收入 `138,790.37 万元`, `+15.67%`; 直销收入 `21,421.47 万元`, `+5.83%`.
- 前五名客户销售额 `49,019.50 万元`,占比 `30.46%`; 第一大客户 `10,835.52 万元`,占比 `6.73%`.
- 前五名供应商采购额 `97,080.28 万元`,占比 `73.45%`; 第一大供应商 `43,030.34 万元`,占比 `32.56%`.

## Zhongjian Regression Criteria

For `/tmp/zhongjian_2025_annual_jina.txt`, output must still include:

- product revenue and gross margin rows for 碳纤维 and 碳纤维织物 when present;
- production/sales/inventory changes when present;
- top customer concentration when present.

## Tests

Add focused tests only.

Suggested tests:

1. `test_extracts_yingjixin_segment_margins_from_jina_fixture`
2. `test_extracts_yingjixin_inventory_rows_from_jina_fixture`
3. `test_extracts_yingjixin_customer_supplier_concentration`
4. `test_required_metrics_are_injected_into_prompt`
5. `test_renderer_prints_required_metrics_before_llm_sections`
6. `test_validator_allows_judgment_referencing_required_metric_with_jina_spacing`
7. `test_required_metrics_absent_when_table_not_present`
8. `test_zhongjian_required_metrics_regression`

Use compact fixtures copied from `/tmp` snippets into tests; do not depend on `/tmp` files.

## Allowed Files

- `scripts/utils/periodic_report_fulltext_llm_analysis.py`
- Optional new helper: `scripts/utils/periodic_report_required_metrics.py`
- `tests/utils/test_periodic_report_fulltext_llm_analysis.py`
- Optional new tests: `tests/utils/test_periodic_report_required_metrics.py`
- Implementation notes under `docs/agent_workflow/`

## Forbidden Files

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/**`
- `scripts/utils/reporter/**`, except this experimental renderer/helper if already in the allowed file
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/periodic_report_extractor.py`, unless review proves reuse is safer than duplication
- `config/**`
- `knowledge/**`
- `reports/**`
- `data/raw/**`

## Open Questions for Review

1. Should required metrics be stored as top-level fields in the analysis dict, or nested under `required_business_metrics` only?
2. Should Markdown render these as tables, or should they be injected only into LLM sections? Recommendation: render as tables for deterministic visibility.
3. Should the helper normalize all values to yuan/万元, or preserve original units? Recommendation: preserve original text plus optional normalized numeric fields later.
4. Should missing required metrics cause an error? Recommendation: no, but if source text contains matching headers and no rows are extracted, tests should catch representative failures.

## Round 1 Feedback

- **Status**: Needs minor fixes
- **R2 Needed**: Yes

### Findings (ordered by severity)

#### 1. Must-fix: `required_business_metrics` collides with the existing fulltext output schema

`build_periodic_report_fulltext_prompt()` / `validate_periodic_report_fulltext_output()` currently allow only three top-level fields in the LLM output: `schema_version`, `sections`, `financial_risks`. If the implementation adds `required_business_metrics` as a top-level field in the analysis dict, the validator will reject the entire output with `unsupported top-level field`. The design must clarify that required metrics are an **input to the prompt and renderer**, not a field the LLM emits. If metrics need to be carried through the analysis dict for renderer convenience, they must be stored outside the validated LLM-output object or the validator must be explicitly widened for deterministic, non-LLM fields only.

#### 2. Must-fix: the proposed validator exception weakens no-fabrication guarantees

The design says: "if a judgment contains an extracted required metric, validator should allow it if the metric exists in `required_business_metrics`, even if raw text normalization would otherwise fail due to Jina spacing." This is too loose. An LLM could emit a fabricated number and still pass by claiming it is a "required metric". The safe rule is: a judgment is allowed to repeat a required metric **only when the exact normalized value (using the same whitespace/unit normalization as the deterministic extractor) is present in `required_business_metrics`**. The metric catalogue alone must not be a bypass for `_check_fidelity`.

#### 3. High: row schema is undefined

`segment_rows`, `region_rows`, `sales_mode_rows`, `inventory_rows`, `customer_concentration`, and `supplier_concentration` are listed but their internal field names, types, optionality, and source-anchoring format are not specified. The design should include a concrete row schema, e.g.:

```python
{
  "product_name": str,          # raw text, whitespace-normalized
  "revenue": str,               # original numeric text
  "revenue_yoy": str | None,
  "gross_margin": str | None,
  "gross_margin_delta": str | None,
  "unit": str | None,           # 元 / 万元 / 万颗 / kg / 吨
  "source_block_id": str,
  "source_excerpt": str,        # short span for renderer/human review
}
```

Without this, tests cannot assert consistently and the renderer cannot format deterministically.

#### 4. High: the design does not reuse the existing `periodic_report_evidence_pack.py` capabilities

`periodic_report_evidence_pack.py` already extracts `segment_margin_table`, `customer_supplier_table`, `supplier_concentration_table`, `production_sales_inventory_table`, `rd_investment_table`, and others with header-driven, Jina-tolerant logic. Adding a separate raw-text parser in a new helper risks duplication and inconsistent results. The preferred data flow is:

1. `build_periodic_report_evidence_pack(text)` → blocks.
2. New helper consumes those blocks (plus optional raw text fallback) → `required_business_metrics`.
3. Prompt receives both fulltext chunks and the structured metrics.

This keeps the table/header extraction in one place and lets required metrics inherit the same Jina-spacing fixes already tested in Phase A.1/A.2.

#### 5. High: source block id semantics are underspecified

The design proposes `source_block_ids: [...]` at the top level of `required_business_metrics`. It is unclear whether these are fulltext block ids (`fulltext-2-0`), evidence-pack block ids (`segment_margin_table-0`), or both. Because fidelity checking in the fulltext path only knows `fulltext-{section}-{chunk}` ids, judgments that reference required metrics need either (a) a deterministic mapping from metric rows back to fulltext block ids, or (b) a renderer that prints metrics independently and does not require evidence refs for them. The design should pick one and document it.

#### 6. Medium: unit handling needs a concrete rule

The design recommends preserving original units, but mixed units (`元`, `万元`, `亿元`) will confuse both the LLM and downstream consumers. Specify that the helper stores:
- `original_value`: the text as found in the report;
- `original_unit`: the unit as found;
- optionally `normalized_yuan_value` / `normalized_wan_yuan_value` for numeric comparison.

The prompt should instruct the LLM to use the original value+unit in judgments and to avoid deriving across units unless the conversion is trivial.

#### 7. Medium: missing-metric visibility is not designed

"Missing fields remain empty rather than inferred" is correct, but the design does not say how the consumer distinguishes "disclosed but not extracted" from "not disclosed at all". Add a `disclosed: bool` or `present: bool` flag per table/metric, or return an empty row list plus a `headers_found: [...]` field so the renderer can show "年报列示该表但关键数据未识别" when appropriate.

#### 8. Medium: renderer placement is not fully specified

The design says render `## 必备经营指标摘录` before the six LLM sections. Because the renderer currently renders only the validated LLM output, the metrics must be passed into `render_periodic_report_fulltext_markdown()` as a separate argument or embedded in a wrapper object. This should be explicit in the design, including fallback text when no metrics are present.

#### 9. Low: acceptance criteria mix product-level segment and product-level inventory metrics

The 英集芯 criteria ask for both revenue/margin and inventory growth per product class (`电源管理类`, `电池管理类`, `数模混合 SoC 类`). The segment table and the production/sales/inventory table are two distinct A-share tables with potentially different product naming. The design should state whether rows are matched by exact product name, shown as two separate tables, or linked via a common `product_key`. Otherwise the acceptance test will be brittle.

#### 10. Low: existing `_empty_fulltext_analysis` returns an incorrect schema

A code-level observation (not a design change request): `scripts/utils/periodic_report_fulltext_llm_analysis.py::_empty_fulltext_analysis` returns `SCHEMA_VERSION` (the v2 constant) instead of `FULLTEXT_ANALYSIS_SCHEMA_VERSION`, and includes `company_profile`, `cards`, `sections`, `financial_risks` fields that conflict with the fulltext schema. If the empty path is ever exercised, it will break consumers. This is worth fixing when implementation starts, but it is not a blocker for the current design review.

### Required design deltas

1. Remove `required_business_metrics` from the LLM-output schema; define it as prompt/renderer input only.
2. Replace the broad "required-metric bypass" with exact normalized-value matching against the deterministic extraction result.
3. Add a concrete row schema for every array in `required_business_metrics`.
4. Specify that the new helper consumes `build_periodic_report_evidence_pack()` blocks first, with raw text fallback only when necessary.
5. Clarify block-id semantics: either map metrics back to fulltext ids or exempt metrics from the evidence-ref requirement in renderer output.
6. Add unit-preservation + optional normalized numeric fields.
7. Add a missing/disclosed visibility field per table.
8. Show the exact renderer signature change for `render_periodic_report_fulltext_markdown()`.

### Missing tests

The current test list is a good start but incomplete. Add at least:

- **Jina spacing**: extraction and validator fidelity for `99. 42%`, `87.4 9%`, `1,062,041,23 4.54` style spacing.
- **Broken product names**: multi-line or space-spliced product names such as `数 模 混 合 SoC 类` are reconstructed into a single row.
- **Table truncation**: a long table exceeding the evidence-pack line window still yields the first/most important rows (e.g. 英集芯 `电源管理类`).
- **Adjacent table boundary**: segment margin table immediately followed by customer/supplier table does not merge rows.
- **Fabrication via required metric**: a judgment containing a value that is **not** in `required_business_metrics` but labeled as a metric must still be dropped.
- **Unit conversion**: `元`, `万元`, `亿元` values are preserved and optionally normalized without loss.
- **Missing table**: when `主营业务分产品情况` is absent, `segment_rows` is empty and no error is raised.
- **Renderer ordering**: Markdown output contains `## 必备经营指标摘录` before `## 公司画像` and after the metadata block.
- **Renderer empty state**: when all metrics are missing, the section prints a deterministic fallback instead of an empty heading.
- **Disclosed-but-empty table**: header is found but rows are not extracted → output carries a `disclosed: true, present: false` marker.

### Blockers

None for the design itself, but two issues must be resolved before implementation:

1. The LLM-output schema collision (Finding 1) must be resolved; otherwise the first end-to-end test will fail.
2. The fidelity-bypass wording (Finding 2) must be tightened; otherwise the validator will silently allow fabricated numbers wrapped as "required metrics".

No changes to Source Intake, `KnowledgeSynthesizer`, report assembly, scoring engine, or risk scoring are required by this design.

## Codex R2 Design Revision

This revision resolves the Round 1 blockers without changing the sprint boundary.

### Revised Status

R2 draft for narrow Claude review.

### Accepted Changes

1. `required_business_metrics` is not an LLM output field.
2. Required metrics do not bypass fidelity checks. They only provide exact normalized values that validator may match.
3. Extraction must consume `periodic_report_evidence_pack.py` blocks first.
4. Row schema, units, missing visibility, and renderer input are now explicit.

### Revised Data Flow

1. `build_periodic_report_evidence_pack(text)` builds deterministic evidence blocks.
2. `build_periodic_report_fulltext_pack(text)` builds larger section chunks for narrative.
3. New helper consumes evidence-pack blocks:

```python
metrics = build_required_business_metrics(evidence_pack)
```

4. `build_periodic_report_fulltext_prompt(fulltext_pack, required_metrics=metrics)` injects the metrics into the prompt as deterministic source material.
5. The LLM still emits only:

```python
{
    "schema_version": "periodic_report_fulltext_analysis.v1",
    "sections": [...],
    "financial_risks": [...],
}
```

6. `validate_periodic_report_fulltext_output(raw, fulltext_pack, required_metrics=metrics)` validates LLM output. The validated LLM object remains schema-compatible.
7. `render_periodic_report_fulltext_markdown(analysis, required_metrics=metrics)` prints required metrics before LLM sections.

### Required Metrics Schema

`required_business_metrics` is deterministic metadata, not LLM output:

```python
{
    "schema_version": "periodic_report_required_metrics.v1",
    "source_pack_schema_version": "periodic_report_evidence_pack.v1",
    "segment_rows": [SegmentMetricRow],
    "region_rows": [SegmentMetricRow],
    "sales_mode_rows": [SegmentMetricRow],
    "inventory_rows": [InventoryMetricRow],
    "customer_concentration": ConcentrationMetric,
    "supplier_concentration": ConcentrationMetric,
    "tables": {
        "segment_margin": TablePresence,
        "region": TablePresence,
        "sales_mode": TablePresence,
        "inventory": TablePresence,
        "customer_supplier": TablePresence,
    },
    "normalized_values": ["..."],
}
```

`SegmentMetricRow`:

```python
{
    "label": str,
    "revenue": {"text": str, "unit": str | None, "normalized": str | None},
    "cost": {"text": str, "unit": str | None, "normalized": str | None} | None,
    "gross_margin": {"text": str, "unit": "%", "normalized": str | None} | None,
    "revenue_yoy": {"text": str, "unit": "%", "normalized": str | None} | None,
    "cost_yoy": {"text": str, "unit": "%", "normalized": str | None} | None,
    "gross_margin_delta": {"text": str, "unit": "pct", "normalized": str | None} | None,
    "source_block_id": str,
    "source_usage": str,
    "source_excerpt": str,
}
```

`InventoryMetricRow`:

```python
{
    "label": str,
    "quantity_unit": str | None,
    "production_volume": {"text": str, "unit": str | None, "normalized": str | None} | None,
    "sales_volume": {"text": str, "unit": str | None, "normalized": str | None} | None,
    "inventory_volume": {"text": str, "unit": str | None, "normalized": str | None} | None,
    "production_yoy": {"text": str, "unit": "%", "normalized": str | None} | None,
    "sales_yoy": {"text": str, "unit": "%", "normalized": str | None} | None,
    "inventory_yoy": {"text": str, "unit": "%", "normalized": str | None} | None,
    "source_block_id": str,
    "source_usage": str,
    "source_excerpt": str,
}
```

`ConcentrationMetric`:

```python
{
    "present": bool,
    "headers_found": [str],
    "top_five_amount": {"text": str, "unit": str | None, "normalized": str | None} | None,
    "top_five_percentage": {"text": str, "unit": "%", "normalized": str | None} | None,
    "largest_amount": {"text": str, "unit": str | None, "normalized": str | None} | None,
    "largest_percentage": {"text": str, "unit": "%", "normalized": str | None} | None,
    "related_party_amount": {"text": str, "unit": str | None, "normalized": str | None} | None,
    "related_party_percentage": {"text": str, "unit": "%", "normalized": str | None} | None,
    "source_block_id": str | None,
    "source_usage": str | None,
    "source_excerpt": str | None,
}
```

`TablePresence`:

```python
{
    "headers_found": [str],
    "present": bool,
    "row_count": int,
    "source_block_ids": [str],
}
```

### Source Block IDs

Metrics keep evidence-pack block ids, e.g. `segment_margin_table-0`, `production_sales_inventory_table-0`, `customer_supplier_table-0`.

These ids are not valid LLM `evidence_refs` in fulltext sections. Therefore:

- deterministic metrics are rendered independently and do not need LLM evidence refs;
- LLM judgments continue to reference fulltext ids such as `fulltext-2-3`;
- prompt may show metrics with their evidence-pack ids for human traceability, but generated judgments must still cite fulltext ids.

This avoids widening the fulltext `evidence_refs` universe and keeps the current validator contract intact.

### Required Metrics and Fidelity

No broad bypass is allowed.

Validator behavior:

- `_check_fidelity()` remains the default authority for LLM judgments.
- If a judgment contains a value that fails raw fulltext fidelity because of Jina spacing or unit normalization, validator may consult `required_metrics["normalized_values"]`.
- The judgment passes only when every disputed value has an exact normalized match in `normalized_values`.
- Matching is value-level, not label-level. Example: `34.47%` can pass only if normalized `34.47%` exists in deterministic metrics.
- Metric labels alone never allow a fabricated value.

Normalization should be conservative:

- remove internal whitespace from numeric strings;
- normalize full-width punctuation;
- preserve sign;
- normalize `%` and `个百分点` separately;
- preserve original text and unit for display;
- optionally store normalized yuan/wan-yuan values only when the unit is explicit.

### Renderer Contract

Change renderer signature to:

```python
render_periodic_report_fulltext_markdown(
    analysis: Dict[str, Any],
    *,
    required_metrics: Dict[str, Any] | None = None,
) -> str
```

Markdown order:

1. metadata block;
2. experimental disclaimer;
3. `## 必备经营指标摘录`;
4. metrics tables;
5. six LLM sections.

If `required_metrics` is absent or empty:

```markdown
## 必备经营指标摘录

未识别到可稳定结构化的分产品、库存、客户或供应商指标。
```

If a table header is found but no rows are parsed, render a compact warning row:

```markdown
| 表格 | 状态 |
|------|------|
| 主营业务分产品情况 | 已发现表头，但未能稳定解析行 |
```

### Prompt Contract

Prompt receives required metrics as deterministic context, not as target JSON output:

```text
以下为程序确定性抽取的必备经营指标。必须在相关章节中解释这些指标的经营含义。
不要在 JSON 输出中复制 required_business_metrics 字段。
如果引用这些指标，仍需引用对应 fulltext evidence refs。
```

### Revised Tests

Required focused tests:

1. `test_required_metrics_consumes_evidence_pack_blocks`
2. `test_extracts_yingjixin_segment_margin_rows_from_evidence_block`
3. `test_extracts_yingjixin_inventory_rows_from_evidence_block`
4. `test_extracts_yingjixin_customer_supplier_concentration_from_evidence_block`
5. `test_required_metrics_preserve_original_units_and_normalized_values`
6. `test_required_metrics_handles_jina_spaced_numbers`
7. `test_required_metrics_handles_broken_product_names`
8. `test_required_metrics_table_presence_when_header_found_but_no_rows`
9. `test_prompt_injects_required_metrics_but_does_not_add_output_schema_field`
10. `test_validator_accepts_exact_required_metric_value_when_raw_spacing_differs`
11. `test_validator_rejects_fabricated_metric_value_not_in_required_metrics`
12. `test_renderer_prints_required_metrics_before_company_profile`
13. `test_renderer_empty_required_metrics_state`
14. `test_zhongjian_required_metrics_regression`

### Implementation Notes

- Prefer a new helper file `periodic_report_required_metrics.py` to keep parsing isolated.
- Do not duplicate the broad table-discovery logic already present in `periodic_report_evidence_pack.py`.
- The helper should parse only the text contained in evidence-pack blocks with relevant usages:
  - `segment_margin_table`
  - `region_table`
  - `segment_table`
  - `production_sales_inventory_table`
  - `customer_supplier_table`
  - `supplier_concentration_table`
- Raw text fallback is allowed only if the evidence pack contains no relevant blocks, and must be bounded and tested.
- The current `_empty_fulltext_analysis` schema mismatch should be fixed during implementation if touching the module.

### R2 Open Questions

1. Is it acceptable that deterministic metrics use evidence-pack ids while LLM judgments use fulltext ids, as long as renderer makes the distinction clear?
2. Should `normalized_values` include every numeric cell, or only values used by required metrics tables? Recommendation: only required table cells.
3. Should table parsing support negative values represented as `减少 1.7 2 个百分点` and `-4.84` as the same normalized delta? Recommendation: yes, normalize both to signed `pct` values for matching while preserving original display text.

## Round 2 Feedback

- **Status**: Ready to implement
- **R3 Needed**: No

### Findings (ordered by severity)

#### 1. High: `normalized_values` is a flat string list — its match contract needs pinning

The design says `normalized_values: ["..."]` at the top level and requires validator to do "exact normalized match". This is fine, but the design should specify:

- what strings go into the list (one per numeric cell or one per composite value?);
- whether values are deduplicated;
- whether the match is case-/sign-sensitive;
- whether the list includes only required table cells or also raw fallback values.

Without this, two implementers could produce incompatible validators: one stores `34.47%` and `106204.12万元`, another stores `34.47` and `1062041200`. Recommend documenting one canonical form in the design, e.g.:

> `normalized_values` contains one entry per numeric value after stripping internal whitespace, normalizing full-width characters to half-width, and appending the unit symbol (`%`, `pct`, `万元`, `元`, `万颗`, `吨`, etc.). Signed values keep the sign. The validator checks whether any contiguous numeric(+unit) token in the judgment appears in this set.

#### 2. High: renderer must not break consumers that call it with one argument

The new signature `render_periodic_report_fulltext_markdown(analysis, *, required_metrics=None)` is backward-compatible, but tests and existing call sites should still be verified. The design notes this; no delta needed, but it should be a check item during implementation.

#### 3. Medium: `tables[*].source_block_ids` duplicates top-level row block refs

`TablePresence` carries `source_block_ids` and each row carries `source_block_id`. This is useful but could drift. Consider requiring that the union of row `source_block_id`s equals `tables[*].source_block_ids` for that category, and add a test for consistency.

#### 4. Medium: `revenue_yoy.unit` is `%` but may also appear as `百分点` or `pct`

The schema says `unit: "%"` for growth rates and margin deltas. Jina text may render deltas as `-4.84pct` or `减少 4.84 个百分点`. The design already recommends normalizing these to signed `pct` values for matching, but the schema field `unit` should either be flexible (`"%" | "pct" | "个百分点"`) or normalized to a canonical `pct`. Recommend canonicalizing `unit` to `pct` for all margin/growth deltas, while preserving original text.

#### 5. Medium: prompt injection wording could still confuse the model

The prompt text says "如果引用这些指标，仍需引用对应 fulltext evidence refs". This is correct, but LLMs may still try to emit evidence-pack ids. Add an explicit forbidden example in the prompt, such as:

> 禁止引用 `segment_margin_table-0` 等 evidence-pack id；所有 judgment 的 evidence_refs 必须是 fulltext 块 id，例如 `fulltext-2-0`。

This prevents the most likely schema violation.

#### 6. Low: acceptance criteria do not cover sales-mode and regional rows for 英集芯

The Yingjixin acceptance list includes 国内/国外 and 经销/直销 figures, but the schema separates these into `region_rows` and `sales_mode_rows`. Ensure at least one test asserts both arrays are populated and preserve the expected values.

#### 7. Low: no test for raw-text fallback path

The design allows raw text fallback only when evidence pack contains no relevant blocks. Add a focused test that simulates a report with only raw text (no `segment_margin_table` block) and verifies the fallback still extracts metrics.

#### 8. Low: `source_excerpt` length is unbounded

The schema includes `source_excerpt: str` per row. If the implementation copies the entire block text, the metrics payload could become large. Recommend bounding `source_excerpt` to e.g. 300 characters in the schema description.

### Required deltas

1. Pin the canonical form of `normalized_values` and the exact-match rule in the design.
2. Document that `unit` for margin/growth deltas is normalized to `pct` while original text is preserved.
3. Add an explicit prompt example forbidding evidence-pack ids in `evidence_refs`.
4. Bound `source_excerpt` length in the schema description.

### Missing tests

- `test_normalized_values_canonical_form`: asserts every entry follows the documented normalization (whitespace stripped, full-width to half-width, unit appended).
- `test_validator_rejects_evidence_pack_id_in_judgment_refs`: ensures LLM cannot cite `segment_margin_table-0`.
- `test_region_and_sales_mode_rows_for_yingjixin`: covers the geographic and channel split.
- `test_raw_text_fallback_extracts_metrics`: covers the fallback path.
- `test_source_excerpt_bounded`: ensures excerpts are truncated.
- `test_table_presence_row_block_id_consistency`: union of row ids matches `tables[*].source_block_ids`.

### Blockers

None. R2 resolves both Round 1 blockers, keeps the implementation within the allowed helper-only experimental scope, and provides enough schema detail to begin implementation after the four minor deltas above are applied.

## Codex Final Implementation Deltas

The Round 2 required deltas are accepted and must be part of the implementation task.

### Canonical `normalized_values`

`normalized_values` must contain one entry per numeric value that appears in required metric rows. It is a deduplicated list.

Canonicalization rules:

- convert full-width characters to half-width;
- strip internal whitespace inside numeric tokens and units, e.g. `1,062,041,23 4.54` -> `1,062,041,234.54`;
- preserve comma separators if present in the original text;
- preserve signs (`-`, `+`, `减少`, `增加`) by converting delta values to signed canonical text when the sign is clear;
- append or preserve the canonical unit:
  - money: `元`, `万元`, `亿元`;
  - quantity: `万颗`, `kg`, `吨`, or the source table unit;
  - percentage rates: `%`;
  - margin/growth deltas: `pct`;
- include only values extracted into required metric rows, not arbitrary fulltext fallback values.

Examples:

| Source Text | Canonical |
|-------------|-----------|
| `34.47` under 毛利率 column | `34.47%` |
| `增加 2.6 4 个百分点` | `+2.64pct` |
| `减少 1.7 2 个百分点` | `-1.72pct` |
| `-4.84` under 毛利率比上年增减 | `-4.84pct` |
| `138 ,790 .37 万元` | `138,790.37万元` |
| `1,062,041,23 4.54 元` | `1,062,041,234.54元` |

The validator exact-match rule is:

> Any numeric(+unit) token that cannot be matched by fulltext fidelity may pass only if its canonical form exactly appears in `required_metrics["normalized_values"]`.

Metric labels never allow a fabricated number.

### Delta Units

For all growth and margin deltas, row fields should preserve original text but canonicalize `unit` to `pct`:

```python
"gross_margin_delta": {
    "text": "减少 1.7 2 个百分点",
    "unit": "pct",
    "normalized": "-1.72pct",
}
```

Plain rates such as gross margin and revenue YoY keep canonical unit `%`.

### Prompt Evidence-Ref Rule

The prompt must explicitly forbid evidence-pack ids in LLM output:

```text
禁止在 judgment.evidence_refs 中引用 segment_margin_table-0、production_sales_inventory_table-0、
customer_supplier_table-0 等 evidence-pack id。judgment.evidence_refs 只能使用 fulltext 块 id，
例如 fulltext-2-0、fulltext-2-3。
```

Validator should already reject unknown refs; add a focused test for this failure mode.

### `source_excerpt` Bound

Each metric row's `source_excerpt` must be bounded to at most 300 characters after whitespace cleanup. It should include enough surrounding table text for human review, but never copy the entire evidence block.

### Final Required Tests

Implementation must include the R2 tests plus:

- `test_normalized_values_canonical_form`
- `test_validator_rejects_evidence_pack_id_in_judgment_refs`
- `test_region_and_sales_mode_rows_for_yingjixin`
- `test_raw_text_fallback_extracts_metrics`
- `test_source_excerpt_bounded`
- `test_table_presence_row_block_id_consistency`

### Final Status

Ready to implement. R3 is not needed.
