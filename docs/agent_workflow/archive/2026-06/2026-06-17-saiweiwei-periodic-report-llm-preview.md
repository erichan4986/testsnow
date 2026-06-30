# Saiweiwei Periodic Report LLM Preview

Date: 2026-06-17

## Inputs

- Company: 赛微微电 / 688325
- Source: 2025 annual report from cninfo, read through Jina Reader
- Local cache: `data/raw/periodic_reports/赛微微电_2025_annual_jina.txt`
- Path: annual/semiannual standalone experimental path
- LLM: DeepSeek/OpenAI-compatible client from local `.env`
- Deterministic inputs:
  - `required_business_metrics`
  - `required_financial_risk_metrics`
  - product/project/customer backfill

No `reports/` or `knowledge/` outputs were written.

## Outputs

- JSON: `/tmp/saiweiwei_2025_annual_fulltext_summary.json`
- Markdown: `/tmp/saiweiwei_2025_annual_fulltext_summary.md`
- Evidence audit: `/tmp/saiweiwei_2025_annual_fulltext_summary_audit.md`

## Coverage Check

The preview covered the required hard metrics:

- product segment revenue and gross margin: 电池安全芯片、电池计量芯片
- inventory growth: 电池安全芯片 +112.98%, 电池计量芯片 +82.31%, 充电管理等其他芯片 +74.99%
- region rows: 境内 / 境外
- sales mode: 经销 / 直销
- customer concentration: top five 60.15%
- supplier concentration: top five 99.55%, first supplier 45.28%
- operating cash flow: 506.53 万元, +107.82%
- inventory book value: 18,139.82 万元
- cash / financial assets / short-term borrowing
- audit opinion and key audit matters: 标准无保留意见; 收入确认、存货跌价

## Observed Quality

Compared with deterministic-only material, the LLM output is useful:

- It preserves product revenue/gross-margin and inventory pressure.
- It connects high inventory growth with demand and impairment risk.
- It identifies high supplier concentration as a high-importance financial risk.
- It captures market context for analog / battery-management ICs and domestic substitution.
- It keeps evidence refs on each judgment and risk.

## Fixes Triggered By This Sample

This new company exposed two small issues that were fixed immediately:

1. `periodic_report_required_financial_metrics` accepted punctuation-only text such as `","` as an amount, producing a bogus `investment_income: 元`.
   - Added a regression test.
   - `_amount_cell()` now rejects amount tokens with no digit.
2. Product/customer backfill treated smart-device application text as customer/channel text, producing awkward output such as `可应用于智能、耳机等智能`.
   - Added a regression test.
   - `_customer_org_tokens()` now filters obvious application/device fragments.

## Remaining Observation

The supplemental company-profile backfill is now acceptable as material context:

> 公司画像补充判断：客户与渠道：智能手机、平板电脑、TWS 耳机等应用领域，采用经销为主。产品覆盖：模拟等产品/技术方向。收入对终端需求周期和渠道备货节奏较为敏感

It is still mechanical and should be treated as downstream LLM material, not final human-facing prose.

## Verification

```bash
python3 -m pytest tests/utils/test_periodic_report_extractor.py tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_required_metrics.py tests/utils/test_periodic_report_required_financial_metrics.py tests/utils/test_periodic_report_product_project_evidence.py tests/utils/test_periodic_report_fulltext_llm_analysis.py -q
# 155 passed

git diff --check
# no output
```
