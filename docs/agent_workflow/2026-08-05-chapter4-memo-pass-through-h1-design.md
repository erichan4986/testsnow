# Chapter 4 Memo Pass-Through H1 Design

## Status

`locked_pending_repository_review`

## Goal

Remove `annual_report_memo.v1` and `broker_research_memo.v1` as intermediate
runtime schemas. Project canonical annual packs and guarded broker digest items
directly into the Chapter 4 `MaterialSnapshot`, while preserving current report
content, evidence-profile routing, diagnostics, citation order, and display
cleanup.

H1 is an ownership and code-reduction refactor. It must not implement the H2
content-policy changes.

## Current Problem

The formal material path currently performs two consecutive projections:

```text
annual/broker producer output
  -> SynthesisSkill memo rows + local citations + memo status
  -> MaterialSnapshot MaterialRows + global citations
  -> Chapter4ViewModel
  -> renderer
```

The two memo builders and their helper surface occupy 339 lines in the
1,880-line `synthesis_skills.py`. They are not durable source contracts:

- renderer access to raw broker memo was removed in G2;
- `MaterialSnapshot` is the Chapter 4 read-model owner;
- evidence profile and material coverage use only memo status/count metadata;
- all eight configured annual packs are `pack_first` with zero v1 adapter and
  actionable-recovery use.

## Locked Boundaries

### In Scope

- replace memo construction with one canonical formal-material preparation
  owner in `deep_analysis_material_snapshot.py`;
- load guarded broker digest items once per `SynthesisSkill.run()`;
- derive profile and material-coverage compatibility fields from formal
  projection diagnostics;
- adapt annual facts, explanations, narrative cards, and broker items directly
  to `MaterialRow`;
- delete memo-only runtime and tests;
- preserve report output and profile behavior.

### Out Of Scope

- changing annual producer, annual pack, or broker digest schemas;
- changing the 300-character annual visible-text bound;
- changing exact annual-body deduplication;
- changing broker admission/status rules;
- changing the configured broker loader budget or the secondary six-row bound;
- changing report profiles, pipeline order, section structure, or citation
  presentation;
- changing LLM prompts/synthesis, scoring, target price, risk, technical
  analysis, recommendation, data, Knowledge notes, or reports.

## Canonical Ownership

### Source Owners

- annual facts: `formal_financial_fact_pack.facts`;
- annual explanations: `formal_financial_explanation_pack.rows`;
- current annual arguments:
  `periodic_report_narrative_evidence_cards.cards`;
- persisted annual fallback:
  `annual_report_material_pack.selected_narrative_cards`;
- broker arguments: guarded `broker_research_digest_items`.

### Projection Owner

`deep_analysis_material_snapshot.py` owns:

- current-card-over-pack precedence;
- visible annual cleanup used by the existing memo path;
- exact annual-body dedupe and canonical-family admission;
- annual and broker status derivation;
- broker item admission, dedupe, attribution, and six-row compatibility bound;
- `MaterialRow` construction;
- global citation allocation;
- formal-material diagnostics consumed by profile/coverage logic.

`SynthesisSkill` owns only orchestration: build/load source packs, refresh and
load broker items once, request formal diagnostics, build the evidence profile,
and invoke synthesis.

The renderer continues to consume only `Chapter4ViewModel`/`MaterialRow`.

## Data Contracts

### Internal Prepared Inputs

Add private immutable projections in `deep_analysis_material_snapshot.py`:

```python
@dataclass(frozen=True)
class _AnnualMaterialProjection:
    status: str
    cards: tuple[Mapping[str, Any], ...]
    facts: tuple[Mapping[str, Any], ...]
    explanations: tuple[Mapping[str, Any], ...]
    warnings: tuple[str, ...]
    has_material: bool


@dataclass(frozen=True)
class _BrokerMaterialProjection:
    status: str
    usable_items: tuple[Any, ...]
    projected_items: tuple[Any, ...]
    institutions: tuple[str, ...]
    families: tuple[str, ...]
    input_item_count: int
```

These types are private implementation details, not persisted schemas and not
stored in `ctx`.

### Formal Diagnostics

Expose one pure function:

```python
def build_chapter4_formal_material_diagnostics(
    ctx: Mapping[str, Any],
) -> dict[str, Any]:
    ...
```

It invokes the same private preparation functions used by the snapshot and
returns only routing/audit metadata:

```python
{
    "annual_status": "ready|deterministic_fallback|blocked|absent",
    "annual_confirmed_row_count": int,
    "annual_explanation_row_count": int,
    "annual_warning_count": int,
    "formal_citation_candidate_count": int,
    "broker_status": "ready|single_institution|absent",
    "broker_input_item_count": int,
    "broker_usable_card_count": int,
    "broker_content_families": list[str],
    "broker_institutions": list[str],
}
```

`SynthesisSkill.run()` stores this small dict under
`chapter4_formal_material_diagnostics`. It is a diagnostic summary, not a row
or citation projection.

For compatibility, evidence profile keeps its existing output keys:

- `annual_memo_status`;
- `broker_memo_status`;
- `broker_single_institution`;
- `broker_usable_card_count`;
- `broker_content_families`;
- `broker_institution_count`;
- `memo_refs_resolved`.

`memo_refs_resolved` becomes true when
`formal_citation_candidate_count > 0`. The count is computed from unique
citation keys belonging to prepared facts, explanations, and annual cards only
when annual status is `ready` or `deterministic_fallback`, plus projected broker
items only when broker status is `ready` or `single_institution`. Synthetic
disclosure-boundary rows do not count. `SynthesisSkill` must not infer this
again. The key name is retained in H1 to avoid an unrelated downstream
contract change.

Material coverage likewise retains its existing `memo_status`,
`memo_row_count`, and `memo_usable_card_count` field names while sourcing their
values from the formal diagnostics.

## Annual Preparation

`_prepare_annual_material(ctx)` follows the existing memo decisions exactly:

1. Read current in-memory cards. A card is usable when it is a mapping and has
   `excerpt` or `source_excerpt`.
2. If at least one current card is usable, use only those cards. Otherwise use
   `annual_report_material_pack.selected_narrative_cards`.
3. Copy each card and normalize its visible excerpt with the current annual
   memo cleaner: strip annual-report/page prefixes and known product-table
   headers, join CJK OCR spaces, normalize whitespace, and apply the same
   300-character complete-boundary cut.
4. Require canonical `argument_family`. Cards without a canonical family are
   outside the producer/material-pack contract and are not projected.
5. Preserve first occurrence under the current whitespace-insensitive exact
   body key.
6. Do not relocate the memo-local table-fragment heuristic, forbidden-source
   token scan, or legacy `card_type` family map. They reject zero current
   canonical cards; producer validation and source-boundary gates own those
   contracts.
7. Preserve `argument_complete`, title, source block/card ids, source credit
   (defaulting current in-memory cards to 75),
   and source order.
8. Filter suspicious `0.00亿元` revenue/profit facts exactly as today and retain
   warnings.
9. Preserve memo status semantics exactly:
   - `absent` when no narrative/fact/explanation material exists;
   - `ready` with at least four valid cards, at least one non-financial family,
     and at least one usable row;
   - `deterministic_fallback` when usable rows exist but ready criteria fail;
   - `blocked` only when material exists, no usable rows exist, and warnings
     exist.

The source cards remain unchanged. Cleanup applies only to projected display
text.

## Broker Preparation

After `_refresh_broker_research_digest_notes(ctx)`, `SynthesisSkill.run()`
checks `broker_research_digest_items`. When its value is `None`, it calls
`_eligible_broker_research_digest_items(ctx)` once and stores the result,
including an empty list. When a list is already present, it preserves that
preloaded list and performs no loader call.

`_prepare_broker_material(ctx)` preserves the current memo contract:

1. Read only `broker_research_digest_items`; the snapshot never performs disk
   I/O.
2. Reapply the existing professional-analysis/scoring/risk guardrails.
3. Require a recognized broker card family and non-empty content.
4. Deduplicate by `(family, viewpoint_cluster-or-prefix, institution)`.
5. Derive institutions, report titles, families, and admission exactly as the
   memo does now.
