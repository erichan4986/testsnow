# Annual Producer v2 Admission Repair Design

**Status:** Revised after Claude Round 1; Round 2 required
**Date:** 2026-07-12
**Scope:** Deterministic annual-report evidence-pack to v2 card admission only.

## 1. Decision

Keep one source-first Annual Producer v2 path. It must not read v1 notes,
renderer output, or report material packs while producing cards.

For a block with a schema-mapped usage, its canonical family is the primary
family except for a strong financial-explanation override. Text signals remain
useful as secondary signals and for unmapped usages, but they no longer reroute
other mapped source material into a different primary family. This eliminates
cross-family duplication without a card-count cap while preserving the existing
financial explanation contract.

Producer admission becomes bundle-first:

1. Materialize normalized SourceUnits from one evidence-pack block.
2. Reject only source-structural noise before bundling.
3. Start a bundle at a self-contained factual seed.
4. Append only adjacent, non-noise continuation units that extend the same
   canonical-family argument.
5. Resolve and admit the whole source substring once.

The v1 adapter remains a read-only material-pack fallback until the eight-stock
coverage gate reaches zero. It is not a producer input.

## 2. Problem Evidence

After the annual coverage repair, the local refresh still reports nonzero
v1_needs_recovery_count for Black Sesame, Zhongjian, SGT Micro, Espressif,
and Zhongji Innolight. The retained legacy material includes concrete product,
customer, causal-financial, business-model, and competition facts.

The current producer has two related failures:

- signal precedence can route a mapped source block into an unrelated primary
  family, creating duplicate cards while starving its usage family;
- it rejects a continuation SourceUnit before it can join the preceding factual
  seed, so a multi-sentence annual-report argument is fragmented or lost.

The evidence-pack cap and SourceUnit coverage proof are not relaxed in this
repair. The coverage proof remains exact and ordinal-contiguous.

## 3. Source-Only Admission Model

### 3.1 Family Resolution

resolve_argument_family(text, usage_hint) follows this order:

1. If text passes strong_financial_explanation(text), return
   financial_quality_explanation with selection_reason =
   financial_override:financial_quality_explanation.
2. Otherwise, if canonical_family_for_usage(usage_hint) exists, return it as
   primary with selection_reason = usage_primary:<family>.
3. Preserve all text-detected families other than the primary as ordered
   secondary_signals.
4. If usage is unmapped and no financial override applies, retain the existing
   signal-precedence resolver and use selection_reason =
   signal_primary:<family>.

The override is intentionally narrow: it requires both a financial metric and
an explanatory or change relation. It preserves the current
management_market_view profitability-commentary test while preventing generic
numeric market outlook text from becoming a financial card.

    strong_financial_explanation(text):
        return has_financial_metric(text) and (
            has_causal_or_financial_action(text)
            or has_financial_change(text)
        )

| Usage class | Strong financial explanation | Primary family |
| --- | --- | --- |
| profitability_commentary or hk_financial_commentary | yes or no | financial_quality_explanation |
| any other mapped usage | yes | financial_quality_explanation |
| any other mapped usage | no | canonical usage family |
| unmapped usage | yes | financial_quality_explanation |
| unmapped usage | no | existing signal precedence |

This is a routing rule, not a second selector. A source excerpt continues to
produce at most one card.

### 3.2 SourceUnit States

Each normalized SourceUnit receives one internal state:

- noise: existing structural, policy, table, page-marker, risk, or definition
  rejection applies;
- seed: the unit is a self-contained factual statement for the canonical
  family, or an existing HK implicit-subject admission succeeds;
- continuation: the unit is not independently self-contained, but has
  has_concrete_annual_anchor(text) evidence and can be appended only to the
  immediately preceding seed bundle;
- skip: neither seed nor safe continuation.

Continuation is never admitted alone. It exists only to retain the second
sentence of a source argument with an earlier factual subject.

