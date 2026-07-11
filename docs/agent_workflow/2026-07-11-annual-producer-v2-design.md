# Annual Producer v2 Design

**Status:** Approved after Round 2; ready for implementation planning
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

- the producer defaults to 12 cards per old type and 24 cards total;
- the annual material pack is called with `max_cards=8` and
  `per_type_limit=2`;
- the annual memo slices the selected narrative cards to the first eight;
- a separate optional LLM display-synthesis loader uses `max_cards=12` and
  `per_type_limit=3` as an input-context budget.

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
11. Canonical annual material has no count cap from producer through Chapter 4.
    The existing optional LLM display-synthesis item budget remains separate and
    may limit only LLM input, never the annual memo or Chapter 4 rows.
12. An annual card with `argument_complete=false` may appear in 4.1 but may not
    enter the 4.4 price-path rows, either alone or through a renderer fallback.

## 4. Canonical Schema Owner

Add a small module:

`scripts/utils/annual_argument_schema.py`

It owns:

- `CARD_SCHEMA_VERSION = "periodic_report_narrative_evidence_card.v2"`;
- `ENVELOPE_SCHEMA_VERSION = "periodic_report_narrative_evidence_cards.v2"`;
- `SELECTION_VERSION = "annual_argument_selection.v2"`;
- the five canonical family constants and order;
- family labels;
- the temporary v1-note adapter;
- `validate_source_unit(unit)`, `validate_card_v2(card)`,
  `is_v1_card(card)`, and `adapt_v1_card(card)` validation/migration helpers.

`validate_card_v2` requires every field in Section 6, rejects unknown family
values, verifies that `source_unit_ids` exactly match `source_units`, and checks
monotonic non-overlapping positions. The adapter emits the same v2 shape and
increments `v1_adapter_use_count`; it does not rerank, filter, or select cards.
Because a v1 note lacks block offsets, its in-memory adapter creates one
`<block_id>:legacy:<excerpt-hash>` unit over the excerpt proxy (`start_pos=0`,
`end_pos=len(excerpt)`), marks the card as legacy-adapted in diagnostics, and
forces `argument_complete=false`. Adapted cards are never persisted as v2 notes
and therefore cannot enter 4.4.

No renderer-specific text cleaning belongs in this module.

## 5. Canonical Families

| Family | Renderer label | Intended material |
| --- | --- | --- |
| `business_structure` | 业务结构 | Core business, product lines, customers, applications, and value-chain position |
| `operating_progress` | 经营变化 | Report-period sales, orders, capacity, customer adoption, delivery, and segment changes |
| `market_competition_outlook` | 管理层判断与行业展望 | Management industry view, competitive position, demand outlook, and future strategy |
| `technology_product_progress` | 技术与产品进展 | Technology platform, named product/project, validation, certification, launch, and mass-production progress |
| `financial_quality_explanation` | 财务质量与变化原因 | Financial facts plus company-explained margin, cash-flow, inventory, expense, impairment, and other financial changes |

These names are also the annual memo `display_group` values and
`MaterialRow.render_role` values. The intermediate roles `product_business`,
`operation_update`, `management_view`, `competitiveness_rd`, and
`financial_explanation` are deleted. Renderer headings remain Chinese labels,
not another machine-readable taxonomy. Formal financial fact and explanation
rows are assigned `financial_quality_explanation` explicitly by the memo builder;
title-based render-role inference is removed.

The same family-to-label table is used by formal-medium and formal-thin annual
sections. This migration does not change profile selection or formal-rich legacy
routing.

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

V2 cards do not emit `card_type`. That key exists only on v1 input consumed by
the temporary adapter. V2 note frontmatter and filenames use
`argument_family`; material-pack records expose the same field.

Each `source_units` entry is a first-class record:

```text
unit_id
block_id
ordinal
start_pos
end_pos
text
```

Positions refer to one whitespace-normalized, punctuation-preserving cleaned
source block. `unit_id` is deterministic as `<block_id>:u<ordinal>`.
`source_unit_ids` is the exact ordered projection of the embedded unit records.
Because a card may contain only contiguous units, `source_excerpt` is the exact
cleaned-block slice from the first unit's `start_pos` through the last unit's
`end_pos`, including normalized inter-sentence whitespace.
Every unit must be an exact substring at `[start_pos:end_pos]` in the cleaned
block, and positions and ordinals must be monotonic.

`argument_complete` is a boolean diagnostic boundary, not a display admission
tier. It is copied card -> note -> material pack -> annual memo ->
`MaterialRow`. The `MaterialRow` default is `false`; formal financial rows do not
become complete through title inference. `build_chapter4_view_model` admits only
annual rows with `argument_complete=true` to 4.4. If none exists, the annual
premise is omitted instead of falling back to an atomic row.

