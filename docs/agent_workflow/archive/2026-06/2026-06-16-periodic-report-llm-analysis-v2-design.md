# Periodic Report LLM Analysis v2 Design

Date: 2026-06-16

## Goal

Replace the current keyword-heavy annual/semiannual report excerpt workflow with a more general, LLM-led analysis flow:

```text
annual/semiannual report text or PDF-derived text
  -> deterministic section/table evidence pack
  -> bounded LLM analyst
  -> deterministic number/entity fidelity validator
  -> human-reviewable annual report analysis
```

The core design shift is:

- Deterministic rules should locate generic A-share report structures.
- The LLM should decide what matters for this specific company and industry.
- Validators should prevent invented numbers, entities, citations, and fact promotion.

This is meant to solve the failure seen in 中简科技: a keyword extractor can find `T1100` and `碳纤维`, but those terms will not generalize to analog chips, software, pharmaceuticals, industrial automation, or consumer companies.

## Current Problem

The existing `periodic_report_extractor` improved from title-level extraction to useful deterministic snippets, but it still has structural limitations:

1. **Industry keywords do not generalize**
   - 中简科技 useful terms include `碳纤维`, `T1100`, `ZM40X`, `商业航天`.
   - These become noise or dead rules for semiconductor, SaaS, pharmaceutical, equipment, and consumer names.

2. **Short snippets lose company logic**
   - Current excerpts can show one product row or one risk paragraph, but do not reconstruct the company model:
     - What the company sells.
     - Which product line is growing or shrinking.
     - Which margin movement matters.
     - Whether management narrative matches financial tables.

3. **Table parsing needs LLM interpretation**
   - A-share reports frequently include broken PDF/Jina table text.
   - Deterministic parsing can locate tables, but LLM summarization is better for turning table fragments into business interpretation.

4. **Rules should not decide materiality**
   - Generic rules can identify `分产品`, `前五名客户`, `研发投入`, `存货`, `在建工程`.
   - Whether those signals are important depends on company context and cross-section comparison.

## Non-Goals

This phase does **not**:

- modify `KnowledgeSynthesizer`
- modify scoring, EV, risk scoring, technical analysis, or final recommendation
- put LLM annual-report analysis into core facts
- write to `knowledge/` by default
- change Source Intake merge or evidence-note behavior
- scrape Xueqiu, Zhihu, Agent-Reach, or social-media sources
- claim that LLM output is official fact
- expose hidden chain-of-thought

The output should be an auditable evidence map, not hidden reasoning.

## Proposed Architecture

### 1. Evidence Pack Builder

Create a deterministic builder that takes extracted annual/semiannual report text and emits a compact, typed evidence pack.

The builder should locate generic sections and tables, not industry-specific terms.

Recommended module:

```text
scripts/utils/periodic_report_evidence_pack.py
```

Primary API:

```python
def build_periodic_report_evidence_pack(text: str, *, report_type: str = "auto") -> dict:
    ...
```

Evidence block shape:

```python
{
    "id": "business_overview-0",
    "usage": "business_overview",
    "section": "第三节 管理层讨论与分析",
    "title": "报告期内公司从事的主要业务",
    "text": "...bounded excerpt...",
    "source_span": {"start": 420, "end": 540},
}
```

Allowed `usage` values:

- `business_overview`
- `industry_outlook`
- `business_model`
- `segment_table`
- `segment_margin_table`
- `region_table`
- `customer_supplier_table`
- `rd_table`
- `management_strategy`
- `risk_disclosure`
- `income_statement`
- `balance_sheet`
- `cash_flow`
- `ar_aging_note`
- `inventory_note`
- `capex_cip_note`
- `goodwill_note`
- `government_grant_note`
- `restricted_assets_note`
- `related_party_transactions`
- `contingencies_litigation`
- `subsequent_events`
- `shareholder_structure`
- `pledge`
- `commitments`
- `audit_opinion`

Caps:

- Max evidence blocks: 30
- Max chars per block: 2,000
- Max total chars into one LLM call: 30,000 by default
- Phase A uses one bounded LLM prompt. If evidence pack exceeds cap, select by priority and truncation; do not implement multi-call synthesis yet.
- Phase B may split into themed calls:
  1. business/industry/management
  2. tables and operating metrics
  3. financial notes and risks

### 2. LLM Annual Report Analyst

The LLM should receive the evidence pack, not raw full text.

It should output JSON only, with a schema designed around investment research questions:

```json
{
  "schema_version": "periodic_report_llm_analysis.v2",
  "company_profile": {
    "summary": "...",
    "evidence_refs": ["business_overview-0"]
  },
  "sections": [
    {
      "usage": "business_model",
      "title": "主营业务结构",
      "summary": "...",
      "evidence_refs": ["business_model-0", "segment_table-0"],
      "confidence": 80
    }
  ],
  "financial_risks": [
    {
      "risk_type": "customer_concentration",
      "summary": "...",
      "evidence_refs": ["customer_supplier_table-0", "ar_aging_note-0"],
      "severity": "high",
      "confidence": 85
    }
  ],
  "follow_up_questions": [
    {
      "question": "...",
      "evidence_refs": ["capex_cip_note-0"]
    }
  ]
}
```

Allowed analysis usages:

- `company_profile`
- `market_outlook`
- `business_model`
- `segment_performance`
- `margin_driver`
- `customer_concentration`
- `rd_progress`
- `capex_capacity`
- `cash_flow_quality`
- `balance_sheet_risk`
- `accounting_policy_risk`
- `management_claim_to_verify`

### 3. Fidelity Validator

V2 cannot rely only on prompt instructions. It must validate that LLM output is grounded in the referenced evidence.

Required deterministic checks:

- Every section has non-empty `evidence_refs`.
- Every `evidence_refs` id exists in the evidence pack.
- Reject raw URLs and Markdown citation markers.
- Reject `confirmed_fact`, `fact_candidate`, `核心事实`, `已证实`.
- Validate numeric grounding with three tiers:
  - **verbatim numbers**: concrete revenue, margin, customer share, balance-sheet, cash-flow, capex, inventory, AR, government-grant, and impairment values must appear in the union of referenced evidence after normalization.
  - **derived numbers**: allowed only when source operands appear in the same referenced evidence and the derivation is deterministic enough to reproduce, such as a growth rate from two consecutive-year values.
  - **contextual years**: the report year / 报告期 may appear in summaries from report metadata and should not be treated as invented.
- Validate product/customer/entity grounding using strict normalized substring matching in Phase A. Chinese NER, fuzzy aliases, and semantic entity matching are deferred to Phase B.
- Confidence must be integer in `[0, 100]`.
- Output remains:
  - `source_type: periodic_report_analysis`
  - `source_credit: 75`
  - `verification_status: professional_analysis`
  - `knowledge_eligible: False`

Important: this validator should check evidence fidelity, not investment correctness.

Failure policy:

- Invalid refs, illegal status markers, raw URLs, or citation markers reject the whole analysis.
- Invented numbers or invented entities drop the offending section / risk / question and keep the rest.
- If no valid analytical sections remain, reject the whole analysis.

### 4. Markdown Preview Renderer

Generate a human-reviewable preview, separate from the main stock report:

```text
/tmp/<stock>_<year>_annual_llm_analysis_v2.md
```

Preview sections:

1. 公司画像
2. 市场前景与行业格局
3. 主营业务与产品结构
4. 分产品收入与毛利率变化
5. 客户与订单结构
6. 研发进展与技术壁垒
7. 资本开支与产能消化
8. 财务质量与排雷观察
9. 管理层叙事待验证点
10. 后续跟踪问题

Each row should show:

- analysis conclusion
- evidence refs
- source section/table type
- confidence

Do not render hidden reasoning. Render only evidence-backed rationale summaries.

## Credit and Report Semantics

Annual/semiannual reports are official filings, but this LLM layer is not official filing text. Therefore:

- Original filing excerpts can remain high-credit official evidence.
- LLM analysis over filing excerpts is medium-credit professional analysis.
- LLM analysis cannot become a confirmed fact by itself.
- LLM analysis can guide human review and future Source Intake display only after validation.

Recommended wording:

- “年报管理层称……”
- “年报分产品表显示……”
- “财报附注提示……”
- “该项需要结合后续季度订单/转固/回款验证……”

Forbidden wording:

- “公司已证实……”
- “确定将带来……收入”
- “官方确认风险已经发生”
- “核心事实”

## 中简科技 Baseline Findings To Preserve

The v2 system should be able to recover these findings without industry-specific keyword rules:

1. **Company profile**
   - High-end carbon fiber supplier focused on aerospace.
   - Extends from fiber into prepreg / structural / functional materials.

2. **Market outlook**
   - Industry shifts from scale competition to value competition.
   - High-end aerospace carbon fiber remains scarce while low-end capacity is pressured.

