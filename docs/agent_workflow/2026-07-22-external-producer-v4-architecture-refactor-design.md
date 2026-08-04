# External Producer v4 Architecture Refactor Design

Date: 2026-07-22
Status: proposed
Decision: clean cutover; v3/v3.1 packs and readers are not retained

## 1. Problem

External Producer currently spreads ownership across acquisition previews, source cleaning, sentence
materialization, scope projection, argument cards, topic narratives, display adapters and Chapter 4 material
selection. The layering is nominal rather than real:

- source cleaning collapses paragraph boundaries before evidence units exist;
- target/peer ownership is reconstructed later from a two-unit lookback;
- family, completeness, selection, pack writing and pack reading live in one 700+ line module;
- display projection repairs evidence after canonicalization instead of consuming display-ready evidence;
- topic narrative and snapshot selection both regroup the same cards;
- v3/v3.1 compatibility paths and preview-era modules keep old contracts alive.

The Zhongji recovery pilot exposed the architectural failure. Company continuations were classified as
`peer_or_industry`, while increasing the ordinal window would classify genuine industry forecasts and Huagong
Technology claims as Zhongji facts. The missing information is paragraph ownership, and it has already been
discarded by the time scope projection runs.

## 2. Goals

1. Preserve source title, paragraph boundaries and exact evidence offsets from intake through the pack.
2. Give one deterministic component exclusive ownership of target/peer/industry scope.
3. Keep LLM work ID-only: selection and ordering, never entity ownership or factual prose.
4. Produce readable topic narratives from canonical units without introducing unsupported claims.
5. Keep the report-side `MaterialSnapshot` and Chapter 4 renderer contract stable.
6. Remove v3/v3.1 compatibility, duplicate projection and obsolete preview-era runtime after cutover.
7. Reduce core runtime size and make each module independently testable.

## 3. Non-goals

- No scoring, target-price, risk, technical-analysis or recommendation changes.
- No Chapter 4.1/4.2 redesign.
- No Xueqiu detail crawling, Chrome/CDP control or new source provider.
- No embedding, fuzzy entity matching or stock-specific attribution rules.
- No arbitrary card, family or source cap. Low-value material may be rejected by explicit quality rules, not by
  position in a list.
- No source-body truncation in canonical production. A deliberately truncated preview input cannot become a ready
  canonical pack.
- No report-time LLM request. v4 packs are built offline and consumed deterministically.

## 4. Options Considered

### A. Extend v3.1 lookback

Rejected. It cannot recover paragraph ownership and creates symmetric false binding in comparative articles.

### B. Canonical source document plus deterministic scope resolver

Selected. It fixes the information loss at source canonicalization, keeps evidence exact and makes ownership
auditable before selection.

### C. Let the LLM assign scope and summarize prose

Rejected. It improves recall but weakens repeatability, entity safety, auditability and cost control.

## 5. Target Architecture

```text
Source intake
  -> ExternalSourceDocument
  -> ExternalEvidenceUnit
  -> ExternalScopeResolver
  -> ExternalArgumentAdmission
  -> ID-only PeerSelector
  -> ExternalArgumentPack v4
  -> ID-only NarrativePlan
  -> ExternalMaterialSnapshot adapter
  -> Chapter 4.3 / 4.4
```

Each arrow is a typed boundary. No downstream layer may recalculate an upstream decision.

## 6. Data Contracts

### 6.1 ExternalSourceDocument

Schema: `curated_external_source_document.v1`

Required fields:

- immutable source metadata: `source_id`, `stock_name`, `title`, `account`, `publish_time`, `source_kind`,
  `source_ref`, `source_url`;
- `normalization_version`;
- `raw_content_hash` and `document_hash`;
- ordered `blocks`.

