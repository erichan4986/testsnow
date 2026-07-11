# Annual Producer v2 Design

**Status:** Proposed and user-approved for Level 3 review
**Date:** 2026-07-11
**Scope:** Deterministic annual-report narrative material only

## 1. Objective

Replace the overlapping eight-type periodic narrative card taxonomy with one
canonical five-family argument schema. Improve annual-report material coverage,
argument integrity, deduplication, and diagnostics while reducing duplicate
classification logic across the producer, material pack, memo, snapshot, and
renderer.

Annual Producer v2 must preserve all concrete, self-contained, non-duplicate
official-report material. It must not use fixed business-level card-count caps.

## 2. Current Problems

The current producer mixes several classification dimensions:

- `business_model` describes an object;
- `operation_update` describes a time state;
- `management_market_view` describes the speaker;
- `market_outlook` describes direction;
- `margin_competitiveness` mixes a metric and competitive position;
- `technology_platform` describes capability;
- `rd_product_progress` describes an event;
- `financial_note` is a catch-all.

One evidence usage can map to two or three card types. The same text is then
deduplicated within selected scopes, mapped again in `annual_report_material_pack`,
mapped again in `synthesis_skills.py`, and sometimes inferred from titles in
`deep_analysis_material_snapshot.py` or the renderer.

The current runtime also applies inconsistent budgets:

- the cache intake builds at most 12 narrative cards across eight old types;
- the annual material pack uses `max_cards=8` and `per_type_limit=2`;
- its second fill round can exceed the per-type limit;
- a separate synthesis-item loader uses `max_cards=12` and `per_type_limit=3`.

This can produce material imbalance. The current 中际旭创 sample selected four
management-view cards and three business-model cards while omitting operating
progress and other families.

## 3. Non-Negotiable Invariants

1. New cards contain only complete source sentence units copied from the annual
   report. They may concatenate contiguous units in original order but may not
   paraphrase source text.
2. The producer does not call an LLM and does not change any LLM prompt.
3. The producer does not feed scoring, risk scoring, target price, technical
   analysis, executive-summary claims, or final recommendation paths.
4. Formal financial fact and explanation packs remain separate authoritative
   inputs and are not replaced by narrative cards.
5. Each card has exactly one canonical family.
6. Material retention has no fixed total or per-family business cap.
7. Sparse reports may retain self-contained official single-point disclosures.
8. Noise, fragments, unsupported numeric units, table rows, and generic slogans
   remain rejectable even when material is sparse.
9. Citation identity and source boundaries must remain unchanged.
10. There must be only one v2 selector. A v1 adapter may translate persisted
    notes during migration but may not select material independently.

## 4. Canonical Schema Owner

Add a small module:

`scripts/utils/annual_argument_schema.py`

It owns:

- card and envelope schema versions;
- the five canonical family constants and order;
- family labels;
- the temporary v1-note adapter;
- schema validation helpers.

No renderer-specific text cleaning belongs in this module.

## 5. Canonical Families

| Family | Intended material |
| --- | --- |
| `business_structure` | Core business, product lines, customers, applications, and value-chain position |
| `operating_progress` | Report-period sales, orders, capacity, customer adoption, delivery, and segment changes |
| `market_competition_outlook` | Management industry view, competitive position, demand outlook, and future strategy |
| `technology_product_progress` | Technology platform, named product/project, validation, certification, launch, and mass-production progress |
| `financial_quality_explanation` | Margin, cash flow, inventory, expenses, impairment, and company-explained financial changes |

These names flow unchanged through annual memo `display_group` and
`MaterialRow.render_role`. Downstream code must not translate them into another
taxonomy.

## 6. Card v2 Shape

Each new card contains at least:

```text
schema_version
selection_version
card_id
argument_family
argument_complete
title
source_block_id
source_unit_ids
source_units
source_excerpt
fact_anchors
secondary_signals
score_parts
quality_score
selection_reason
source_type
source_credit
report_year
report_type
```

`source_excerpt` is the ordered join of `source_units`. Every source unit must be
a substring of the cleaned source block, and unit positions must be monotonic.

`argument_complete` is a boolean diagnostic boundary, not a display admission
tier. `false` cards may be displayed as official single-point disclosures but
must not independently feed Chapter 4 price-path inference.

## 7. Source Units and Card Assembly

1. Split each evidence block at complete Chinese or English sentence boundaries.
2. Preserve punctuation and source order.
3. Start a card from the smallest source unit that is self-contained and has a
   concrete anchor.
4. Append only contiguous units that supply a missing subject, scope, evidence,
   progress state, or causal mechanism.
5. Stop once the argument is independently understandable and the next unit adds
   a different argument.
6. Split long material at sentence boundaries rather than truncating a clause.
7. Source units owned by one admitted card may not be wholly reused by another
   card from the same block.

One block may produce multiple cards when non-overlapping source units carry
different fact anchors.

## 8. Unified Admission Contract