The implementation contract is:

    for raw_unit in source_units:
        unit = extract_a_share_causal_tail(raw_unit, usage, style) or raw_unit
        if noise_reason(unit.text, source_block_text=block_text):
            state = noise
        elif is_seed(unit, family, usage, style):
            state = seed
        elif has_concrete_annual_anchor(unit.text):
            state = continuation
        else:
            state = skip

    is_seed(unit, family, usage, style):
        return family_accepts(unit.text, family, usage, style)
               and is_self_contained_atomic_fact(
                   unit.text, family, document_style=style, usage_hint=usage)

    is_continuation(unit, bundle, family):
        return has_concrete_annual_anchor(unit.text)
               and continues_same_argument(bundle, unit, family)

The A-share causal-tail replacement runs before noise, seed, and continuation
classification. Noise always wins. argument_complete is calculated once for
the final bundle and never determines whether a seed is admitted.

### 3.3 Bundle Boundaries

A bundle uses one contiguous sequence of original SourceUnits from one
source_block_id. It starts with a seed and may append a continuation only
when all conditions hold:

- ordinal and source offsets are adjacent;
- the continuation is not noise;
- it does not begin a new self-contained seed;
- _continues_same_argument() accepts the running bundle and next unit for
  the canonical family.

The bundle ends before a blocked unit, a new seed, or a failed continuity
check. The emitted excerpt remains the exact normalized substring from the
first start offset through the last end offset. No text is rewritten.

### 3.4 Family Admission

Bundle-level family admission retains current table/noise guards and uses the
same generic source evidence:

- business_structure: explicit company/business context, or the existing
  style-gated HK implicit-subject rule, plus a concrete anchor;
- technology_product_progress: a mapped high-value product/R&D usage containing
  either a named model/product pattern (letter-plus-digit model, rate such as
  800G or 1.6T, or named Chinese series) or one of SoC, MCU, FPGA, NPU, GPU,
  IP core, PDK, or process platform; it must also contain one action relation:
  breakthrough, release, customer validation, introduction, cooperation,
  production, delivery, launch, iteration, upgrade, tape-out, or sample
  delivery. Bare platform, technology, capability, or R&D-platform wording is
  never a technology-product anchor;
- operating_progress: a report-period change with an operating anchor;
- market_competition_outlook: a management, industry, demand, competition,
  strategy, or outlook statement;
- financial_quality_explanation: a financial metric plus causal or
  explanatory relation.

argument_complete remains observational. It may score a card but must not
silently discard a source-admissible atomic fact, and it must not change 4.4
behavior.

## 4. Diagnostics and Contracts

Producer diagnostics add only generic source-selection detail:

- primary-family reason (usage_primary or signal_primary);
- number of bundled continuation units;
- rejection counts for noise, skip, and unattachable continuation;
- existing source-unit ids and score parts.

No diagnostics are displayed in the report. They remain in card notes for
debugging producer quality.

The material-pack coverage audit remains unchanged except for consuming the
new v2 cards. It must still prove each legacy fragment through an exact
normalized substring of a single unit or ordinal-contiguous unit sequence.

## 5. Explicit Non-Goals

- No v1-note lookup, legacy-aware selector, or stock-specific rule.
- No LLM memo, prompt, renderer, material snapshot, report wording, scoring,
  target-price, risk, technical, recommendation, or collection change.
- No increase above the evidence-pack 48-block cap.
- No report generation or v1 note archival until acceptance succeeds.

## 6. Acceptance Matrix

### Unit and Contract Tests

1. Mapped product_capacity_profile text with a product signal remains
   business_structure; the product signal is secondary, not a reroute.
2. An unmapped usage still selects its signal-derived primary family.
3. A factual seed plus one context-dependent adjacent continuation emits one
   card with both SourceUnits and an exact source substring.
4. The continuation alone emits no card.
5. A new self-contained seed starts a new card rather than overlapping the
   prior bundle.
6. A noise/table/checkbox unit never joins a bundle.
7. HK product/platform narrative remains style-gated; a pure year or label
   alone remains rejected.
8. Existing A-share checkbox causal-tail behavior remains exact-substring
   safe.
9. SourceUnit coverage still rejects nonadjacent ordinals.
10. A management_market_view profitability explanation with metric plus change
    relation remains financial_quality_explanation; generic market numeric text
    remains market_competition_outlook.