## 7. Source Units and Card Assembly

1. Normalize whitespace once per evidence block without deleting punctuation.
2. Split at complete Chinese or English sentence boundaries and materialize one
   SourceUnit record for every usable sentence.
3. Preserve punctuation, offsets, ordinal, and source order.
4. Start a card from the smallest source unit that is self-contained and has a
   concrete anchor.
5. Append only contiguous units that supply a missing subject, scope, evidence,
   progress state, or causal mechanism.
6. Stop once the argument is independently understandable and the next unit adds
   a different argument.
7. Split long material at sentence boundaries rather than truncating a clause.
8. Source units owned by one admitted card may not be wholly reused by another
   card from the same block.

One block may produce multiple cards when non-overlapping source units carry
different fact anchors. Candidate generation is source-unit-first: it emits at
most one candidate bundle for a given starting unit, then resolves that bundle to
one family. It never loops over families to create alternative candidates.

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

Atomic-fact admission is part of this one normal selector. There is no sparse
fallback selector. After hard noise filtering, any self-contained unit with a
concrete anchor must be admitted as either an atomic card or part of a complete
card. If such usable units exist but the producer emits no cards, it returns no
narrative cards and records `admission_invariant_violation`; it must not silently
substitute slogans or table fragments.

Reject:

- incomplete clauses or missing subjects;
- isolated labels, product names, or numbers;
- table headers and structural rows;
- regulatory boilerplate;
- generic slogans without a concrete object;
- malformed units or suspicious OCR fragments;
- source text containing model-added interpretation.

## 9. Family Assignment

Each candidate bundle is passed once to
`resolve_argument_family(bundle, usage_hint)`. The resolver collects signal
evidence from the core predicate and fact anchors, uses the usage hint only as a
weak tie-breaker, and returns one primary family plus `secondary_signals`. The
producer must not append one candidate per matched family.

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

When multiple primary signals remain, the precedence above is the final stable
tie-breaker. Tests cover at least management-view versus market-outlook,
technology capability versus product progress, and business description versus
report-period operating progress.

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

Only complete annual narrative cards are eligible as 4.4 annual premises.
Atomic annual facts remain visible in 4.1 but are never paired or promoted by a
renderer heuristic in v2. Broker and external 4.4 rules are unchanged.

## 11. Retention, Ordering, and Deduplication

There is no fixed total-card or per-family cap.

This applies end to end to the canonical annual path:

- remove producer `max_cards_per_type` and `max_total_cards` truncation;
- remove material-pack `max_cards`, `per_type_limit`, round-robin, and second
  fill-round truncation;
- remove the annual memo `valid_cards[:8]` slice;
- remove annual renderer `row_limit` / `rows[:row_limit]` truncation for both
  formal-medium and formal-thin projections;
- preserve all admitted rows through `MaterialRow` and formal-medium 4.1.

The optional LLM display-synthesis path retains its configured
`max_display_items` context budget. It takes a deterministic quality-ordered
slice after the uncapped pack is built and cannot alter the pack, memo, snapshot,
or Chapter 4 rows.

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

The primary invariant is one candidate per starting unit, one-family ownership,
and non-overlapping admitted source-unit ownership. Candidate count and final
admitted card count therefore cannot exceed usable source-unit count. A repeated
candidate identity, reused admitted unit, or count above usable units produces
`candidate_explosion` with affected block ids and no narrative-card output.

Existing table/noise gates continue to reject structural rows before admission.
When narrative cards are blocked or absent, annual memo retains deterministic
formal financial facts and explanations as fallback material.

## 13. Diagnostics Contract

The diagnostics envelope uses these stable keys:

```text
source_blocks_seen
source_units_seen
usable_units
candidates_by_family
admitted_by_family
argument_complete_counts
rejection_counts
missing_families
candidate_explosion
candidate_explosion_block_ids
admission_invariant_violation
v1_adapter_use_count
cards[]: card_id, source_unit_ids, fact_anchors, secondary_signals,
         score_parts, selection_reason
```

`rejection_counts` has stable reason keys: `incomplete`, `no_anchor`,
`table_noise`, `ocr_damage`, `boilerplate`, `duplicate`,
`reused_source_units`, and `invalid_unit`.

Diagnostics remain profile/debug payload only and are not rendered in report
body text.

## 14. Migration Plan

### Batch A: Canonical v2 path

1. Add `annual_argument_schema.py`.
2. Replace the old producer taxonomy and selector with the one v2 family path;
   delete `_CARD_TYPES`, `_USAGE_TO_CARD_TYPES`, `_CARD_TYPE_MARKERS`,
   `_truncate_cards`, and `_select_diverse_cards` rather than retaining a
   parallel producer. Replace the old per-type marker table with compact generic
   predicate/anchor signals keyed only by the five families.