6. Preserve `ready`, `single_institution`, and `absent` status semantics.
7. Store all deduplicated items as `usable_items` for status, diagnostics, and
   profile routing. Store `usable_items[:6]` as `projected_items` only when
   status is `ready` or `single_institution`; otherwise `projected_items` is
   empty.
8. Preserve risk, forecast, and general-section render roles and attribution.

The optional display synthesis and freshness overlay must consume the stored
item list rather than reload notes.

## Direct MaterialRow Projection

Replace `_annual_rows(memo, allocator)` and `_broker_rows(memo, allocator)` with
ctx/projection-based adapters.

Extend `_CitationAllocator` with keyed allocation for direct rows:

```python
def allocate(self, key: tuple[Any, ...], meta: Mapping[str, Any]) -> int:
    ...
```

Requirements:

- annual citation keys remain equivalent to current fact, explanation, and card
  keys;
- broker items receive one citation in admitted source order before rows are
  bucketed; visible rows remain grouped as general sections, forecasts, then
  risks, so mixed-family fixtures may intentionally cite non-monotonic ref IDs;
- broker source ids retain the existing SHA256 seed precedence
  `viewpoint_cluster`, then title, then content, with the first 16 hex chars;
- direct annual/broker refs occupy the same leading global namespace;
- external local refs still receive the offset after all formal refs;
- repeated annual keys reuse their first ref;
- row ids and source ref ids retain their current prefixes.

Preserve the two synthetic annual disclosure-boundary rows in the full snapshot
for H1 equivalence, even though current Chapter 4 selectors do not display
them.

`MaterialSnapshot.schema` remains `deep_analysis_material_snapshot.v1`.

## SynthesisSkill Changes

In `run()`:

```text
build annual material pack
refresh broker notes
load broker items once and store list
build/store chapter4 formal diagnostics
build canonical synthesis items
build curated external display
build evidence profile from formal diagnostics
build material coverage from formal diagnostics
continue existing synthesis flow
```

Delete:

- `_annual_narrative_cards()`;
- `_clean_annual_memo_excerpt()` after equivalent projection tests are green;
- `_looks_like_annual_table_fragment()`;
- `_build_annual_report_memo()`;
- `_build_broker_research_memo()`.

Update `_build_material_coverage_diagnostics()` and
`_build_evidence_profile()` to read
`chapter4_formal_material_diagnostics`. They must not reconstruct eligibility
or status locally.

## Test Strategy

### Batch A: Formal Projection Contract

Add failing tests in `tests/utils/test_deep_analysis_material_snapshot.py` for:

- current in-memory annual cards winning over stale pack cards;
- annual facts/explanations/cards becoming equivalent MaterialRows;
- canonical family and `argument_complete` preservation;
- 复旦 page/table/CJK whitespace cleanup and 300-character boundary;
- 黑芝麻 traditional-Chinese spacing cleanup;
- exact-body dedupe and rejection of noncanonical cards without
  `argument_family`;
- suspicious zero fact warnings and status;
- broker multi-institution, same-cluster/different-institution, forecast, risk,
  attribution, single-institution, absent, and six-row behavior;
- mixed broker input order proving citation IDs are allocated before grouped
  row emission;
- deterministic formal diagnostics;
- global citation order and external offset.

### Batch B: Synthesis Orchestration

Update `tests/reporter/test_synthesis_skills.py` to assert:

- broker loader is called once after refresh and its empty/non-empty result is
  stored;
- a preloaded broker list is preserved and causes zero loader calls;
- profile routing is identical for ready/fallback/absent annual material and
  ready/single-institution/absent broker material;
- coverage counts and compatibility field names are unchanged;
- freshness and optional display synthesis reuse stored broker items;
- no memo is written to `ctx`.

### Batch C: Renderer And Hygiene Migration

Update memo-shaped fixtures in:

- `tests/reporter/test_deep_analysis_renderer.py`;
- `tests/utils/test_external_v4_snapshot.py`;
- `tests/test_runtime_hygiene.py`.

Renderer tests must provide source packs/items or a prebuilt `MaterialSnapshot`,
never `annual_report_memo` or `broker_research_memo`.

Hygiene tests must assert the two memo schema strings, builders, and raw ctx
keys are absent from runtime code, except compatibility output field names such
as `annual_memo_status`.