3. **Segment performance**
   - Carbon fiber revenue declined; carbon fiber fabric revenue grew materially.
   - Fabric margin improved while carbon fiber margin declined.

4. **Customer concentration**
   - Top five customers account for nearly all sales.
   - First customer accounts for a very high share.

5. **R&D**
   - T1100 and ZM40X are material technology progress points.
   - R&D capitalization remains zero.

6. **Capex/capacity**
   - Fourth-phase project drives construction-in-progress growth.
   - Capacity digestion is explicitly disclosed as a risk.

7. **Financial risks**
   - AR total declined, but 1-2 year AR increased.
   - Inventory rose, especially finished goods.
   - Idle equipment impairment exists.

The key test is that these should emerge from generic section/table labels, not hardcoded `碳纤维`, `T1100`, or `商业航天` rules.

## Implementation Phases

### Phase A: Helper-only V2 Prototype

Allowed files:

- `scripts/utils/periodic_report_evidence_pack.py`
- `scripts/utils/periodic_report_llm_analysis_v2.py`
- `tests/utils/test_periodic_report_evidence_pack.py`
- `tests/utils/test_periodic_report_llm_analysis_v2.py`
- `docs/agent_workflow/*periodic-report-llm-analysis-v2-claude-notes.md`

No pipeline integration.
No Source Intake integration.
No main report changes.
No CLI unless review explicitly approves it.
Do not modify `scripts/utils/periodic_report_extractor.py`.
Do not modify `scripts/utils/periodic_report_llm_analysis.py`.

### Phase B: Runtime Preview Only

After tests pass, run a preview on 中简科技’s local annual report text.

Expected artifact:

```text
/tmp/zhongjian_2025_annual_llm_analysis_v2.md
```

The preview is for human review only.

### Phase C: Optional Source Intake / Report Display

Deferred until Phase A/B are accepted.

Requires separate design review.

## Test Plan

Evidence pack tests:

- locates management discussion without using company-specific terms
- extracts product/segment table blocks as raw bounded evidence
- extracts segment margin table blocks with revenue, cost, gross margin, and YoY columns when present
- extracts customer/supplier table blocks
- extracts R&D table blocks
- extracts risk disclosure blocks
- extracts AR aging, inventory, CIP, government grants, restricted assets when present
- extracts related-party, litigation/contingencies, subsequent-events, shareholder/pledge, and commitments blocks when present
- caps block length and total block count
- preserves source span/id stability

LLM analysis v2 tests:

- prompt includes evidence block ids and typed usages
- prompt does not include raw full report outside evidence pack
- validator rejects missing evidence refs
- validator rejects invented numbers
- validator rejects invented percentages
- validator rejects invented years
- validator allows contextual report year from metadata
- validator allows unit-normalized values such as `1.2亿元` vs `12000万元`
- validator allows derived growth rates only when source operands appear in referenced evidence
- validator drops sections with invented product/customer names
- validator rejects cross-evidence misattribution when the cited evidence lacks the number/entity
- validator handles table truncation artifacts without inventing missing digits
- validator rejects raw URLs and citation markers
- validator rejects `confirmed_fact` / `fact_candidate`
- validator keeps `source_credit: 75`
- validator returns `knowledge_eligible: False`
- renderer shows evidence refs and confidence
- validator rejects `periodic_report_llm_analysis.v1` schema for v2 output

Implementation note:

- Phase A may duplicate simple validation helpers from v1 to keep blast radius low. A later cleanup can extract shared citation/status/confidence validators after v2 proves useful.

Baseline fixture tests:

- With a small synthetic annual report, output can identify:
  - business model
  - segment performance
  - customer concentration
  - R&D progress
  - capex/capacity
  - financial risk

## Open Questions For Review

1. Should V2 use one large prompt with 40 evidence blocks, or split by theme into 2-3 calls?
2. Should the number/entity fidelity validator reject the whole analysis or only the offending section?
3. Should product/customer name validation use simple substring checks first, or a Chinese named-entity heuristic?
4. Should Phase A include a small CLI/smoke script for preview, or keep preview as a temporary local script?
5. Should `periodic_report_extractor.py` be retired later, or kept as a rule-only fallback?

## Recommendation

Proceed with **Phase A helper-only V2**.

Do not continue adding industry-specific extraction keywords. Keep deterministic code focused on generic report structure and tables, and let the LLM perform company-specific interpretation under strict evidence validation.

## Codex Follow-up After Round 1

Round 1 feedback is adopted as implementation contract:

- Use one bounded prompt for Phase A: max 30 evidence blocks and max 30,000 prompt evidence chars.
- Replace `product_margin_table` with `segment_margin_table` to avoid duplicating the same A-share `分行业/分产品/分地区` table.
- Add evidence usages for related-party transactions, litigation/contingencies, subsequent events, shareholder/pledge, and commitments.
- Implement numeric fidelity as verbatim / derived / contextual-year tiers.
- Implement entity fidelity as normalized substring checks only in Phase A; defer Chinese NER and fuzzy aliases.
- Drop offending sections for invented numbers/entities; reject whole analysis for invalid refs, illegal markers, raw URLs, citation markers, or no remaining valid sections.
- Do not modify v1 files in Phase A.

## Round 1 Feedback

- **Status**: Needs minor fixes
- **R2 Needed**: No — if the required deltas below are folded into the Phase A implementation task; otherwise Yes, solely to lock down the fidelity validator contract.

### Findings by Severity

#### High — must fix before task

1. **Fidelity validator "reject any Arabic number..." rule is under-specified and will false-positive.**
   - LLM summaries legitimately need to refer to years (e.g. "2025年"), and the report header itself contains the year. A strict substring-only check will reject benign summaries.
   - Growth rates/percentages are often not literal in evidence: a table may contain 2024 and 2025 revenue, and the LLM may write "营收同比增长 X%". The number X may not appear verbatim in the referenced block.
   - Unit normalization matters: evidence "1.2亿元" vs summary "12000万元" should be considered the same value, but simple substring check fails.
   - **Fix**: define three tiers in the validator contract:
     - (a) **verbatim numbers** — must appear in referenced evidence (e.g. specific revenue figures, customer share percentages).
     - (b) **derived numbers** — allowed only when both source operands appear in the same referenced evidence and the derivation is deterministic (e.g. growth rate from two consecutive years in a segment table).
     - (c) **contextual years** — the report year / 报告期 may appear in any summary because it is report metadata, not a newly introduced fact.
   - Reject or drop a section only for (a) violations; flag (b) for human review if derivation cannot be reproduced.

2. **Product/customer name validation needs a concrete strategy.**
   - The design says "Reject or flag product/customer names that do not appear in referenced evidence" but does not say how.
   - Simple substring is brittle: aliases, abbreviations, and OCR/PDF spacing artifacts will both false-negative (miss invented names) and false-positive (reject valid paraphrases).
   - **Fix**: Phase A should use strict substring over normalized tokens as a fail-safe, not a complete solution. Document that Chinese NER / fuzzy alias matching is deferred to Phase B. Add tests for invented product/customer names and for valid aliases that must pass.

#### Medium — should fix before task

3. **Evidence pack usage list has gaps for financial forensics.**
   - Current list covers business, tables, and common notes well, but omits several A-share forensics-relevant sections:
     - `related_party_transactions`（关联交易）
     - `contingencies_litigation`（或有事项、诉讼仲裁）
     - `subsequent_events`（期后事项、资产负债表日后事项）
     - `shareholder_structure` / `pledge`（股权质押、实控人变更）
     - `commitments`（重大承诺）
   - These are where annual-report red flags frequently hide. Add them to the usage list, even if Phase A only locates the heading and bounded text.

4. **`product_margin_table` and `segment_table` overlap.**
   - Most A-share reports have one "分产品/分行业/分地区" table that contains both revenue and margin. Splitting into `segment_table` and `product_margin_table` may duplicate blocks or confuse the LLM.
   - **Fix**: either merge into `segment_table` and let the LLM infer product vs. region vs. industry, or define a single `segment_margin_table` usage. Keep `product_margin_table` only if it specifically targets product-level gross margin tables separate from revenue breakdown.

5. **One big prompt vs. themed calls needs a Phase A decision.**
   - The design proposes 45k chars / 40 blocks as the default cap, with optional split into 2–3 themed calls. 45k chars is large enough to degrade model recall for mid-tier models; 40 blocks is also a lot of context.
   - **Fix**: recommend one bounded prompt for Phase A, but lower the default cap to ~30k chars / 25–30 blocks. Use the three themed splits as an explicit Phase B optimization, not as Phase A scope. This keeps the helper simple and testable.

6. **Phase A allowed files are safe, but add one explicit prohibition.**
   - The list correctly isolates the work. Add: "Do not modify `scripts/utils/periodic_report_extractor.py` or `scripts/utils/periodic_report_llm_analysis.py` (the v1 helper)." V2 should be a parallel prototype; retrofitting v1 can wait until v2 is proven.

#### Low — nice to have

