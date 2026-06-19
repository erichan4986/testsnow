# Periodic Report Experimental Path Scoped Review

Date: 2026-06-17

## Scope

Reviewed the annual/semiannual standalone experimental path after the required business metrics, required financial-risk metrics, product/project backfill, and deterministic supplier-risk backfill work.

No main report pipeline, scoring, technical analysis, `KnowledgeSynthesizer`, `reports/`, or `knowledge/` integration was performed.

## File Buckets

### Current Effective Experimental Path

- `scripts/utils/periodic_report_evidence_pack.py`
- `scripts/utils/periodic_report_fulltext_llm_analysis.py`
- `scripts/utils/periodic_report_required_metrics.py`
- `scripts/utils/periodic_report_required_financial_metrics.py`
- `scripts/utils/periodic_report_product_project_evidence.py`
- `tests/utils/test_periodic_report_evidence_pack.py`
- `tests/utils/test_periodic_report_fulltext_llm_analysis.py`
- `tests/utils/test_periodic_report_required_metrics.py`
- `tests/utils/test_periodic_report_required_financial_metrics.py`
- `tests/utils/test_periodic_report_product_project_evidence.py`

### Still Active Legacy / Parallel Path

- `scripts/utils/periodic_report_extractor.py`
- `scripts/periodic_report_extractor.py`
- `tests/utils/test_periodic_report_extractor.py`

This extractor is older than the fulltext experimental path, but it is still referenced by `scripts/utils/a_stock_source_intake.py` and tested. Do not delete it during this cleanup round.

### Retired Predecessors

The earlier `periodic_report_llm_analysis.py` and `periodic_report_llm_analysis_v2.py` helper files are no longer present in the working tree. Remaining mentions are historical docs only.

### Local Validation Cache

- `data/raw/periodic_reports/*.txt`

These are local annual-report Jina text caches used for repeatable offline validation. They should be treated as validation fixtures/caches until the commit policy is decided; they are not report output.

## Offline Sample Validation

Generated deterministic offline previews without network or LLM calls:

- `/tmp/zhongjian_2025_annual_offline_required_backfill_check.md`
- `/tmp/shengbang_2025_annual_offline_required_backfill_check.md`
- `/tmp/yingjixin_2025_annual_offline_required_backfill_check.md`
- `/tmp/huadajiutian_2025_annual_offline_required_backfill_check.md`

Summary output:

- `/tmp/periodic_report_offline_required_backfill_summary.json`

### Sample Results

| Company | Required Metrics | Product / Project Backfill | Financial Risk Backfill |
|---|---|---|---|
| 中简科技 | Segment margin, inventory, customer/supplier concentration present | Captures aviation/aerospace, carbon-fiber, T1100/ZM40X project content; latest readability pass removed mid-word and repeated-word artifacts | No supplier risk backfill; supplier concentration is moderate at 41.58% / 20.63% |
| 圣邦股份 | Segment margin, inventory, customer/supplier concentration present | Captures analog-chip product platform terms such as signal chain, power management, sensors, and LDO; avoids the earlier generic `人工智能，采用...` wording | Supplier concentration backfilled: 90.99% / 39.61% |
| 英集芯 | Segment margin, per-product inventory, region/channel, customer/supplier concentration present | Captures brand/channel and AEC-Q100 / QC5.0 / PD / Tier 1 project content | Supplier concentration backfilled: 73.45% / 32.56% |
| 华大九天 | Segment and concentration metrics present; no inventory table | Captures EDA / 3DIC / verification / ISO certification context | No supplier risk backfill; supplier concentration is moderate at 44.48% / 17.30% |

## Findings

### Good Enough for Continued Experimentation

- Required business metrics now reliably surface segment revenue/gross margin, inventory where present, channel/region tables, and customer/supplier concentration.
- Required financial-risk metrics surface the main hard numbers needed for risk synthesis: cash flow, inventory/impairment, supplier concentration, capex/financial assets/goodwill/audit signals where extracted.
- Deterministic supplier-risk backfill avoids depending entirely on the LLM for high supplier concentration. It did not fire for moderate supplier concentration in 中简科技 or 华大九天.
- EDA vocabulary expansion did not create observed cross-industry pollution in 中简科技, 圣邦股份, or 英集芯.

### Still Needs Polishing

- Product/project backfill is now better as a deterministic material layer, but it is still more mechanical than a final human-facing annual-report summary.
- Some profile and RD backfill sentences are concise enough for downstream LLM context, but should not be treated as final prose without the final report-generation pass.
- 华大九天 profile is acceptable for the EDA vocabulary smoke test, but the next real LLM preview should confirm that EDA product categories do not crowd out financial-risk analysis.
- Offline deterministic-only previews are material checks, not a substitute for real LLM fixed-section summaries.

## Readability Pass

After the scoped review, a small readability pass was applied to product/project backfill:

- Added regression coverage for platform product categories, using signal-chain / power-management / sensor examples.
- Added regression coverage for carbon-fiber RD snippets to prevent mid-word starts such as `法工艺`, duplicated words such as `研发研发`, and overlong trailing fragments such as `提升竞争力国产...`.
- Profile backfill now prefers product / technology categories over generic application words when both are present.
- RD progress backfill now trims common tail clauses and keeps only clauses that still contain product or technology signals.
- The EDA vocabulary expansion remained scoped to product / application evidence and did not create observed cross-industry pollution in the four offline previews.

## Verification

```bash
python3 -m pytest tests/utils/test_periodic_report_extractor.py tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_required_metrics.py tests/utils/test_periodic_report_required_financial_metrics.py tests/utils/test_periodic_report_product_project_evidence.py tests/utils/test_periodic_report_fulltext_llm_analysis.py -q
# 153 passed

git diff --check
# no output
```

## Recommendation

Keep the current experimental path as a standalone material layer for now.

Before Source Intake or report-pipeline integration:

1. Decide whether `data/raw/periodic_reports/*.txt` should be committed as fixtures, ignored as local cache, or moved under a dedicated test fixture directory.
2. Run one real LLM preview after the readability pass on at least 英集芯 and 华大九天.
3. If the real preview is good, design the Source Intake integration boundary so this remains evidence material and does not enter scoring or core facts directly.