Each block has `block_id`, `block_ordinal`, `block_kind`, `text`, `start`, `end` and `block_hash`.
`block_kind` is one of `narrative`, `heading`, `table`, `structural_noise`. Paragraph boundaries remain explicit.
Markup removal and whitespace normalization happen once here. They must not merge two source paragraphs.
`raw_content_hash` audits the fetched body; `document_hash` audits the canonical block sequence. Evidence exactness
is measured against this canonical document, whose normalization version is persisted and reproducible. No later
layer may clean or shorten its text.

The document records `boundary_status`. Comparative documents require preserved multi-block boundaries; a
collapsed comparative body fails with `scope_input_degraded`. Preview-only callers may inspect degraded documents,
but the canonical pack builder rejects them. Trailing disclaimers and navigation are retained as
`structural_noise` blocks instead of causing blind body truncation.

### 6.2 ExternalEvidenceUnit

Schema: `curated_external_evidence_unit.v2`

Required fields:

- `unit_id`, `source_id`, `block_id`, `block_ordinal`, `unit_ordinal`;
- `start`, `end`, `text`, `unit_hash`, `block_hash`, `document_hash`;
- `coverage_families` and `argument_status`;
- `scope_provenance`.

The invariant is `block.text[start:end] == unit.text`. A unit is never rewritten for display. Structural noise is
classified before unit admission, so a later display-span repair layer is unnecessary.

### 6.3 Scope provenance

Schema: `curated_external_scope_provenance.v2`

Unit origins:

- `explicit_target`;
- `target_document_context`;
- `target_peer_relation`;
- `explicit_peer`;
- `industry_context`;
- `ambiguous`.

Provenance stores the exact owner surface, anchor type, anchor block/unit ID and resolver version. `ambiguous`
units remain in diagnostics but cannot enter target cards.

Card scope is derived only from member units:

- all target-origin units: `target`;
- a `target_peer_relation` unit, or target-origin plus directly attached peer context:
  `target_with_peer_context`;
- no target-origin unit: `peer_or_industry`.

## 7. Scope Resolution

`ExternalScopeResolver` is the sole owner of entity scope.

### 7.1 Document mode

The resolver receives the configured target name and aliases from the producer invocation and classifies a
document as:

- `target_centric`: title identifies the target and has no comparison construction;
- `comparative`: title/body headings explicitly compare multiple named subjects;
- `industry`: no target-centric owner is established.

Document mode is context, not evidence. A target-centric title does not automatically turn every sentence into a
target fact.

### 7.2 Block owner

Resolution is block-first:

1. An explicit target surface in the block establishes target ownership for that unit and compatible
   continuations.
2. An explicit non-target named subject establishes peer ownership for that unit.
3. Every block has an immutable `primary_owner`, derived from its heading or the first subject before its first
   relation separator. A later contrast clause may have a different `local_owner`, but does not silently replace
   the block primary owner. This handles a Huagong-owned paragraph that briefly compares Zhongji and then returns
   to omitted-subject Huagong facts.
4. In comparative documents, owner-less continuations use the block primary owner. Ownership does not cross
   blocks implicitly.
5. In target-centric documents, bounded company continuations (`公司`, `本公司`, an attributed management
   statement, or a company action) may use the document target anchor.
6. Generic industry, market, supplier or competitor assertions remain `industry_context`, even inside a
   target-centric article.
7. A unit containing both target and peer facts becomes `target_peer_relation` only when an explicit relation
   grammar proves that the target participates in the assertion. Mere co-occurrence is insufficient.
8. Any unresolved subject is `ambiguous` and fails closed.

Entity detection uses the configured target name/aliases plus an exact document-local entity inventory. The
inventory is built from comparative title forms (`A与B`, `A和B`, `A对比B`), heading subjects, organization-suffix
subjects and named actors captured before bounded action verbs. Relation forms also capture suffix-less surfaces,
including `竞争对手英伟达` and `与华为合作`. It does not depend on a fixed company dictionary. Relation phrases
such as `竞争对手`, `同行`, `供应商`, `合作方`, `相比` and `相较` require explicit relationship proof rather than
inheritance. A newly captured non-target surface is peer context for the current document; an uncertain surface
does not become target context.

