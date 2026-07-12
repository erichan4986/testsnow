# Annual Producer v2 Coverage Repair Design

**Status:** Proposed for Claude Round 1 read-only review  
**Date:** 2026-07-12  
**Scope:** Deterministic annual-report evidence-pack selection, source-unit admission, and v1-to-v2 migration coverage only.

## 1. Decision

Keep one Annual Producer v2 schema and one SourceUnit-first selector. Repair the
upstream evidence-pack coverage failure before attempting Batch B legacy removal.

The evidence pack will use a cap of **48 blocks**. Before applying its existing
priority order, it reserves one high-value narrative block for every populated
canonical family. The remaining capacity is then filled by the existing
deterministic usage priority. There is no per-family business cap and no second
card selector.

The repair adds explicit document style handling for `a_share_annual`,
`hkex_annual`, and `unknown`. Hong Kong reports remain in the same producer and
schema, but their management-discussion paragraphs may satisfy an
implicit-subject rule that is not appropriate for A-share checkbox/table text.

## 2. Why This Is Needed

The local refresh acceptance found three distinct failures that were previously
collapsed into `v1_adapter_use_count`:

| Failure | Evidence | Repair boundary |
| --- | --- | --- |
| Upstream omission | Zhongji's `business_overview-0` ranked 33rd after dedupe and was cut by `_MAX_BLOCKS = 30`. | Evidence-pack allocator |
| Valid HK narrative rejected | Black Sesame's SESAMEX and full-stack platform paragraph reached the pack but lacked an explicit company subject. | Style-aware atomic admission |
| Valid A-share cause rejected with form noise | Zhongjian's payment-method and cash-flow explanation shared a block with `applicable/not applicable` markers. | Source-boundary extraction before unit admission |
| False migration-loss signal | Shengbang's long v1 excerpt was already represented by split v2 SourceUnits, but exact excerpt equality did not prove that. | Material-pack coverage audit |

`v1_adapter_use_count` must therefore no longer be interpreted as a count of
facts that v2 failed to retain. It remains a migration diagnostic only.

## 3. Scope and Non-Goals

In scope:

- `periodic_report_evidence_pack.py` evidence block allocation and document-style
  metadata;
- shared usage-to-family ownership in the annual schema;
- deterministic A-share and HK source-boundary admission rules;
- material-pack diagnostics that distinguish v2 coverage from true recovery
  needs;
- focused unit tests and a local-cache refresh acceptance gate.

Out of scope:

- LLM prompts, LLM memos, `KnowledgeSynthesizer`, collection, network access,
  or PDF/OCR fetching;
- scoring, target price, risk score, technical analysis, executive summary, and
  final recommendation;
- Chapter 4 renderer wording or profile routing;
- deleting or archiving any existing v1 Knowledge note in this repair.

## 4. Invariants

1. A v2 card still contains only direct, ordered source substrings represented by
   SourceUnits. No repair paraphrases annual-report text.
2. The canonical five-family schema remains the only v2 taxonomy:
   `business_structure`, `operating_progress`,
   `market_competition_outlook`, `technology_product_progress`, and
   `financial_quality_explanation`.
3. The family reservation is an evidence-block allocator, not a second producer
   candidate selector. A block is selected once; SourceUnit admission and family
   resolution still happen once downstream.
4. A missing family produces no synthetic placeholder. The allocator reserves a
   slot only when a real high-value narrative candidate exists.
5. The 48-block cap is an input-context safety cap, not a card-output cap.
   Cards, memo rows, and Chapter 4 annual material remain uncapped after
   admission.
6. `argument_complete=false` annual cards remain excluded from Chapter 4.4.
7. A legacy v1 note is never hidden or archived until deterministic source-unit
   coverage proves that all of its meaningful factual fragments survive in v2.
8. HK-specific acceptance may be selected only by report style plus generic
   structural anchors. It must not use stock, industry, issuer, or product-name
   allowlists.
9. A-share form-marker cleanup can select an exact source substring after a
   marker, but must never rewrite the wording or promote a table/header fragment.
10. Source credit, citations, and report-year/report-type provenance remain
    unchanged.

## 5. Architecture

### 5.1 One shared usage-to-family resolver

`annual_argument_schema.py` becomes the owner of a public deterministic usage
metadata table and helper:

```text
canonical_family_for_usage(usage) -> canonical family | None
is_high_value_narrative_usage(usage) -> bool
```

The table is the one owner of both values, rather than separate producer and
evidence-pack lists. `is_high_value_narrative_usage` is true only for these
generic usages:

```text
business_structure:
  business_overview, business_model, product_capacity_profile,
  sales_certification_model, hk_business_overview, hk_customer_ecosystem
operating_progress:
  management_strategy
market_competition_outlook:
  management_market_view, industry_outlook, market_demand_outlook,
  competitive_position, future_strategy, hk_market_outlook
technology_product_progress:
  rd_product_progress, hk_product_progress
financial_quality_explanation:
  profitability_commentary, hk_financial_commentary
```