A card is admitted when it is complete enough to understand independently and
contains at least one concrete fact anchor.

Fact anchors include:

- named products, projects, technologies, customers, or applications;
- business or segment names;
- report periods, dates, or progress states;
- metrics with valid units;
- operating changes;
- company-stated causes or mechanisms.

Both of these are admissible:

- a single official fact such as a named product entering mass production;
- a complete argument connecting a change or judgment to evidence or mechanism.

Reject:

- incomplete clauses or missing subjects;
- isolated labels, product names, or numbers;
- table headers and structural rows;
- regulatory boilerplate;
- generic slogans without a concrete object;
- malformed units or suspicious OCR fragments;
- source text containing model-added interpretation.

## 9. Family Assignment

Each card receives exactly one `argument_family`. Classification uses the
evidence-block usage hint, core predicate, and fact anchors.

Deterministic precedence is based on the card's primary assertion:

1. metric plus a company-stated cause or financial mechanism →
   `financial_quality_explanation`;
2. named technology/product plus validation, launch, certification, or production
   progress → `technology_product_progress`;
3. report-period operating change plus sales, orders, capacity, customer, or
   delivery anchor → `operating_progress`;
4. management industry, competition, demand, or future judgment →
   `market_competition_outlook`;
5. descriptive product, customer, application, or value-chain scope →
   `business_structure`.

Other family signals are retained in `secondary_signals`. They do not cause card
duplication.

If one source block contains two separable assertions, different non-overlapping
unit sets may form separate cards.

## 10. Completeness and Quality Score

Quality score affects ordering, not normal material count.

Positive score parts:

- self-contained sentence and explicit subject;
- named product, project, customer, or application;
- valid metric and report period;
- concrete progress or operating change;
- causal explanation or mechanism;
- `argument_complete=true`.

Penalty parts:

- OCR, table, page, or contents noise;
- dangling fragments;
- generic industry slogans;
- repeated source units;
- missing or invalid numeric units;
- semantic duplication.

`argument_complete=true` requires a change/judgment plus at least one supporting
fact, scope, or mechanism. A self-contained official fact without that support is
still admitted with `argument_complete=false`.

## 11. Retention, Ordering, and Deduplication

There is no fixed total-card or per-family cap.

Ordering is deterministic:

1. place the highest-quality card from every populated family;
2. order remaining cards by quality, source order, and card id;
3. keep every remaining card that contributes a new fact anchor or distinct
   source argument.

Drop a card only when:

- its normalized source-unit identity exactly duplicates an admitted card;
- it reuses the same source units from the same block;
- it has the same primary family and anchor signature and adds no distinct
  period, metric, progress state, product, customer, application, or mechanism;
- existing deterministic text similarity confirms it is a restatement.

Different products, metrics, periods, or mechanisms remain distinct even when
their wording is similar.

## 12. Candidate Explosion and Failure Behavior

Normal material is not limited by count. An internal candidate explosion must
fail closed rather than silently keep the first N rows.

The primary invariant is one-family ownership and non-overlapping source-unit
ownership. Final admitted card count therefore cannot exceed usable source-unit
count. Violating this invariant produces `candidate_explosion` with the affected
block ids and no narrative-card output.

Existing table/noise gates continue to reject structural rows before admission.
When narrative cards are blocked or absent, annual memo retains deterministic
formal financial facts and explanations as fallback material.

## 13. Diagnostics Contract

Producer diagnostics include:

- source blocks and usable source units seen;
- candidates and admitted cards by family;
- `argument_complete` true/false counts;
- per-card fact anchors, secondary signals, score parts, and selection reason;
- rejection reasons: `incomplete`, `no_anchor`, `table_noise`, `ocr_damage`,
  `boilerplate`, `duplicate`, `reused_source_units`, and `invalid_unit`;
- `missing_family` values;
- candidate-explosion status and block ids;
- v1 adapter use count during migration.

Diagnostics remain profile/debug payload only and are not rendered in report
body text.

## 14. Migration Plan

### Batch A: Canonical v2 path

1. Add `annual_argument_schema.py`.
2. Replace the old producer taxonomy and selector with the v2 family path.
3. Write only v2 cards and notes.
4. Add a read-only v1-note adapter in the schema owner.
5. Make material pack, annual memo, MaterialRow, and renderer consume canonical
   family names directly.
6. Advance the selection version so current notes refresh.
7. Do not delete the adapter until real-report acceptance passes.

The adapter maps old cards as follows:

- `business_model` → `business_structure`;
- `operation_update` → `operating_progress`;
- `management_market_view` and `market_outlook` →
  `market_competition_outlook`;
- `technology_platform` and `rd_product_progress` →
  `technology_product_progress`;
- `financial_note` → `financial_quality_explanation`;
- `margin_competitiveness` uses its excerpt: company-explained metric changes map
  to `financial_quality_explanation`; competitive-position content maps to
  `market_competition_outlook`.

### Batch B: Remove legacy taxonomy

