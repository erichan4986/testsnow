# Periodic Report LLM Analysis v2 Phase A — Implementation Notes

**Date**: 2026-06-16
**Task**: Implement helper-only v2 of periodic report LLM analysis (evidence pack + bounded LLM + fidelity validator).

## Changed Files

- `scripts/utils/periodic_report_evidence_pack.py` (new)
- `scripts/utils/periodic_report_llm_analysis_v2.py` (new)
- `tests/utils/test_periodic_report_evidence_pack.py` (new)
- `tests/utils/test_periodic_report_llm_analysis_v2.py` (new)
- `docs/agent_workflow/2026-06-16-periodic-report-llm-analysis-v2-claude-notes.md` (this file)

No other files were modified. In particular, the v1 files remain untouched:
- `scripts/utils/periodic_report_extractor.py`
- `scripts/utils/periodic_report_llm_analysis.py`

## Test Commands and Results

After the invalid-ref fix:

```bash
python3 -m pytest tests/utils/test_periodic_report_llm_analysis_v2.py -q
# 26 passed in 0.14s

python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_llm_analysis_v2.py -q
# 40 passed in 0.15s

python3 -m pytest tests/utils/test_periodic_report_extractor.py tests/utils/test_periodic_report_llm_analysis.py -q
# 44 passed in 0.33s
```

All focused v2 tests, combined evidence/v2 tests, and the unrelated v1 regression tests pass.

## What Was Implemented

### `scripts/utils/periodic_report_evidence_pack.py`

Public API:

- `build_periodic_report_evidence_pack(text, *, report_type="auto")` — deterministic generic section/table locator.

Key behaviors:

- Returns `schema_version: "periodic_report_evidence_pack.v1"`.
- Detects `report_type` and `audit_status` from report headings and audit-opinion text.
- Extracts blocks by generic A-share section subheadings (no industry/product keywords).
- Extracts table blocks by header/content classification:
  - `segment_margin_table` / `segment_table`
  - `region_table`
  - `customer_supplier_table`
  - `rd_table`
- Supported note/section usages include related-party, contingencies/litigation, subsequent events, shareholder structure, pledge, commitments, audit opinion, AR aging, inventory, CIP, government grants, restricted assets, etc.
- Caps: max 30 blocks, max 2,000 chars per block.
- Stable ids assigned as `{usage}-{index}` for identical inputs.
- Includes `source_span` with `start`/`end` positions.

### `scripts/utils/periodic_report_llm_analysis_v2.py`

Public API:

- `build_periodic_report_llm_v2_prompt(evidence_pack, *, max_blocks=30)` — bounded prompt builder.
- `validate_periodic_report_llm_v2_output(raw_text, evidence_pack)` — deterministic JSON/fidelity validator.
- `summarize_periodic_report_with_llm_v2(evidence_pack, client)` — end-to-end helper returning a credit-typed analysis.
- `render_periodic_report_llm_v2_markdown(analysis)` — human-review Markdown preview.

Key behaviors:

- `SCHEMA_VERSION = "periodic_report_llm_analysis.v2"`.
- Prompt contains only evidence-pack block ids/usages/texts; full report text is not included.
- Default prompt cap: 30 blocks, 30,000 total chars.
- Duck-typed LLM client: supports `.chat(prompt)` or `.chat.completions.create(...)`.
- No OpenAI/DeepSeek import at module load.
- Validator rejects whole analysis on:
  - JSON parse failure
  - schema version mismatch (v1 rejected)
  - invalid/missing evidence refs in `company_profile`, `sections`, `financial_risks`, or `follow_up_questions`
  - raw URLs
  - Markdown citation markers
  - `confirmed_fact` / `fact_candidate` / `核心事实` / `已证实` anywhere in parsed content
- Validator drops individual sections/risks on:
  - unknown `usage` / `risk_type`
  - missing/invalid confidence
  - confidence outside `[0, 100]`
  - invented numbers/percentages not grounded in referenced evidence
  - invented product/customer/supplier names not found in referenced evidence