## Three-Stock Acceptance

Run offline comparisons after focused/full tests:

1. 中际旭创: annual plus multi-institution broker material;
2. 复旦微电: dense A-share annual material and no broker material;
3. 黑芝麻智能: HK annual format and no broker material.

For H1, require:

- unchanged profile;
- unchanged Chapter 4 headings and row order;
- unchanged visible facts and broker attribution;
- unchanged citation source identities and citation count;
- no new OCR/table/boilerplate text;
- no changes outside Chapter 4/material diagnostics;
- all quality/source/prose gates pass, allowing only pre-existing prose
  warnings.

Do not access the network or refresh LLM/external materials for this comparison.

## Runtime Budget

Baseline is commit `e504cb9`.

- target runtime net reduction: at least 160 lines;
- minimum acceptable net reduction: 110 lines;
- stop if runtime reduction is below 110 lines;
- stop if implementation creates another persisted schema, row projection, or
  disk-reading path.

Test and workflow-document lines do not count toward the runtime budget.

## Failure Modes

| Failure mode | Symptom | Required guard |
|---|---|---|
| visible cleanup disappears | CJK split words/page headers return | A/HK noisy fixtures |
| stale pack beats current cards | old annual text appears | precedence fixture |
| projection and profile derive status separately | report route changes | one diagnostics-owner test |
| broker notes reload | repeated disk work/inconsistent contents | loader call count |
| direct citation allocation collides | wrong footnote source | exact identity/order tests |
| external offset uses partial formal rows | external refs shift | full-snapshot offset test |
| H1 changes caps/admission | row counts change | frozen equivalence fixtures |
| synthetic disclosure rows leak | boilerplate becomes visible | selector/renderer test |
| code only moves files | no meaningful reduction | runtime budget gate |

## Allowed Files

Runtime:

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/deep_analysis_material_snapshot.py`

Tests:

- `tests/reporter/test_synthesis_skills.py`
- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/utils/test_external_v4_snapshot.py`
- `tests/test_runtime_hygiene.py`

Workflow documents:

- H1 design, review, task, and implementation notes under
  `docs/agent_workflow/`.

## Verification Gates

1. focused formal projection and synthesis tests;
2. snapshot/renderer/external snapshot tests;
3. reporter downstream suite;
4. full repository `pytest`;
5. `bash tools/ci_grep_gates.sh`;
6. `git diff --check`;
7. runtime numstat against `e504cb9`;
8. three-stock offline comparison.

## Stop Conditions

Stop and return to design if:

- producer schemas or pipeline order must change;
- profile names or routing thresholds must change;
- citation identities cannot be preserved;
- H1 requires changing truncation, caps, or sparse broker admission;
- runtime net reduction is below 110 lines;
- tests reveal dependence outside the allowed files;
- network, LLM, Chrome/CDP, data, Knowledge notes, or report-template changes
  become necessary.

## H2 Deferred Decisions

Only after H1 acceptance:

- remove the annual 300-character display bound and retain complete source
  arguments in the snapshot;
- remove broker's secondary six-row cap while retaining an explicit intake
  budget;
- define whether one high-value broker card should render as a sparse,
  non-consensus observation;
- remove other compatibility-only aliases discovered after the canonical
  projection has shipped.

## Design Delta After Codex Self-Review

Accepted:

- diagnostics now own an exact formal citation candidate count;
- broker citations are allocated in source selection order before grouped row
  emission;
- legacy family mapping and zero-hit memo admission guards are deleted rather
  than relocated;
- preloaded broker items are preserved and bypass the loader;
- broker usable items are separated from the six projected items;
- absent material contributes no citation candidates;
- broker source-id hashing is explicitly locked.

Rejected:

- unconditional broker reload after note refresh, because it changes injected
  ctx behavior;
- moving all legacy memo guards into the snapshot, because canonical producers
  already own those guarantees and current pack audit shows zero hits.

Deferred:

- all H2 content-policy changes remain deferred.

Repository review required: `yes`, because this Level 3 batch removes two
runtime schemas and changes synthesis/read-model cooperation across more than
three files including tests.