7. **Preview renderer path uses `/tmp`.**
   - Writing to `/tmp/<stock>_<year>_annual_llm_analysis_v2.md` is acceptable for Phase B human review, but the design should clarify that this is display-only and must not be committed to `reports/`.

8. **Consider reusing v1 validator primitives.**
   - The existing `scripts/utils/periodic_report_llm_analysis.py` already implements citation-marker rejection, illegal-substring rejection, invalid-ref rejection, and confidence bounding. Phase A v2 will duplicate these.
   - **Fix**: acceptable for Phase A (new module, clean slate), but add a note that a follow-up refactor should extract shared validator helpers to avoid drift.

### Required Design Deltas

1. **Fidelity validator contract** — add the verbatim / derived / contextual-year tier rule above.
2. **Evidence usage list** — add `related_party_transactions`, `contingencies_litigation`, `subsequent_events`, `shareholder_structure`, `commitments`; clarify or merge `segment_table` / `product_margin_table`.
3. **Prompt cap** — default to one call with ~30k chars / 25–30 blocks; themed split is Phase B.
4. **Section-level failure mode** — for invented numbers/entities, drop the offending section and keep the rest; for invalid refs / illegal status markers / citation markers, reject the whole analysis.
5. **Phase A file prohibition** — explicitly forbid modifying v1 extractor and v1 LLM helper.
6. **Output metadata** — preserve `source_credit: 75`, `verification_status: professional_analysis`, `knowledge_eligible: False`, same as v1, until Phase C integration design.

### Missing Tests

The test plan is solid but should add the following focused cases:

1. **Invented number**: LLM summary contains "营收 5.3亿元" but referenced evidence only says "营收 4.1亿元" → section dropped or whole analysis rejected per contract.
2. **Invented percentage**: LLM writes "毛利率同比下降 3pct" but evidence only lists absolute margins, not the change → reject or flag.
3. **Unit-normalized number**: evidence "1.2亿元", summary "12000万元" → should pass if unit normalization is implemented.
4. **Derived growth rate**: evidence table contains 2024 revenue 100 and 2025 revenue 120 → LLM summary "营收同比增长 20%" should pass.
5. **Invented product name**: LLM claims "X100 芯片量产" but evidence only mentions "X80" → section dropped.
6. **Invented customer name**: LLM claims "成为华为供应商" but evidence only says "前五名客户 A" → section dropped.
7. **Cross-evidence misattribution**: LLM cites `business_overview-0` for a number that only appears in `segment_table-0` → invalid refs reject whole analysis.
8. **Table truncation artifact**: evidence block is truncated mid-number (e.g. "营收 12…"); LLM must not invent the missing digits.
9. **Core-fact leakage guard**: verify output `knowledge_eligible=False`, `source_credit=75`, and rejection of any `confirmed_fact` / `fact_candidate` / `核心事实` / `已证实` substring anywhere in the raw response.
10. **Evidence pack isolation**: builder output contains only bounded blocks; full report text outside blocks is not passed to the LLM.
11. **Source span/id stability**: running the builder twice on the same report produces identical ids for identical spans.
12. **Schema version**: validate `periodic_report_llm_analysis.v2` and reject v1.

### Open Questions

With the deltas above, the open questions can be resolved as follows:

1. **One large prompt vs. split?** → One prompt for Phase A, ~30k chars / 25–30 blocks. Themed split is Phase B.
2. **Reject whole analysis or offending section?** → Invalid refs / illegal markers / citation markers → whole analysis. Invented numbers/entities per section → drop section; if no valid sections remain, reject whole.
3. **Product/customer validation strategy?** → Strict normalized substring in Phase A; Chinese NER / alias fuzzy match deferred to Phase B.
4. **CLI/smoke script in Phase A?** → No committed CLI. Phase B preview can be a temporary local script; any committed CLI requires separate review.
5. **Retire `periodic_report_extractor.py`?** → Keep as rule-only fallback. Do not retire until v2 is proven across multiple industries and report types.

### Final Recommendation

Approve **Phase A helper-only V2** after the required design deltas are written into the task file. The architecture is materially better than continuing to stack industry keywords: generic section/table location plus LLM interpretation plus deterministic fidelity guards is the right long-term shape. The main risk is not the architecture but the fidelity validator — it must be contractually precise to avoid either letting invented numbers slip through or rejecting every useful summary. Do not proceed to Phase C (Source Intake / report display) until the fidelity validator has passing tests for invented numbers, invented entities, unit normalization, and derived growth rates.
