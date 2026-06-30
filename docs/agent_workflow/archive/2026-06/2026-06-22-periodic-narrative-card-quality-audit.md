# Periodic Narrative Card Quality Audit

Date: 2026-06-22

Scope: review the current experimental `periodic_narrative_cards` Knowledge samples for four stocks:

- 赛微微电
- 华大九天
- 中际旭创
- 德邦科技

This audit is read-only against Knowledge cards. It does not change extractor rules, pipeline behavior, scoring, fulltext LLM, or source intake.

## 1. Current Sample Counts

| Stock | Total cards | Main card types |
| --- | ---: | --- |
| 赛微微电 | 4 | business_model 2, rd_product_progress 2 |
| 华大九天 | 24 | business_model 5, financial_note 9, management_market_view 5, market_outlook 2, operation_update 1, rd_product_progress 2 |
| 中际旭创 | 9 | business_model 3, management_market_view 4, margin_competitiveness 1, market_outlook 1 |
| 德邦科技 | 20 | business_model 2, financial_note 4, management_market_view 6, margin_competitiveness 2, market_outlook 4, rd_product_progress 2 |

## 2. Overall Verdict

Status: usable as experimental Knowledge material, but not yet ready for broad automatic rollout.

The strongest cards already provide real incremental value for LLM reading: company business boundaries, product platforms, R&D/product progress, competitive position, industry structure, and management outlook. The weak cards are mostly low-value financial-note fragments, accounting-policy snippets, duplicated outlook sentences, and occasional excerpts ending mid-sentence.

The current Knowledge metadata is safe for the experimental layer:

- `source_type: periodic_report_narrative_evidence`
- `source_credit: 75`
- `knowledge_eligible: false`
- `knowledge_fact_status: narrative_evidence`
- `synthesis_eligible: false`
- `experimental: true`

## 3. Good Examples

### 德邦科技 — R&D/Product Progress

File: `knowledge/10-Stocks/德邦科技/periodic_narrative_cards/2025-annual-rd-product-progress-0.md`

Value: high.

The card captures TIM1 thermal interface material, high-power chip thermal management, application scenarios, core additives, process design, and thermal stability. This is exactly the kind of annual-report text that normal financial data sources do not preserve.

### 德邦科技 — Margin/Competitiveness

File: `knowledge/10-Stocks/德邦科技/periodic_narrative_cards/2025-annual-margin-competitiveness-0.md`

Value: high.

The card captures advanced packaging materials, mature mass supply, Underfill/DAF/CDAF/Lid materials, validation/import status, and leading packaging customers. This is useful for company moat, customer verification, and product-stage reasoning.

### 中际旭创 — Industry Demand

File: `knowledge/10-Stocks/中际旭创/periodic_narrative_cards/2025-annual-management-market-view-2.md`

Value: high.

The card captures 800G/1.6T/3.2T demand timing and market-size forecast. This is company-specific enough for LLM synthesis and avoids hardcoding optical-module keywords globally.

### 华大九天 — Competitive Landscape

File: `knowledge/10-Stocks/华大九天/periodic_narrative_cards/2025-annual-management-market-view-2.md`

Value: high.

The card captures EDA global oligopoly, first/second/third tier positioning, and domestic vendor gap. This is useful for competitive-position reasoning.

## 4. Weak Examples

### Accounting Policy Noise

File: `knowledge/10-Stocks/华大九天/periodic_narrative_cards/2025-annual-financial-note-4.md`

Problem: low-value accounting policy.

The card is about borrowing cost capitalization recognition principles. It is technically from the annual report, but it is not useful for understanding the company unless tied to a specific unusual financing or asset-construction issue.

Suggested fix: financial_note should prefer company-specific explanations with phrases like `主要系`, `原因说明`, `较上年同期`, `减值`, `回款`, `现金流`, `商誉`, `存货跌价`; penalize generic accounting-policy headings like `确认原则`, `计量方法`, `会计政策`, `借款费用资本化`.

