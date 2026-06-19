# Yingjixin Periodic Report LLM Preview

Date: 2026-06-17

## Inputs

- Source text: `data/raw/periodic_reports/英集芯_2025_annual_jina.txt`
- Path: annual/semiannual standalone experimental path
- LLM: DeepSeek/OpenAI-compatible client from local `.env`
- Deterministic inputs:
  - `required_business_metrics`
  - `required_financial_risk_metrics`
  - product/project/customer backfill

No `reports/` or `knowledge/` outputs were written.

## Outputs

- JSON: `/tmp/yingjixin_2025_annual_llm_required_metrics_experiment.json`
- Markdown: `/tmp/yingjixin_2025_annual_llm_required_metrics_experiment.md`
- Evidence audit: `/tmp/yingjixin_2025_annual_llm_required_metrics_experiment_audit.md`

## Coverage Check

The preview covered the required hard metrics:

- product segment revenue and gross margin: 电源管理类、电池管理类、数模混合 SoC 类
- inventory growth: 51.80%, 61.04%, 618.99%
- customer concentration: 30.46%, first customer 6.73%
- supplier concentration: 73.45%, first supplier 32.56%
- operating cash flow: 2,742.05 万元, -88.28%
- inventory impairment / allowance
- goodwill increase
- sales mode: 经销 / 直销

## Observed Quality

Compared with the deterministic-only preview, the LLM output is materially closer to the desired 90-point summary style:

- It connects product growth with margin and inventory pressure.
- It explains cash-flow divergence rather than only listing values.
- It identifies supplier concentration, goodwill, overseas exposure, and governance events.
- It retains evidence refs for each judgment/risk.

## Issues To Fix Later

Do not treat this preview as final integration-ready.

Observed issues:

1. `governance_risk` appeared in the raw LLM response. Validator now remaps this common model alias to the fixed taxonomy.
2. Governance risk appeared twice after normalization (`audit_internal_control` and `related_party_governance`) with overlapping content.
3. One `customer_concentration` risk summary actually described supplier concentration, indicating that risk-type semantic validation still needs tightening.
4. `profit_quality` was framed as an improving quality point but still listed as a risk. The prompt or post-validator may need to distinguish positive observations from risk items.

These are prompt/validator polishing issues, not blocker evidence-fabrication issues.

## Current Recommendation

Keep the deterministic layer as a material layer.

Before Source Intake or report integration, run one more focused pass on:

- risk deduplication between audit/governance categories
- risk-type semantic consistency
- positive observation vs risk filtering

## Prompt/Validator Polishing Pass

Status after focused fixes:

- Added tests for three failure modes:
  - supplier-concentration content mislabeled as `customer_concentration`
  - overlapping `audit_internal_control` / `related_party_governance`
  - positive profit-quality observation incorrectly entering `financial_risks`
- Validator now:
  - remaps customer/supplier concentration when the summary text clearly points to the other side
  - deduplicates audit/internal-control and related-party/governance overlap under one semantic key
  - drops pure positive `profit_quality` observations unless the text contains concrete adverse signals such as扣非下降、毛利率下降、经营现金流下降/背离、亏损、减值、非经常性依赖等

Focused tests:

```bash
python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_required_metrics.py tests/utils/test_periodic_report_required_financial_metrics.py tests/utils/test_periodic_report_product_project_evidence.py tests/utils/test_periodic_report_fulltext_llm_analysis.py -q
# 123 passed
```

Real LLM re-run:

- JSON: `/tmp/yingjixin_2025_annual_llm_required_metrics_experiment.json`
- Markdown: `/tmp/yingjixin_2025_annual_llm_required_metrics_experiment.md`
- Evidence audit: `/tmp/yingjixin_2025_annual_llm_required_metrics_experiment_audit.md`
- Latest risk types: `cash_flow_quality`, `audit_internal_control`, `receivables_collection`, `revenue_recognition`, `profit_quality`, `inventory_impairment`, `rd_conversion`

Remaining observation:

- Required metrics still surface supplier concentration deterministically (`73.45%`, first supplier `32.56%`), but the final LLM risk list may omit `supplier_concentration` depending on the model response. If we want supplier concentration to always appear in `financial_risks` when thresholds are high, that should be a separate deterministic risk-backfill pass, not just prompt polishing.

## Deterministic Supplier-Risk Backfill

Implemented a narrow deterministic backfill for high supplier concentration:

- Trigger: `required_financial_risk_metrics.supplier_concentration` shows top-five supplier concentration >= 60%, or largest supplier >= 30%.
- Detail merge: uses `required_business_metrics.supplier_concentration` to fill missing largest-supplier details when financial-risk metrics only extracted the top-five aggregate.
- Deduplication: if LLM already emitted `supplier_concentration`, the deterministic backfill does not add another copy.
- Guardrail: low supplier concentration does not generate a risk just because the metric exists.

Focused tests:

```bash
python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_required_metrics.py tests/utils/test_periodic_report_required_financial_metrics.py tests/utils/test_periodic_report_product_project_evidence.py tests/utils/test_periodic_report_fulltext_llm_analysis.py -q
# 127 passed
```

Offline re-render using the previous LLM JSON:

- JSON: `/tmp/yingjixin_2025_annual_llm_required_metrics_experiment_backfilled.json`
- Markdown: `/tmp/yingjixin_2025_annual_llm_required_metrics_experiment_backfilled.md`
- Evidence audit: `/tmp/yingjixin_2025_annual_llm_required_metrics_experiment_backfilled_audit.md`

Backfilled supplier-risk summary:

> 前五名供应商采购额97080.28万元，占年度采购总额73.45%；第一大供应商采购额43030.34万元，占比32.56%。供应商集中度较高，需要作为财务风险跟踪项。
