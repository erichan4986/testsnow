# External Producer v2 Evidence Unit Selector Design

## 1. Status

- Status: accepted and locked, supersedes the free-form candidate contract in the 2026-07-16 Batch B design.
- Gate B2: reset to blocked.
- Production config/cache cutover: forbidden until the new live gate passes.
- Compatibility: none. The current v2 packs are unpromoted review artifacts and will not receive an adapter.

## 2. Problem Statement

Three live runs proved that prompt tightening cannot make the current contract reliable:

1. The LLM simultaneously selects material, copies quotes, writes claims, assigns entity scope, assigns
   topic family, and explains incremental value.
2. Exact-quote validation checks source identity, numbers, models, selected strong terms, and target-name
   presence, but it cannot prove general semantic entailment. Unsupported phrases such as
   `正在向车规MCU和白电市场拓展` therefore pass when their numeric/entity anchors happen to pass.
3. A canonical `topic_family` supplied by the LLM is trusted without evidence-family validation. The same
   Fudan source material produced two topic families in one run and only `technology_product` in another.
4. Chapter 4 profile routing counts those stochastic topic labels. Extraction variance can therefore
   change report layout even when source material is unchanged.
5. Transport batching improved recall but did not repair the claim/topic/profile ownership problem.

The redesign removes prose and taxonomy ownership from the LLM. The LLM becomes an evidence-unit
selector only.

## 3. Locked Decisions

1. Persisted external cards contain exact source units, not LLM-authored claims.
2. Target-bound units with canonical coverage are admitted deterministically; the LLM may only group
   those units and select optional peer/industry units by stable ID.
3. Entity scope and coverage families are computed deterministically from selected evidence text.
4. Profile routing counts deterministic target-bound coverage only. Peer/industry cards never make a
   profile `external_rich`.
5. Exact source wording is rendered with existing Preview framing; readability belongs to the renderer.
6. No fuzzy quote repair, semantic paraphrase validator, second LLM critic, stock-specific runtime rule,
   or report-time LLM call is introduced.
7. Current unpromoted v2 pack/candidate schemas are replaced. No legacy or v2 compatibility reader remains.

## 4. Data Contracts

### 4.1 External source unit

Refresh-time materialization produces immutable units from canonical cleaned source content:

```json
{
  "schema_version": "curated_external_source_unit.v1",
  "unit_id": "external-unit:<source-id>:<ordinal>:<hash>",
  "source_id": "curated-source:...",
  "source_ordinal": 7,
  "text": "复旦微电在国网单相智能电表MCU市场份额第一。",
  "source_block_hash": "sha256...",
  "unit_hash": "sha256...",
  "target_bound": true,
  "coverage_families": ["competitive_landscape", "technology_product"]
}
```

Rules:

- Materialize from the already cleaned `source_packet.content`.
- Split only at complete Chinese/English sentence or semicolon boundaries.
- Preserve source order and terminal punctuation; every `text` must be a continuous substring of the
  canonical packet content.
- Do not rewrite whitespace after unit IDs/hashes are calculated.
- Remove only structural labels, navigation/footer residue, empty fragments, and demonstrably incomplete
  source tails. Semantic value is not decided by the splitter.
- A unit enters the selector pool when it contains the target name or at least one canonical coverage
  family signal. This is a broad transport filter, not final admission.

### 4.2 Deterministic target admission

A source unit is mandatory target material when:

- its exact text contains the configured stock name;
- it has at least one canonical `coverage_family`;
- it is not structural noise or an exact baseline duplicate.

Mandatory target units are retained without an LLM keep/skip decision and have no total cap. This makes
profile-critical coverage deterministic and prevents a refresh from losing financial or competitive
material because the model overlooked it. A mandatory unit remains a standalone card unless the selector
proposes a valid adjacent group; grouping changes presentation, not admission or coverage.

### 4.3 LLM unit decision

The selector receives at most 24 ordered units from one source per request. Its input contains mandatory
target units for optional grouping plus non-target units for optional peer/industry selection. It returns
one decision for every supplied unit:

```json
{
  "schema_version": "curated_external_unit_selection.v1",
  "decisions": [
    {
      "unit_id": "external-unit:...",
      "action": "keep",
      "group_id": "argument-1",
      "reason": "incremental_target_fact"
    },
    {
      "unit_id": "external-unit:...",
      "action": "skip",
      "group_id": "",
      "reason": "baseline_duplicate"
    }
  ]
}
```

For mandatory target units, `skip` is invalid; the selector may only keep them or assign a group. For
non-target units, `keep/skip` controls whether they appear in the optional peer/industry block.

The LLM cannot output:

- claim text or source quote;
- topic family or entity scope;
- incremental prose;
- numbers, models, target price, score, risk score, or recommendation.

The selector response is valid only when its decision IDs exactly equal the supplied unit IDs, with no
missing, duplicate, or unknown ID. An incomplete response receives one retry using the same selector.
Failure after the retry marks the refresh `selector_incomplete`; partial packs are not written as ready.

Units sharing a non-empty `group_id` must be 1--3 adjacent units from the same source in source order.
Invalid groups fail closed. `skip` reasons are diagnostics only and do not persist as report material.

### 4.4 Canonical card and pack

The breaking schema is explicit:

```text
curated_external_argument_card.v3
curated_external_argument_pack.v3
external_unit_selector.v1
external_argument_validator.v3
```

Each card stores:

- selected evidence units with exact text/hash/source identity;
- deterministic `entity_scope`;
- deterministic multi-label `coverage_families`;
- deterministic `primary_family` used only for display grouping;
- citation refs and Preview/display-only safety flags;
- baseline exact-overlap diagnostics.

It does not persist a duplicate free-form `claim` or `incremental_delta`. The report-time display reader
derives `display_text` by joining selected evidence units in source order. The reader never opens source
packets or invokes an LLM.

## 5. Deterministic Enrichment

### 5.1 Entity scope

- `target`: selected text explicitly contains the configured stock name and no peer context.
- `target_with_peer_context`: selected text contains the stock name plus another named company or an
  explicit comparison/competition marker.
- `peer_or_industry`: selected text does not contain the stock name.
- Source title never substitutes for target evidence.
- A continuation such as `公司/双方/其` is target-bound only when grouped with an adjacent preceding unit
  that explicitly contains the target name.

### 5.2 Coverage families

One exact evidence group may have multiple families. A single shared family table maps generic evidence
signals to the existing canonical families:

- `financial_quality`
- `technology_product`
- `competitive_landscape`
- `demand_customer`
- `capacity_delivery`
- `commercialization`
- `policy_geopolitics`
- `valuation_expectation`

Family inference reads exact evidence text, never LLM labels. The table is generic and has no stock name,
stock code, industry name, or sample-specific phrase. `primary_family` is chosen by a fixed shared priority
only for display; `coverage_families` remains multi-label for diagnostics/profile.

`other` may be used as a display fallback but never contributes to external richness. Family inference is
also the deterministic admission signal for target-bound units; the LLM cannot remove or relabel it.

### 5.3 Baseline overlap

- Exact normalized containment/hash overlap with annual/broker baseline is rejected deterministically.
- Partial or semantic overlap is retained as Preview material; the selector may skip it but cannot create
  a persisted overlap explanation.
- No embedding, fuzzy quote repair, or semantic hard rejection is introduced in this batch.

## 6. Display and Profile Ownership

### 6.1 Display

- Target and target-with-peer cards render first under their deterministic family headings.
- Peer/industry cards render in a separate `同业/行业背景（Preview）` block.
- `display_text` is the exact selected source text plus citation; renderer framing may add a fixed prefix
  and Preview disclaimer but may not rewrite the evidence.
- Peer/industry material remains traceable but cannot be phrased as a target-company fact.

### 6.2 Profile

For the v3 pack path:

```text
target_cards = cards whose entity_scope starts with target
target_coverage = union of target_cards.coverage_families excluding other
external_rich = len(target_coverage) >= 3
```

The old `external_claims >= 6` fallback is removed for the v3 path because six same-theme cards are volume,
not breadth. Peer/industry families and card counts do not contribute. Single-source richness remains a
diagnostic warning, not an automatic rejection.

Annual/broker precedence remains unchanged:

1. formal-rich formal support remains first;
2. annual + usable broker remains formal-medium;
3. annual + deterministic external-rich remains formal-thin-external-rich;
4. otherwise retain current partial/insufficient fallback.

## 7. Refresh and Runtime Flow

```text
clean source packets
  -> materialize exact source units
  -> deterministic target admission + optional peer pool
  -> per-source unit batches
  -> LLM target grouping / peer keep-skip decisions only
  -> completeness/group validator
  -> deterministic entity/family/baseline enrichment
  -> dedupe exact/contained argument groups
  -> persisted pack v3
  -> report-time pack reader
  -> exact display projection + target-only profile coverage
```

The report pipeline never reads legacy digest/narrative caches, source JSONL, or full bodies. Refresh is an
explicit offline operation. Missing/stale/invalid/incomplete packs fail closed.

## 8. Deletion and Slimming

This is replacement work, not coexistence work. Delete in the same implementation:

- free-form candidate `claim/source_quote/topic_family/incremental_delta` parsing;
- `_anchors_supported()` semantic proxy and title-based target fallback;
- quote-copy prompt and `source_quote_not_exact` path for selector output;
- v1 digest/narrative producer, repair, composer, multipass theme profiles, and compatibility adapters
  already scheduled for Gate B2 deletion;
- profile counting based on raw card count or LLM topic labels;
- tests and fixtures whose only purpose is old schema compatibility.

Keep one source-unit splitter, one selector, one deterministic validator, one pack reader, and one display
projection. No recovery selector or legacy fallback is allowed.

Runtime budgets relative to `62be6bf`:

- intermediate replacement state must not exceed `+650` after user approval on 2026-07-17;
- final Gate B2 state after deletion must be net `<= +120`;
- crossing either limit stops implementation and returns to design.

## 9. Failure Modes and Tests

| Failure | Observable result | Required test |
|---|---|---|
| Unit text is rewritten or not a source substring | invalid unit/pack | exact substring + stable hash tests |
| Source tail is incomplete | unit omitted with diagnostic | truncated-tail fixture |
| Selector omits or duplicates unit IDs | `selector_incomplete` | missing/duplicate/unknown ID fixtures |
| Selector tries to skip mandatory target unit | invalid selection | mandatory-skip fixture |
| Selector groups non-adjacent or cross-source units | invalid selection | adjacency/source identity fixtures |
| Target inferred from title or pronoun alone | peer/industry or rejection | title-only and pronoun-only fixtures |
| LLM tries to add claim/topic/number fields | ignored/rejected schema | extra forbidden-field fixture |
| Financial evidence is labelled technology by LLM | impossible; family derived from text | Fudan financial fixture |
| Peer cards create external-rich profile | profile remains non-rich | peer-only three-family fixture |
| Six same-family target cards create rich profile | profile remains non-rich | same-family volume fixture |
| Three target evidence families exist | formal-thin-external-rich | target multi-family fixture |
| Report reader opens source/legacy files | CI/spy test fails | reader isolation fixture |
| Pack version changes | stale, no fallback | stale schema/version fixture |

Focused tests must also prove citation refs remain complete, Preview flags remain false for scoring/risk,
and formal-medium/formal-rich routing is unchanged.

## 10. Gate B2 Live Acceptance

Run fresh external refreshes for Zhongji Innolight, Fudan Microelectronics, and Black Sesame Intelligence
twice with identical source packets and baseline.

Required for approval:

1. Every selector batch is complete; no unknown/missing/duplicate unit ID and no mandatory target skip.
2. Every persisted evidence unit is an exact source substring with valid hashes and citation identity.
3. No persisted LLM-authored claim, topic, delta, target price, score, risk score, or recommendation exists.
4. Every target card contains the target name in its grouped evidence; peer cards are separately labelled.
5. Fudan target coverage includes at least `financial_quality`, `technology_product`, and
   `competitive_landscape` from the available local sources.
6. The two runs may select different individual units, but must produce the same profile and the same
   target coverage-family set for each stock. Instability blocks cutover.
7. Reader/display/lint and all focused/downstream/CI gates pass.
8. Samples are shown to the user before any config/cache promotion.

Do not lower the profile threshold, admit peer topics into richness, or add stock-specific runtime rules to
manufacture a passing sample.

## 11. Scope

Allowed runtime owners:

- `scripts/utils/curated_external_full_body_viewpoint_claims.py`
- `scripts/utils/curated_external_argument_cards.py`
- `scripts/utils/curated_external_display.py`
- `scripts/previews/curated_external_full_body_viewpoint_preview.py`
- the existing narrow v3 pack plumbing/profile consumers in report skills/reporter

Allowed tests are the corresponding focused utility, preview, synthesis, renderer, freshness, quality,
source-boundary, and recommendation contract tests.

Forbidden:

- source collection, Chrome/CDP, Xueqiu detail pages, annual/broker producer changes;
- scoring, target price, risk score, technical analysis, recommendation, or KnowledgeSynthesizer prompt;
- production config/cache/report changes before Gate B2 sample approval;
- stock/industry-specific runtime rules or compatibility adapters.

## 12. Design Delta

Accepted:

- exact source units as persisted/displayed argument text;
- deterministic admission for target evidence; LLM reduced to grouping and optional peer selection;
- deterministic multi-label coverage and target-only profile routing;
- peer/industry background retained separately;
- breaking schema with no compatibility path.

Rejected:

- another free-form prompt refinement;
- a second LLM critic;
- fuzzy quote repair or broader semantic regex patches;
- lowering `external_rich` to pass Fudan;
- counting peer cards or card volume as target-company coverage.

Deferred:

- semantic embedding dedupe;
- renderer prose summarization;
- external source collection/relevance-ranking changes.