All table, statement, and structural usages are explicitly false. This moves the
current usage fallback knowledge out of the producer so the evidence pack and
producer cannot drift into two taxonomies. It is a hint for evidence allocation
only; `resolve_argument_family(bundle, usage_hint)` remains the sole v2
card-family resolver.

The helper maps only generic usages such as `business_overview`,
`product_capacity_profile`, `rd_product_progress`, `cash_flow_capex_table`,
`hk_business_overview`, and `hk_financial_commentary`. An unrecognized usage has
no reservation and is still eligible through the normal fill pass.

### 5.2 Evidence-pack document style

`build_periodic_report_evidence_pack()` emits:

```text
document_style: a_share_annual | hkex_annual | unknown
```

The existing deterministic `_looks_like_hk_report()` determines `hkex_annual`.
For non-HK annual reports the value is `a_share_annual`; all other cases are
`unknown`. The producer reads this envelope field only to choose an admission
policy and records it in envelope diagnostics. It is not added as a renderer
field or a new card-schema field.

### 5.3 Family-reserved 48-block allocator

The existing dedupe step continues to establish a deterministic candidate list.
The final selection changes from `blocks[:30]` to this two-pass algorithm:

1. Group deduplicated blocks by `canonical_family_for_usage(block["usage"])`.
2. Within each populated family, find its best high-value narrative block using
   `is_high_value_narrative_usage`, the existing usage priority, and stable
   source order. A candidate must also contain at least one complete sentence or
   semicolon-delimited clause with 24 non-whitespace characters. Table,
   statement, checkbox, and structural usages are never family-reserved.
3. Select at most one such reserve block per family in canonical family order.
4. Fill the remaining capacity, up to 48 total, from the normal globally sorted
   block list. Already reserved blocks are skipped. Existing `USAGE_PRIORITY`,
   usage limits, and stable tie-breaking remain authoritative in this pass.
5. If fewer than 48 blocks exist, keep all selected blocks. Do not manufacture
   a block for an absent family.

The allocator deliberately protects business overview and comparable narrative
coverage from being starved by tables, but does not elevate every narrative block
above formal financial evidence. It is deterministic and preserves the existing
priority behavior outside the one-per-populated-family reservation.

### 5.4 A-share form-marker source boundaries

For `a_share_annual`, an otherwise useful evidence block containing an
`applicable/not applicable` marker is not automatically admitted or rejected as
a whole. The extraction layer will identify exact sentence/line spans after the
marker and may emit a child narrative block only when all conditions hold:

- the span is a direct contiguous substring of the cleaned block;
- it contains a concrete causal, operating, product, or financial anchor;
- it is not a table header, checkbox-only answer, or generic boilerplate; and
- the parent usage is compatible with narrative explanation.

The original noisy structural fragment remains rejectable. This preserves the
Zhongjian payment-method explanation without weakening the existing broad
checkbox-noise tests.

### 5.5 HKEX implicit-subject admission

For `hkex_annual`, an atomic paragraph from an HK management-discussion usage
may be self-contained despite omitting an explicit `company/group/business`
subject when it has a generic structural anchor:

- a named platform, product, solution, or ecosystem; and
- an action, application, capability, customer/market context, or progress
  predicate in the same source unit.

The acceptance is limited to HK narrative usages such as
`hk_business_overview` and `hk_product_progress`. It does not admit arbitrary
bullet labels, tables, or slogan-like text. Traditional Chinese source text and
source offsets are retained exactly.

### 5.6 Legacy-v1 migration coverage audit

`annual_report_material_pack.py` will classify each readable legacy note against
v2 cards from the same `source_block_id`:

| Classification | Meaning | Pack behavior |
| --- | --- | --- |
| `exact_shadowed` | Current exact normalized excerpt identity matches a v2 card. | Do not adapt v1. |
| `covered_by_v2_units` | Every meaningful legacy fragment is an exact normalized substring of one v2 SourceUnit or an ordered contiguous v2 SourceUnit sequence from that block. | Do not adapt v1; record coverage proof. |
| `needs_recovery` | At least one meaningful factual legacy fragment has no deterministic v2 source-unit proof. | Keep the v1 adapter active and record the missing fragments. |

Meaningful fragments are complete sentence or semicolon-delimited source
fragments with a concrete fact anchor. Checkbox-only noise, headings, empty
fragments, and generic boilerplate do not create a recovery obligation.

New diagnostics include at least:

```text
v1_exact_shadowed_count
v1_unit_covered_count
v1_needs_recovery_count
v1_adapter_use_count
v1_recovery_examples
```

This closes the Shengbang false positive while leaving Zhongji's actually missing
business paragraph and Black Sesame's platform fact visibly recoverable. A
legacy note is never deleted by this classification. Batch B removal remains
blocked until all configured-stock recovery counts reach zero after a real local
refresh.

## 6. Failure Modes and Gates