- Numeric fidelity tiers:
  - **verbatim numbers**: must appear in referenced evidence after unit normalization (e.g. `1.2亿元` ↔ `12000万元`)
  - **derived growth rates**: allowed when two operand values in referenced evidence reproduce the rate
  - **contextual years**: report-year references like `2024 年度` / `2024年` are allowed
- Entity fidelity: explicit mentions after `客户`/`产品`/`供应商` must appear in referenced evidence (strict substring, normalized whitespace).
- Output metadata:
  - `source_type`: `periodic_report_analysis`
  - `source_credit`: 75
  - `verification_status`: `professional_analysis`
  - `claim_status`: `professional_analysis`
  - `knowledge_eligible`: False
  - `report_eligible`: True
- Empty evidence pack returns an empty analysis without calling the client.

## Validator Behavior Summary

The validator is evidence-fidelity-only, not investment-correctness:

1. Refs are checked fail-closed: every analytical object (`company_profile`, `sections`, `financial_risks`, `follow_up_questions`) must reference existing block ids. Invalid or missing refs in any of these objects reject the whole analysis.
2. Illegal status markers and citation syntax are rejected at the analysis level.
3. Each section/risk/question is independently checked for numeric and entity grounding; failures drop that object, not the whole analysis.
4. If no valid objects remain, the whole analysis is rejected.

## 2026-06-16 Invalid Evidence-Refs Fix

Previously, invalid `evidence_refs` in a single section, financial risk, or follow-up question were silently dropping that object while keeping the rest of the analysis. This allowed an LLM to smuggle unsupported claims alongside supported ones.

Fix applied:

- `_normalize_sections`, `_normalize_financial_risks`, and `_normalize_questions` now call `_reject_invalid_evidence_refs` directly (no try/except swallowing).
- Any invalid/missing refs in these objects raise `PeriodicReportLLMv2Error("invalid evidence_refs")`, causing the whole analysis to be rejected.
- `company_profile` already rejected invalid refs; behavior unchanged.

Tests added:

- `test_validator_rejects_invalid_refs_in_sections`
- `test_validator_rejects_invalid_refs_in_financial_risks`
- `test_validator_rejects_invalid_refs_in_follow_up_questions`

## Did We Access Network / Run Real LLM / Chrome / Full Report?

- **Network**: No.
- **Real LLM**: No. All tests use `FakeChatClient` / `FakeCompletionClient`.
- **Chrome/CDP**: No.
- **Xueqiu detail scraping**: No.
- **Full stock report**: No.
- **CLI added**: No.
- **Source Intake / evidence notes / pipeline wiring**: No.

## Deviations from Design

- The design allowed both `segment_table` and `segment_margin_table`. In the implementation, a table that contains revenue/cost/margin columns is classified as `segment_margin_table`; a plain revenue-only table would be `segment_table`. This avoids duplicate blocks for the same underlying table.
- The default prompt cap is 30 blocks / 30,000 chars (per Round 1 feedback), not 40 / 45,000.
- Multi-call themed synthesis is not implemented; Phase A uses one bounded prompt.
- Chinese NER / fuzzy alias matching for entity fidelity is out of scope; Phase A uses strict normalized substring matching for explicit `客户`/`产品`/`供应商` mentions.

## 2026-06-16 Phase A.1 Fixes

### Changed Files

- `scripts/utils/periodic_report_evidence_pack.py`
  - Rewrote table extraction to handle real annual-report layouts:
    - blank lines between rows,
    - multi-line cells (R&D project tables),
    - adjacent tables separated by headings or blank lines.
  - Added generic table header/boundary detection using A-share structural tokens (分产品/分行业/分地区/前五名客户/主要研发项目名称/研发投入等) rather than company-specific keywords.
  - Kept max 30 blocks / 2,000 chars per block and stable ids.