### 7.3 Required golden cases

- Zhongji target article: `公司已接到部分客户全年订单` is target context.
- Zhongji target article: standalone industry shipment/capacity forecasts remain industry context.
- Zhongji/Huagong comparison: each paragraph and clause switches ownership correctly.
- `其竞争对手英伟达发布...` never inherits target ownership.
- Fudan product/financial facts retain target ownership without pulling peer context into target cards.
- Black Sesame target/partner relations require the target to participate in the asserted relation.

## 8. Argument Admission and Families

Family taxonomy remains the current eight canonical families. One shared taxonomy module owns family titles,
rules and ordering.

Admission is deterministic and requires:

- at least one canonical family;
- a complete relation, metric or directional conclusion;
- exact evidence and valid scope provenance;
- no baseline duplicate.

The completeness grammar includes positive, negative and constraint conclusions. It must cover forms such as
`不存在`, `未出现`, `没有明显瓶颈`, `催化`, `影响有限`, while rejecting headings, questions and unfinished
labels. Rules are general linguistic predicates, not stock-specific phrases.

Target-origin facts are retained without an arbitrary count cap. Exact duplicate units are stored once.
Peer/industry facts enter the ID-only selector only after deterministic scope and admission.

Each admitted unit has one card owner. A deterministic primary-family resolver selects the first family by the
shared canonical priority order; remaining matches stay in `coverage_families` and do not create duplicate cards.
Target cards group contiguous compatible units by `(source_id, block_id, scope_bucket, primary_family)`. Card IDs
are hashes of their ordered unit IDs, so regeneration is stable. A unit cannot appear in two cards.

## 9. Selection and Narrative

### 9.1 Peer selector

The LLM receives only eligible `peer_or_industry` unit IDs and exact texts. It may return `keep`, `skip` and a
same-block group ID. It cannot output scope, family, claim text, prices, scores, risk or recommendations.

Batching is source/block aware and prompt-character bounded. `MAX_SELECTOR_PROMPT_CHARS` is a versioned producer
constant, initially 24,000 characters. Batches may contain multiple sources, but groups cannot cross a source or
block. Request count is deterministic: the minimum number of character-bounded batches needed for all eligible
peer units, plus at most one retry for each malformed batch. There is no per-source request requirement and no
source/card truncation. Validation fails closed; no raw fallback is allowed.

### 9.2 Narrative plan

The existing free-form topic narrative draft is replaced by an ID-only `ExternalNarrativePlan`:

- topic family and scope bucket;
- ordered card/unit IDs grouped into display paragraphs.

The plan contains no relation label: an LLM-selected `contrast` or `support` relation would itself be an
unverifiable semantic claim. The renderer uses neutral deterministic connectors around exact evidence text. The
planner cannot write factual prose. `MAX_NARRATIVE_PLAN_PROMPT_CHARS` is initially 30,000 characters and the plan
uses at most one request with no retry. If the input exceeds that budget or the plan is absent/invalid,
deterministic family/scope/source order is used. This preserves readability without creating a second fact owner.

## 10. Pack v4

Schema: `curated_external_argument_pack.v4`

The pack contains:

- stock and build versions;
- canonical source documents with their ordered blocks, plus source document fingerprints;
- canonical cards and citations;
- optional ID-only narrative plan;
- diagnostics for documents, blocks, units, scope, admission, selection and rejection.

Canonical source documents are embedded because strict offset and block-hash validation is impossible from
fingerprints alone. The reader performs one strict validation path. Missing or older schema versions fail closed.
There is no v3/v3.1 adapter and no raw-card display fallback.

Reader invariants include:

- source/block/unit hashes and exact offsets reconstruct against embedded canonical blocks;
- every target card has at least one target-origin unit;
- every peer card has no target-origin unit;
- provenance anchors exist and are reconstructable;
- citation identities match source documents;
- narrative plan references canonical cards only;
- every evidence unit has exactly one card owner;
- forbidden scoring/recommendation fields are absent.

## 11. Report Boundary

The pack reader returns one `ExternalMaterialSnapshot` containing cards, citations, narrative plan and diagnostics.
`deep_analysis_material_snapshot.py` adapts this object into existing `MaterialRow` and
`ExternalTopicNarrative` contracts. Chapter 4 renderers continue to consume the existing view model and do not
read packs, infer scope, regroup families or clean evidence text.

The adapter maps canonical unit `text` directly into rows; the current `external_display_text()` accessor is
removed. It maps the ID-only narrative order into the existing narrative dataclasses without retaining free-form
quotes or independently recalculating scope/family. To avoid unrelated pipeline churn,
`curated_external_display.py` preserves the current display-envelope keys
`_curated_external_argument_cards`, `_curated_external_topic_narratives`, `citations` and status/stat fields.
`evidence_freshness.py`, synthesis skills and assembly skills consume that envelope but do not interpret v4 pack
internals.

4.4 may reuse the same snapshot but cannot independently reopen source files or legacy pack fields.

## 12. Module Boundaries

Proposed runtime modules:

- `external_source_document.py`: canonical source documents and blocks;
- `external_evidence.py`: unitization, taxonomy and admission;
- `external_scope.py`: deterministic scope and provenance validation;
- `external_pack.py`: selector contracts, card construction, pack reader/writer;
- `external_narrative_plan.py`: ID-only plan validation and deterministic fallback;
- `curated_external_display.py`: thin report adapter only.

No module should exceed roughly 350 runtime lines. Shared text normalization, hashing and identity helpers have one
owner.

The following are removed after cutover:

- `curated_external_display_projection.py`;
- v3/v3.1 schemas, readers and projection branches in `curated_external_argument_cards.py`;
- free-form `curated_external_topic_narrative.py` contracts;
- duplicate scope/family/accessor helpers in snapshot and renderer;
- preview-era modules only after a call-graph test proves no configured entry imports them.

Acquisition utilities still used by WeChat/video/discovery scripts remain until their callers move to
`ExternalSourceDocument`; they are not deleted merely because the report runtime does not import them.
`curated_external_to_synthesis_items.py`, which currently has no production caller, is a deletion candidate in
Batch D; the call-graph gate, not its age, decides removal.

## 13. Migration Batches

### Batch A: Source and scope core

Add SourceDocument, EvidenceUnit v2 and ScopeResolver with fixture-based tests. Do not touch report readers or
canonical packs.

Exit gate: all golden ownership cases pass, exact offsets are proven and no v3 behavior is used by the new tests.

### Batch B: Pack and narrative plan

Build v4 cards, selector validation, narrative plans and strict reader. Regenerate pilot packs in `/tmp` only.

Exit gate: Zhongji, Fudan and Black Sesame pilot packs pass scope, exactness, unsafe and request-count gates.

### Batch C: Report cutover

Adapt v4 snapshot to the existing Chapter 4 view model, regenerate all three canonical packs and run formal report
verification.

Exit gate: three reports pass quality/source/prose gates; 4.3 and 4.4 contain no legacy fallback or scope mismatch.

### Batch D: Deletion and compression

Delete v3/v3.1 readers, projection, free-form narrative compatibility and proven-unused preview paths. Consolidate
tests around public contracts and golden fixtures.

Exit gate: repository search shows one scope owner, one family owner, one pack reader and no old schema literals in
runtime. The display envelope has one writer, and freshness/synthesis/assembly consumers contain no pack-schema
branch.

## 14. Verification Matrix