### Mid-sentence Truncation

Files:

- `knowledge/10-Stocks/华大九天/periodic_narrative_cards/2025-annual-management-market-view-0.md`
- `knowledge/10-Stocks/中际旭创/periodic_narrative_cards/2025-annual-business-model-0.md`

Problem: excerpts end with `…` in the middle of a thought.

Suggested fix: improve excerpt clipping to prefer sentence/semicolon boundaries before adding ellipsis. If no boundary exists within a small look-back window, keep current behavior.

### Form Marker Noise

Files:

- `knowledge/10-Stocks/德邦科技/periodic_narrative_cards/2025-annual-market-outlook-3.md`
- `knowledge/10-Stocks/德邦科技/periodic_narrative_cards/2025-annual-management-market-view-5.md`
- `knowledge/10-Stocks/华大九天/periodic_narrative_cards/2025-annual-financial-note-3.md`

Problem: useful text is mixed with annual-report form markers such as `√适用 □不适用` or `适用 □不适用`.

Suggested fix: strip checkbox markers during excerpt cleanup while preserving the selected content.

### Duplicate Outlook / Strategy Cards

Example:

- 德邦科技 `market_outlook-3`
- 德邦科技 `management_market_view-5`

Problem: same strategy paragraph can be classified into two card types.

Suggested fix: add cross-type de-duplication by normalized excerpt hash or high-overlap text similarity. Prefer the more specific type when both match:

1. `rd_product_progress`
2. `margin_competitiveness`
3. `market_outlook`
4. `management_market_view`
5. `business_model`
6. `financial_note`

## 5. Card Type Quality

| Card type | Current quality | Notes |
| --- | --- | --- |
| business_model | Good | Stable and useful, but can include sales/procurement mode fragments; okay for LLM context. |
| rd_product_progress | Good when hit | High value; should keep expanding by annual-report glossary/product terms rather than hardcoded one-stock keywords. |
| margin_competitiveness | Good but sparse | Very valuable when captured; needs broader anchors around `毛利率`, `同比提升`, `客户导入`, `批量供货`, `国产化`, `验证`. |
| management_market_view | Mixed | Captures real market view, but sometimes overlaps with market_outlook or strategy paragraphs. |
| market_outlook | Mixed | Valuable for industry trend, but must avoid duplicating management_market_view. |
| financial_note | Weakest | Some useful cash-flow/impairment notes, but too many generic accounting-policy fragments. Needs stronger filters. |
| operation_update | Sparse | Currently underrepresented; likely needs better anchors around产销、订单、客户、项目、交付、产能、库存. |

## 6. Recommended Next Fix Bucket

Do one focused extractor-quality bucket before writing more stock samples:

1. Financial-note noise filter:
   - penalize generic accounting policy phrases;
   - keep company-specific causal explanations.
2. Excerpt clipping:
   - prefer `。`, `；`, `;`, `！`, `？` boundary before truncating;
   - avoid ending on a half phrase when a nearby boundary exists.
3. Checkbox cleanup:
   - remove `√适用 □不适用`, `适用 □不适用`, `□适用 不适用` from excerpts.
4. Cross-type de-duplication:
   - de-duplicate identical or near-identical excerpts across card types;
   - keep the more specific type.

Suggested validation set:

- 赛微微电: ensure sparse-but-clean behavior remains acceptable.
- 华大九天: reduce financial_note accounting-policy noise.
- 中际旭创: reduce mid-sentence truncation.
- 德邦科技: keep TIM/advanced-packaging/high-value cards and reduce duplicated strategy/outlook cards.

## 7. Go / No-Go

Go for a small extractor-quality iteration.

No-go for broad batch writing across more stocks until the above four quality issues are improved and re-audited. The current sample set is useful for calibration, not yet a default all-stock ingestion path.