- `scripts/utils/periodic_report_llm_analysis_v2.py`
  - Added a strict JSON schema example to the system prompt, listing allowed fields for each object and forbidding `content`/`description`/`name`/`industry`/top-level `summary`/string-list questions.
  - Added `_normalize_top_level_keys` to reject unsupported top-level fields.
  - Made `_normalize_questions` reject string-list `follow_up_questions`.
- `tests/utils/test_periodic_report_evidence_pack.py`
  - Added real-layout fixtures for segment margin, customer/supplier, and R&D tables.
- `tests/utils/test_periodic_report_llm_analysis_v2.py`
  - Added tests for strict schema prompt, unsupported fields, and string-list follow-up questions.

### Test Results

```bash
python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_llm_analysis_v2.py -q
# 48 passed in 0.23s

python3 -m pytest tests/utils/test_periodic_report_extractor.py tests/utils/test_periodic_report_llm_analysis.py -q
# 44 passed in 0.54s
```

### Strict Schema Prompt

Fixed. `build_periodic_report_llm_v2_prompt()` now includes a full JSON schema example and explicit field allow-lists. Validator rejects unsupported top-level fields and string-list questions, and drops objects whose only analytical content is in unsupported fields (`content`/`description`) when no valid `summary` is present.

### Real-Layout Table Capture

Verified against `/tmp/zhongjian_2025_annual_jina.txt` logic using small in-test fixtures:

- `segment_margin_table` block contains:
  - `443,494,353.42` (碳纤维 revenue)
  - `55.21%` / `-19.59%` / `-8.79%`
  - `碳纤维织物` / `75.46%` / `54.60%` / `13.38%`
- `customer_supplier_table` block contains:
  - `99.42%` top-five concentration
  - `客户 A` / `87.49%`
- `rd_table` block contains:
  - `T1100`, `ZM40X`
  - `可批量供货`, `项目目标已达成`

No whole financial note is misclassified as a table that squeezes out the business tables.

### Deviations

- The prompt schema example is stricter than the original design; it explicitly enumerates allowed nested keys rather than relying on prose rules.
- Table extraction is now header-driven and tolerates Jina-style blank-line row separation; this is a broader change than a simple regex tweak.

### Blockers

None. Phase A.1 remains helper-only, touches only the allowed files, and does not require network, real LLM, Chrome, Source Intake, or full report runs.

## 2026-06-16 Codex Follow-up Verification Fixes

### Extra Issues Found

- Real `/tmp/zhongjian_2025_annual_jina.txt` still missed late R&D projects in `rd_table` because the R&D table exceeded the generic 70-line table window. `T1100` was retained, but late rows such as `ZM40X` were dropped.
- The v2 validator was too strict for useful but grounded LLM summaries:
  - rounded yuan-unit amounts such as `4.43亿元` did not match source values such as `443,494,353.42元`;
  - model/product code numbers inside `T1100` / `ZM40X` / `ZT8E-12K` were treated as standalone financial numbers.

### Additional Changes

- `scripts/utils/periodic_report_evidence_pack.py`
  - Added a dedicated `_RD_TABLE_MAX_LINES = 180` while keeping ordinary tables at 70 lines.
- `scripts/utils/periodic_report_llm_analysis_v2.py`
  - Added rounded large-number evidence matching within 1% for yuan amounts.
  - Ignored numeric tokens adjacent to ASCII letters so model codes do not fail number fidelity.
- `tests/utils/test_periodic_report_evidence_pack.py`
  - Added a long multiline R&D table regression test where `ZM40X` appears after 80 continuation lines.
- `tests/utils/test_periodic_report_llm_analysis_v2.py`
  - Added tests for rounded yuan-unit matching and product-code numeric tokens.

### Verification

```bash
python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_llm_analysis_v2.py -q
# 51 passed in 0.24s

python3 -m pytest tests/utils/test_periodic_report_extractor.py tests/utils/test_periodic_report_llm_analysis.py -q
# 44 passed in 0.43s
```

Real 中简科技 evidence pack check:

- `segment_margin_table`: contains `443,494,353.42`, `55.21%`, `碳纤维织物`, `75.46%`.
- `customer_supplier_table`: contains `99. 42%`, `87.4 9%`.
- `rd_table`: contains `T1100`, `ZM40X`, `可批量供货`, `项目目标已达成`.

Real LLM preview was run once against DeepSeek and wrote only `/tmp` files:

- `/tmp/zhongjian_2025_annual_v2_analysis.md`
- `/tmp/zhongjian_2025_annual_v2_analysis.json`
- `/tmp/zhongjian_2025_annual_v2_evidence_pack.json`
- `/tmp/zhongjian_2025_annual_v2_raw_response.json`

Validated preview now keeps 7 sections and 3 financial risk observations. It includes 主营业务表现、客户集中度、研发进展、资本开支与产能建设、资产负债表风险、会计政策风险、管理层表述待验证.

### Remaining Caution

The section currently named `资本开支与产能建设` may include broader annual-report “投资状况分析” amounts, not pure fixed-asset capex. Later display/integration should label this as “资本开支/投资状况” or split pure capex from broad investment amount.

## 2026-06-16 Codex Phase A.2 Coverage Expansion

### Motivation

User-provided GPT summary of 中简科技 2025 annual report showed that v2 still missed several high-value evidence categories: product/capacity profile, sales certification model, production/sales/inventory, R&D spend/personnel/capitalization, AR customer concentration, bills receivable, asset impairment, cash-flow capex, financial assets, audit key matters, and governance dissent.

### Changes

- `scripts/utils/periodic_report_evidence_pack.py`
  - Added bounded keyword-window extraction for annual-report evidence that generic section/table slicing tends to lose.
  - Added usages:
    - `product_capacity_profile`
    - `sales_certification_model`
    - `production_sales_inventory_table`
    - `rd_investment_table`
    - `management_market_view`
    - `ar_customer_concentration_note`
    - `bills_receivable_note`
    - `asset_impairment_note`
    - `cash_flow_capex_table`
    - `financial_assets_note`
    - `audit_key_matters`
    - `governance_dissent`
  - Tightened boilerplate filtering so `合格供方目录` is no longer deleted just because it contains `目录`.
- `scripts/utils/periodic_report_llm_analysis_v2.py`
  - Expanded allowed `sections[].usage` and `financial_risks[].risk_type` for these new evidence classes.
  - Updated prompt allow-list text; evidence refs and fidelity checks remain fail-closed.
- Tests
  - Added fixtures for product/capacity/sales-certification, production-sales-inventory, R&D investment, financial-risk notes, expanded LLM usages, and expanded risk types.

### Verification

```bash
python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_llm_analysis_v2.py -q
# 57 passed

python3 -m pytest tests/utils/test_periodic_report_extractor.py tests/utils/test_periodic_report_llm_analysis.py -q
# 44 passed
```

Real local pack check against `/tmp/zhongjian_2025_annual_jina.txt`:

- HIT `product_capacity_profile`
- HIT `sales_certification_model`
- HIT `production_sales_inventory_table`
- HIT `rd_investment_table`
- HIT `rd_table`
- HIT `management_market_view`
- HIT `ar_customer_concentration_note` with `98.81%`
- HIT `bills_receivable_note`
- HIT `asset_impairment_note`
- HIT `cash_flow_capex_table`
- HIT `financial_assets_note`
- HIT `audit_key_matters`
- HIT `governance_dissent`

### Scope

Helper-only. No Source Intake wiring, no report pipeline changes, no real LLM call, no network, no Chrome/CDP, no full report run.

## 2026-06-16 Codex Effect Preview Follow-up

### Additional Fixes After Preview

The first real v2 preview improved coverage but still showed two extraction weaknesses:

- `product_capacity_profile` stopped at the numbered subheading `1、高性能碳纤维（可定制）` and missed product/capacity details.
- `rd_investment_table` stopped at the R&D personnel age table and missed `研发投入金额`, `研发投入占营业收入比例`, and `研发支出资本化的金额`.

Fixes:

- Expanded keyword windows for annual-report profile and R&D investment blocks.
- Allowed numbered subheadings inside `product_capacity_profile`, `sales_certification_model`, `rd_investment_table`, `production_sales_inventory_table`, and `cash_flow_capex_table`.
- Added regression fixtures mirroring Jina-style numbered product sections and long R&D personnel/investment tables.

### Latest Verification

```bash
python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_llm_analysis_v2.py -q
# 59 passed

python3 -m pytest tests/utils/test_periodic_report_extractor.py tests/utils/test_periodic_report_llm_analysis.py -q
# 44 passed
```

### Latest Real Preview

Ran one real DeepSeek preview against `/tmp/zhongjian_2025_annual_jina.txt`.

Outputs:

- `/tmp/zhongjian_2025_annual_v2_analysis_after_a2.md`
- `/tmp/zhongjian_2025_annual_v2_analysis_after_a2.json`

Result shape:

- sections: 10
- financial_risks: 4
- follow_up_questions: 2

Notable sections now present:

- 主营业务表现
- 客户集中度
- 产销存信号
- 研发投入
- 研发进展
- 投资活动现金流
- 管理层市场观点
- 销售与认证模式
- 产品与产能概况
- 经营模式

Notable risks now present:

- customer_concentration
- ar_customer_concentration
- inventory_risk
- asset_impairment

Remaining limitation:

- Cash-flow capex evidence is improved enough for a conservative section, but `购建固定资产、无形资产和其他长期资产支付的现金` is split across lines in Jina text and may need a dedicated cross-line note extractor before Source Intake integration.

## 2026-06-16 Codex Evidence Digest Reframe

### Change

User clarified that the annual/semiannual report output should be an intermediate material layer for the final report, not a second standalone investment report.

Updated `periodic_report_llm_analysis_v2.py` accordingly:

- Reframed the helper as `定期报告证据摘要`.
- Prompt now states the output is `中间素材`, not a final report.
- Prompt explicitly forbids buy/sell advice, position advice, and valuation conclusions.
- Prompt frames the desired content as `年报事实 + 管理层解释 + 可跟踪问题`.
- Markdown renderer title changed from `年报/半年报 LLM 分析预览` to `定期报告证据摘要`.
- Renderer disclaimer now says the digest does not directly provide valuation conclusions, buy/sell advice, or position advice.

### Numeric Retention Fix

After user feedback that the first A.2 preview lost key figures, added prompt-level metric rules:

- Critical evidence blocks include `metric_rule` in the user prompt.
- System prompt requires key numbers for income, margin, production/sales/inventory, R&D investment, customer concentration, cash flow, and impairment.
- Added validator support/test for `百分点` wording when evidence contains the same percentage delta.

### Verification

```bash
python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_llm_analysis_v2.py -q
# 63 passed

python3 -m pytest tests/utils/test_periodic_report_extractor.py tests/utils/test_periodic_report_llm_analysis.py -q
# 44 passed
```

### Latest Preview

Generated:

- `/tmp/zhongjian_2025_annual_v2_digest.md`
- `/tmp/zhongjian_2025_annual_v2_digest.json`
- also refreshed `/tmp/zhongjian_2025_annual_v2_analysis_after_a2.md`

The latest digest retains key figures:

- 2025 revenue `846,092,620.66`, YoY `4.14%`
- carbon fiber revenue `443,494,353.42`, YoY `-19.59%`, margin `55.21%`, margin delta `-8.79pct`
- carbon fiber fabric revenue `402,520,846.01`, YoY `54.60%`, margin `75.46%`, margin delta `13.38pct`
- sales volume `315,326.80 KG`, production `388,277.44 KG`, inventory `94,938.11 KG`, inventory YoY `150.95%`
- R&D spend `117,509,715.58`, R&D/revenue `13.89%`, R&D staff `75`, capitalization `0.00`
- top-five customers `99.42%`, customer A `87.49%`, AR top-five `98.81%`

Scope remains helper-only: no Source Intake wiring, no report pipeline changes, no scoring/risk changes.