| Requirement | Verification |
|---|---|
| Preserve paragraphs | SourceDocument block fixture and hash test |
| Exact evidence | offset/hash round-trip tests |
| Target continuation | Zhongji target-centric fixtures |
| Industry isolation | shipment/capacity negative fixtures |
| Comparative ownership | Zhongji/Huagong alternating-owner fixture |
| No peer-to-target leak | named peer and relationship negative fixtures |
| Complete negative conclusions | rumor/bottleneck/catalyst fixtures |
| ID-only LLM boundary | forbidden-field and malformed-response tests |
| No cap | high-value multi-block fixture retains all admissible target facts |
| Reader fail closed | forged hash, provenance, citation and plan tests |
| Stable report boundary | MaterialSnapshot and renderer regression tests |
| Stable pipeline envelope | freshness/synthesis/assembly contract tests |
| Clean cutover | runtime grep rejects v3/v3.1 schema and legacy fallback |

Pilot acceptance for all three stocks:

- target facts classified as peer: zero in reviewed golden set;
- peer/industry facts classified as target: zero;
- high-value target-family unsafe units: zero;
- displayed evidence exactness: 100%;
- missing/unused citations: zero;
- reader, display and lint: ready/ok;
- no target family previously populated by valid source evidence becomes empty without an explicit rejection record.

## 15. Failure Modes

| Failure | Observable symptom | Gate |
|---|---|---|
| Paragraphs collapsed | scope crosses unrelated statements | SourceDocument block test |
| Target title over-applied | industry forecast appears as company fact | industry negative fixture |
| Comparative owner not switched | Huagong fact shown as Zhongji | comparative fixture |
| Ambiguous pronoun elevated | unsupported target card | ambiguous fail-closed test |
| Negative conclusion rejected | valid rumor/bottleneck fact is unsafe | completeness fixtures |
| LLM writes scope/prose | forbidden fields enter response | selector/plan schema tests |
| Narrative references missing unit | broken or invented paragraph | strict plan reader |
| LLM relation changes meaning | misleading connector | plan schema forbids relation/prose fields |
| Old pack silently displayed | mixed v3/v4 runtime | schema grep and reader test |
| Renderer reclassifies evidence | report differs from pack scope | snapshot/renderer identity test |

## 16. Size and Stop Conditions

The current core path is approximately 1,500 runtime lines across argument cards, display projection, topic
narrative, display and the full-body orchestrator. v4 should replace rather than wrap it.

Targets:

- final core runtime at least 250 net lines smaller than the v3/v3.1 path it replaces;
- no new runtime module above 350 lines;
- no second scope resolver, family resolver, pack reader or raw fallback;
- tests may grow during Batches A-C, then duplicate private-helper tests are removed in Batch D.

The deletion budget is credible only if implementation removes, rather than wraps, the complete 183-line display
projection module, the 179-line free-form topic narrative module, v3 materialization/preparation/reader branches
in `curated_external_argument_cards.py`, and the old orchestration/prompt branches in
`curated_external_full_body_viewpoint_claims.py`. Batch notes must report added/removed/net runtime lines for this
named file set after every batch.

Stop and return to design if:

- paragraph boundaries cannot be retained without rewriting source evidence;
- scope needs stock-specific company dictionaries or fuzzy/embedding matching;
- any peer fact enters a target card in the golden fixtures;
- v4 requires report-time LLM calls;
- a mixed v3/v4 reader becomes necessary;
- Batch D cannot remove the old projection/reader paths;
- runtime grows instead of shrinking after the clean cutover.

## 17. Rollback

Canonical v3 packs remain untouched through Batches A and B. Batch C validates explicit pilot paths before config
changes, then lands the v4 reader, report adapter, configuration and three packs in one atomic commit. Rollback
restores that commit as a unit; mixed code/data versions are not supported. No source material, knowledge note or
historical report is deleted during the cutover.

Before Batch A, record the current runtime baseline as `(HEAD SHA, worktree diff fingerprint, per-file numstat)`.
All size claims use that immutable audit record rather than only `HEAD`, because the accepted v3.1 implementation
is currently an uncommitted worktree delta.