After A-share rich, A-share sparse, and HK samples pass:

1. refresh all configured stocks that have local periodic-report caches;
2. remove the v1 adapter;
3. remove old eight-type constants, markers, selection priority, and tests;
4. remove synthesis, snapshot, and renderer remapping/inference helpers;
5. remove migrated old notes;
6. run final runtime/test line audit.

The v1 adapter is not a permanent compatibility path.

## 15. Expected File Scope

Runtime scope:

- `scripts/utils/annual_argument_schema.py` (new, small)
- `scripts/utils/periodic_report_narrative_evidence_cards.py`
- `scripts/utils/annual_report_material_pack.py`
- periodic narrative note writer/loader as required by schema refresh
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`

Test scope is limited to corresponding producer, pack, synthesis, snapshot,
renderer, quality, and source-boundary tests.

No scoring, target-price, risk-scoring, technical-analysis, recommendation,
collection, browser, or LLM-prompt files are allowed.

## 16. Requirement-Test Matrix

| Requirement | Required evidence |
| --- | --- |
| Five canonical families | Positive and negative fixture for every family |
| Single-family ownership | Ambiguous multi-signal card emits once with secondary signals |
| Original source preservation | Every source unit is an ordered substring of its block |
| Official single-point disclosure retained | Self-contained fact admitted with `argument_complete=false` |
| Complete argument preferred | Complete card ranks above otherwise comparable atomic fact |
| Same block may emit multiple cards | Distinct non-overlapping product/metric assertions survive |
| No source-unit reuse | Overlapping duplicate card is rejected |
| No hidden count cap | More than 12 distinct high-quality cards all survive |
| Semantic novelty | Different products, periods, metrics, and mechanisms survive |
| Duplicate removal | Same family and anchor signature restatement is removed |
| Sparse-report behavior | Useful atomic facts survive without low-quality fill |
| Candidate explosion | Ownership invariant violation fails closed with block ids |
| v1 migration | Old notes adapt once and v2 selection version forces refresh |
| Direct family propagation | Memo display group equals MaterialRow render role |
| Citation hygiene | No visible missing/unused/malformed references |
| Source boundary | Narrative cards remain official, non-scoring material |
| No business-path regression | Scoring/risk/target/technical/recommendation outputs unchanged |

## 17. Real-Report Acceptance

### 复旦微电

- distinct FPGA, EEPROM/NOR/NAND, MCU, customer/application, and report-period
  operating-progress anchors must not be lost;
- business structure and operating progress must not duplicate the same units;
- financial explanations remain attributed to official material.

### 中际旭创

- operating progress must be represented when present;
- management outlook and business description must not consume all material;
- product-rate and demand-outlook repetitions must deduplicate without deleting
  distinct periods or products.

### Sparse A-share sample

- retain self-contained official single-point disclosures;
- do not fill missing families with slogans or table fragments.

### HK sample

- preserve Traditional Chinese source units;
- retain HK usage mapping and source boundaries;
- do not require A-share-specific headings or metrics.

Every sample must pass report quality, source boundary, citation alignment, CI
grep gates, and whitespace checks.

## 18. Failure Modes

| Failure | Visible symptom | Required detector |
| --- | --- | --- |
| Over-filtering sparse material | Empty annual narrative despite concrete official facts | Atomic-fact admission tests and sparse real sample |
| Family overlap persists | Same sentence appears in multiple report groups | Single-family/source-unit ownership tests |
| Product or metric loss | Distinct lines disappear during dedupe | Anchor-preservation tests and baseline coverage diff |
| Hidden cap remains | Later valid cards disappear after a fixed count | More-than-12-card test |
| Table/OCR leak | Broken rows appear in 4.1 | Noise fixtures and manual real-report review |
| Legacy mix | v1/v2 notes coexist or stale notes are reused | Selection-version migration tests |
| Citation drift | Visible annual row has missing/unused ref | Reporter quality/source-boundary tests |
| Candidate explosion | Hundreds of structural cards enter material pack | Ownership invariant and fail-closed diagnostics |
| Downstream leak | Annual cards affect score or recommendation | Byte-for-byte business-path invariants |

## 19. Budgets and Stop Conditions

- Batch A temporary runtime net addition target: no more than +80 lines.
- Batch B final runtime reduction target: 110–180 lines against the pre-v2 base.
- If final reduction is under 80 lines, legacy-path deletion must be audited
  before declaring completion.
- Stop if implementation introduces a second selector.
- Stop if passing a sample requires stock- or industry-specific classification
  rules.
- Stop if distinct baseline fact anchors decrease without an explicit rejection
  reason accepted in review.
- Stop on citation, source-boundary, scoring, risk, target, technical, or
  recommendation regression.
- Stop if v1 adapter remains after migration acceptance.

## 20. External Producer

External Producer v2 is explicitly deferred. Annual v2 must complete both
migration batches and formal acceptance before external claim extraction,
narrative composition, or display producer behavior is redesigned.