| Failure mode | Observable symptom | Required gate |
| --- | --- | --- |
| Reservation crowds out financial evidence | 48-block pack loses the top-ranked financial summary/table. | Synthetic priority-order allocator test |
| Family reserve adds a second selector | Same source block/card appears through two selection paths. | One-allocation-path unit test and code review |
| HK rule accepts unsupported bullets | A short HK label becomes a v2 card. | HK negative admission test |
| A-share cleanup weakens checkbox filtering | Checkbox/table payload becomes a card. | Existing checkbox regressions plus causal-tail positive test |
| Fragment coverage hides a lost legacy fact | Adapter count falls while a concrete legacy sentence has no v2 proof. | Material-pack `needs_recovery` test |
| Fragment coverage duplicates v1 material | Split v2 units and an old long note both appear. | `covered_by_v2_units` suppression test |
| Cap grows without control | A pathological annual report sends unbounded source text downstream. | Explicit `len(blocks) <= 48` test |
| Report-style detection misroutes unknown input | Nonannual/nonHK data uses special rules. | Style classification tests |

## 7. Test and Acceptance Matrix

Focused tests must cover:

1. 48 is the hard evidence-pack limit and selection is deterministic.
2. A block ranked below the old 30 limit, including a business overview, survives
   when it is the only high-value narrative candidate for its family.
3. Existing high-priority financial/table blocks still survive the reserve pass.
4. A report with no candidate in a family emits no fabricated placeholder.
5. `a_share_annual` causal tail after a checkbox marker is kept as an exact source
   substring, while the structural checkbox fragment is still rejected.
6. `hkex_annual` platform/product narrative with an implicit subject is admitted;
   a platform-only label is rejected.
7. A v1 long excerpt split across valid v2 SourceUnits is
   `covered_by_v2_units` and does not increment adapter use.
8. A genuinely omitted legacy factual fragment is `needs_recovery`, remains
   adapted, and appears in recovery diagnostics.
9. `argument_complete` and 4.4 admission behavior remain unchanged.
10. Current formal-medium/formal-thin renderer and source-boundary focused tests
    remain green.

Local-cache acceptance, after implementation, refreshes the same eight stocks
without network access. It must show:

- Zhongji's main-business block selected by v2;
- Black Sesame's HK platform fact admitted under the HKEX rule;
- Zhongjian's payment-method/cash-flow cause admitted without its checkbox
  boilerplate;
- Shengbang's split v2 product fact marked `covered_by_v2_units`, not recovered
  through the adapter;
- no configured stock has `v1_needs_recovery_count > 0` before Batch B is
  reconsidered.

Only after that refresh succeeds may a report-generation acceptance begin.

## 8. Complexity Budget and Stop Conditions

Target runtime delta is at most +80 lines, with a hard stop at +100 net lines.
The implementation must replace the current final cap slice and exact-only
legacy shadow logic rather than layer a parallel allocator or migration system
alongside them. It may add tests and design notes beyond this runtime budget.

Stop implementation and return to design if any of these occur:

- a separate HK producer, a second card selector, or a stock/industry-specific
  allowlist becomes necessary;
- the rule needs text rewriting rather than direct source-substring selection;
- evidence-pack output cannot be kept at or below 48 blocks;
- a configured stock still has `v1_needs_recovery_count > 0` after the proposed
  repair;
- runtime net growth exceeds +100 lines;
- any path reaches scoring, target, risk, technical, recommendation, LLM, or
  collection logic.

## 9. Design Delta From Annual Producer v2 Batch A

Accepted:

- Repair upstream coverage before deleting the adapter.
- Explicitly distinguish HKEX annual-report formatting from A-share form
  semantics while keeping one v2 producer.
- Use a family-reserved allocator and raise only the evidence-pack cap to 48.
- Replace exact-note-only migration shadowing with source-unit coverage proof.

Deferred:

- Legacy note archival/deletion.
- Producer changes beyond annual-report evidence packs.
- Renderer/readability changes and formal-medium profile changes.

Rejected:

- Unbounded evidence packs. They would make prompt/input and runtime behavior
  unpredictable even though downstream annual cards have no business cap.
- A separate sparse fallback or a separate HK selector. Both would duplicate
  selection semantics and undermine v2's single admission contract.

## 10. Claude Round 1 Review Questions

Review only this design. Do not modify code, tests, reports, or Knowledge notes.

1. Does family reservation preserve the one-selector invariant and avoid an
   accidental second taxonomy?
2. Are the `a_share_annual` and `hkex_annual` admission boundaries strict enough
   to avoid false positives while retaining the proven missing facts?
3. Is the `covered_by_v2_units` proof strong enough to suppress duplicate v1
   adaptation without hiding a lost factual fragment?
4. Is the 48-block cap and the +100 runtime hard stop proportionate to the
   observed cache distribution and implementation scope?
5. Are the test and local-cache acceptance gates sufficient before Batch B
   adapter removal is reconsidered?