11. A seed followed by noise and then a continuation does not admit the
    continuation.
12. A zero-recovery material pack also has zero v1_adapter_use_count.

### Representative Source Fixtures

The unit suite must include source excerpts, not stock-specific branches:

| Existing source pattern | Required fixture assertion |
| --- | --- |
| Black Sesame A2000 product and customer-progress sentences | mapped HK product usage emits a technology card with the adjacent continuation |
| Zhongjian payment method changes from avionics payment to bank transfer | cash-flow usage emits one financial causal card without checkbox text |
| SGT Micro product breadth and R&D product launch | product/R&D usage emits factual business or technology cards, not a table |
| Espressif B2D2B model, product lifecycle, and IoT demand statement | business, continuation, and market usages preserve the three factual excerpts |
| Zhongji main-business and competition statements | business overview and competitive-position usages preserve independent source facts |

### Local-Cache Acceptance

Refresh the same eight local annual caches without network access. Require:

- each configured stock has v1_needs_recovery_count == 0;
- Black Sesame retains A2000/platform and named customer-product progress;
- Zhongjian retains the payment-method/cash-flow causal explanation;
- SGT Micro retains its concrete product and R&D facts;
- Espressif retains business-model, lifecycle, and market-demand facts;
- Zhongji retains main-business and competition facts;
- no v2 card has noncontiguous units, overlapping source ranges, or duplicate
  SourceUnit ownership;
- no reports are generated before the gate passes.

## 7. Complexity Budget and Stop Conditions

This batch must replace the current early per-unit self-contained admission and
signal-first family routing. It must not layer a parallel recovery selector.

The runtime baseline is measured from aa7bdd9 with:

    git diff --numstat aa7bdd9 -- \
      scripts/utils/annual_argument_schema.py \
      scripts/utils/periodic_report_evidence_pack.py \
      scripts/utils/periodic_report_narrative_evidence_cards.py \
      scripts/utils/annual_report_material_pack.py

The current measured result is +220 net lines. The earlier +327 figure was
recorded before the Codex consolidation pass and is not the active baseline.
This batch has a provisional target of no more than +30 additional runtime
lines and a hard stop at +50 additional lines (+270 absolute). It must replace
the signal-first mapped routing and early per-unit self-contained gate; it may
not layer a state machine alongside them.

Stop immediately if:

- a v1 note must be read during producer selection;
- a second card-selection route, stock allowlist, or text-rewrite rule becomes
  necessary;
- a source bundle crosses blocks or nonadjacent SourceUnits;
- the 48-block cap must increase;
- any protected report/scoring/LLM/collection path changes;
- the eight-stock coverage gate remains nonzero after the proposed repair.

## 8. Failure Modes

| Failure | Observable symptom | Test / gate |
| --- | --- | --- |
| usage routing loses specific source context | product fact moves to an unrelated family | mapped usage-primary test |
| continuation leaks without an anchor | dangling sentence becomes a card | continuation-alone negative test |
| bundling overlaps arguments | one SourceUnit appears in multiple cards | source-unit ownership invariant |
| relaxed admission accepts tables/forms | table or checkbox appears as a card | noise/checkbox regressions |
| migration hides a lost fact | adapter reaches zero without exact proof | eight-stock coverage audit |
| implementation grows another selector | runtime exceeds budget or reads v1 | scope audit and line budget |

## 9. Design Delta From Claude Round 1

Accepted:

- Preserve a strong financial-explanation override instead of making usage
  routing absolute.
- Specify seed, continuation, noise, A-share tail, and argument-complete order
  as one producer state contract.
- Define technology anchors and action relations without a company or industry
  allowlist.
- Add representative source fixtures and an explicit zero-recovery adapter gate.
- Reconcile the active runtime baseline using the four-file diff command.

Rejected:

- No v1-aware recovery selector or adapter input to the producer.
- No change to material-pack coverage proof or 48-block cap.

Round 2 required: yes. The revision changes mapped-family precedence and
introduces precise bundle semantics, so the updated contracts need a second
read-only review before implementation.