3. Materialize SourceUnit records before card assembly and write only v2 cards
   and notes.
4. Add the read-only v1-note adapter in the schema owner.
5. Remove canonical-path caps from producer, pack, annual memo, and Chapter 4.
6. Make material pack, annual memo, `MaterialRow`, and renderer consume canonical
   family names directly. Delete the `card_group` mapping and
   `classify_annual_render_role` title inference in this batch.
7. Add `argument_complete` to `MaterialRow` and filter annual 4.4 rows in
   `build_chapter4_view_model` before the renderer sees them.
8. Write the concrete schema and selection versions from Section 4. A note is
   current only when both equal v2; otherwise it is adapted read-only and marked
   for refresh.
9. Do not delete the adapter until real-report acceptance passes and
   `v1_adapter_use_count` is zero for all refreshed samples.

When v1 and v2 notes coexist during Batch A, the loader groups them by source
block plus normalized excerpt identity and prefers v2. Only an unshadowed v1
note is adapted and counted. The adapter never makes a second selection decision.

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
2. verify active note directories contain v2 notes only and adapter use is zero;
3. remove or archive migrated v1 notes, then remove the v1 adapter and mapping;
4. delete residual old card-type titles, loader compatibility branches, tests,
   and marker helpers that no longer serve generic noise/anchor detection;
5. merge duplicate pack/loader ordering and validation helpers;
6. run the final runtime/test line audit.

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
| 4.4 completeness boundary | Atomic annual row appears in 4.1 but not 4.4; complete row may appear in both |
| End-to-end uncapped annual path | More than 12 distinct cards survive producer, pack, memo, snapshot, and 4.1 |
| LLM context budget isolation | Optional display-synthesis slicing does not change pack/memo/4.1 counts |
| Admission invariant | Usable anchored unit plus zero cards fails closed without invoking fallback selection |
| Schema validation | Invalid family, unit ids, positions, or selection version are rejected |
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

### 赛微微电 (sparse A-share)

- retain self-contained official single-point disclosures;
- do not fill missing families with slogans or table fragments.
- use the checked-in `赛微微电_2025_annual_jina.txt` cache for producer, pack,
  memo, and snapshot acceptance; a full report is not required because the stock
  is not in `config/stocks.json`.

### 黑芝麻智能 (HK)

- preserve Traditional Chinese source units;
- retain HK usage mapping and source boundaries;
- do not require A-share-specific headings or metrics.

复旦微电、中际旭创、 and 黑芝麻智能 must pass their available single-stock
report entry plus report quality, source boundary, citation alignment, CI grep,
and whitespace checks. 赛微微电 must pass the producer-to-snapshot integration
acceptance plus the same applicable source/citation/CI checks.

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

- Batch A runtime net-add target is no more than +80 lines, with a +100 hard
  stop. The target is net because old producer and display-role code is deleted
  in the same batch.
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

Expected replacement/deletion budget:

| Existing runtime | Batch |
| --- | --- |
| `_CARD_TYPES`, `_USAGE_TO_CARD_TYPES`, `_CARD_TYPE_MARKERS`, per-type candidate loop | A |
| `_truncate_cards`, `_select_diverse_cards`, producer count parameters | A |
| material-pack `_select_records` round-robin and count parameters | A |
| annual memo `card_group` and `valid_cards[:8]` | A |
| `classify_annual_render_role` and intermediate annual roles | A |
| annual renderer `row_limit` / `rows[:row_limit]` | A |
| v1 adapter/map and old-type note fixtures | B |
| residual old title/loader compatibility helpers | B |
| duplicate pack/loader ordering and validation helpers | B |

## 20. Design Delta after Round 1

**Accepted:** canonical families now replace intermediate render roles directly;
`argument_complete` is wired through `MaterialRow` and strictly filters annual
4.4 rows; SourceUnit has a concrete positional record; family resolution is a
single deterministic call; schema, selection version, diagnostics, samples, and
deletion targets are explicit.

**Rejected:** the suggested separate sparse-report fallback would create a
second selector. Atomic facts instead pass the unified admission path, and an
unexpected empty result becomes `admission_invariant_violation`. Removing the
existing LLM display `max_display_items` was also rejected because it is a token
context budget, not a canonical material cap; tests enforce that it cannot alter
the annual report path.

**Deferred:** External Producer v2 and any LLM prompt or memo change remain out of
scope.

**R2 required:** yes. Round 2 must verify direct display-role propagation, the
strict 4.4 boundary, SourceUnit ownership, cap isolation, and the revised runtime
deletion budget before implementation planning.

## 21. External Producer

External Producer v2 is explicitly deferred. Annual v2 must complete both
migration batches and formal acceptance before external claim extraction,
narrative composition, or display producer behavior is redesigned.
