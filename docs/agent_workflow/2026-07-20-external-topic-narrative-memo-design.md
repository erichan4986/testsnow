# External Topic Narrative Memo Design

## 1. Status And Goal

- Status: proposed for Level 3 Round 1 read-only review.
- Goal: make Chapter 4.3 read as one coherent paragraph per canonical topic while preserving External Producer v3's exact-source, target/peer ownership, citation, and display-only contracts.
- Selected approach: add an optional producer-time, cached, extractive Topic Memo inside the existing v3 pack file.
- Report generation must never call an LLM or reread external source caches.

The current deterministic grouping correctly collapses repeated headings, but each accepted card is still rendered as a separate source sentence with repeated framing. A free-writing report-time summary would improve fluency at the cost of latency, nondeterminism, hallucination risk, and repeated token use. This design instead lets the refresh-time LLM select boundary-complete exact prefixes from already accepted evidence units. The renderer joins those verified prefixes into a paragraph with deterministic connectors.

## 2. Locked Product Behavior

Chapter 4.3 keeps the existing section heading and Preview disclaimer. Target-company material remains before peer/industry material. Within each entity scope, canonical topic order remains:

1. demand/customer
2. commercialization
3. technology/product
4. financial quality
5. competitive landscape
6. capacity/delivery
7. policy/geopolitics
8. valuation/expectation
9. unknown topics in first-seen order

Cards are grouped by `(scope_bucket, primary_family)`, where `target` and
`target_with_peer_context` share the `target` bucket and `peer_or_industry`
remains isolated. Each non-empty group renders one topic heading and one paragraph. Example:

```markdown
**技术与产品**

近期外部材料主要围绕技术与产品展开。新一代产品已进入客户验证阶段[^12]；此外，相关平台支持 4-128TOPS 算力配置[^13]。
```

The peer scope retains one concise boundary banner because source-boundary checks need an explicit separation from target-company claims:

```markdown
> **同业/行业背景（Preview）**：以下内容仅描述同业或行业背景，不代表目标公司已确认事实。
```

Rows no longer repeat `同业/行业背景观察：`, `外部新增待验证变量：`, or `相对正式材料/机构假设...：` when a valid Topic Memo group is available. Deterministic card rendering remains the fallback and keeps its current framing.

## 3. Non-Goals

- Do not change source discovery, source admission, target bundling, peer selection, card taxonomy, card count, profile routing, scoring, target price, risk, technical analysis, recommendation, or `KnowledgeSynthesizer`.
- Do not replace the ID-only External Producer v3 selector or combine prose composition with selector decisions.
- Do not add a report-time LLM call, memo note directory, sidecar file, embedding, semantic matcher, or second verification model.
- Do not make a Topic Memo required for a ready pack or a successful report.
- Do not add a total card, source, topic, sentence, or paragraph cap.
- Do not use the memo in Chapter 4.4 price-path reasoning. Chapter 4.4 continues to consume canonical `MaterialRow` cards.

## 4. Ownership And Data Flow

```text
source packets
  -> External Producer v3 exact source units
  -> canonical v3 cards and citations (unchanged)
  -> group accepted cards by scope_bucket + primary_family
  -> one stock-level Topic Memo LLM request
  -> validate exact clause spans against accepted source units
  -> store optional topic_narratives envelope in the same pack JSON

report runtime
  -> read v3 cards and optional envelope from pack only
  -> project cards plus validated narratives into MaterialSnapshot
  -> apply existing annual/broker incremental external-row selection
  -> use a narrative group only when it exactly covers the visible cards in that group
  -> otherwise fall back to deterministic grouped-card rendering for that group
```

The core card pack remains the sole evidence owner. Topic Memo data is a display projection and cannot create evidence, citations, families, scopes, cards, or profile coverage.

## 5. Persistence Contract

Keep the top-level `curated_external_argument_pack.v3` schema. Add one optional top-level object:

```json
{
  "topic_narratives": {
    "schema_version": "curated_external_topic_narratives.v1",
    "producer_version": "external_topic_narrative.v1",
    "source_pack_fingerprint": "sha256",
    "status": "ready|partial|unavailable",
    "groups": [],
    "diagnostics": {}
  }
}
```

`source_pack_fingerprint` is a deterministic hash of the core pack schema, selector version, validator version, stock identity, and ordered canonical card projection: `card_id`, `argument_key`, `entity_scope`, `primary_family`, and each evidence unit's `unit_id` and `unit_hash`. It excludes diagnostics, timestamps, citation presentation metadata, and the narrative envelope itself.

The existing v3 card validator and selector version remain unchanged. An absent, malformed, stale, or partly invalid narrative envelope must not invalidate a valid core pack. The reader keeps its existing core `status/cards/citations/stats/pack` fields and additionally returns `topic_narrative_status` plus `topic_narratives`. Allowed narrative statuses are `missing`, `ready`, `partial`, `unavailable`, `stale`, and `invalid`; only validated groups appear in `topic_narratives`. Duplicate core `card_id` or `argument_key` values make the envelope invalid because narrative ownership would be ambiguous, but they do not weaken or replace core card validation.

## 6. LLM Draft Contract

The Topic Memo composer receives only accepted cards, ordered by scope bucket and topic while preserving the current canonical card order and source-unit order inside each group. It receives stable IDs plus exact source text. One request covers all groups for one stock.

It returns:

```json
{
  "schema_version": "curated_external_topic_narrative_draft.v1",
  "groups": [
    {
      "scope_bucket": "target",
      "primary_family": "technology_product",
      "parts": [
        {
          "argument_key": "...",
          "unit_id": "...",
          "quote": "an exact, boundary-complete source substring",
          "relation": "first|continuation|separate"
        }
      ]
    }
  ]
}
```

The LLM may shorten a source unit only by selecting a complete prefix. It cannot write narrative prose, citations, entity scope, topic labels outside the supplied group, numbers, prices, scores, risks, recommendations, or conclusions. `relation` is a closed display hint, not a causal or bullish/bearish judgment.

Deterministic connector mapping is:

- `first`: no connector;
- `continuation`: `此外，`;
- `separate`: end the prior sentence and start the exact quote without a semantic connector.

The renderer adds the group lead sentence (`近期外部材料主要围绕...展开。` or `同业与行业材料主要集中在...。`) and inline citations. The LLM does not produce either.

## 7. Validation Contract

A narrative group is accepted only when all checks pass:

1. `scope_bucket` and `primary_family` identify an existing canonical card group. The target bucket may reference only `target` and `target_with_peer_context` cards; the peer bucket may reference only `peer_or_industry` cards.
2. Every part references an existing card `argument_key` and one of that card's source units.
3. `quote` is an exact prefix of that unit after the same whitespace normalization used by v3 source units; the validator never compares against an independently cleaned or paraphrased string. Requiring the unit start preserves the original grammatical subject and prevents a target/peer attribution from being dropped by clipping.
4. A shortened quote ends on `，,；;。！？!?：:` and must not end with an ellipsis. A full-unit quote is always boundary-complete. This rejects clipped words while allowing a long source unit to drop trailing digressions.
5. A quote is non-empty, contains at least one Chinese/alphanumeric content token, and is not only a heading, disclaimer, or structural label.
6. Every evidence unit of every canonical card in the group is represented exactly once by one accepted part. There is no cap. The memo may shorten a unit but may not hide one, so it cannot become a second evidence selector.
7. An `argument_key` or `(unit_id, quote)` pair cannot be reassigned to another scope/topic group.
8. Parts preserve canonical card order and source-unit order. The LLM cannot reorder chronology or ownership.
9. The draft contains no unknown keys or forbidden fields such as free prose, target price, score, risk score, or recommendation.
10. Only the first part may use `relation=first`; later parts use `continuation` or `separate`. The renderer may replace terminal punctuation only while joining parts, then attaches that part's source-unit refs before the resulting punctuation. It may not alter quote words.
11. Draft groups are unique by `(scope_bucket, primary_family)`. Unknown, duplicate, or omitted groups are rejected or marked missing independently; no raw model response or rejected quote is persisted.

Validation is group-local. One bad group is rejected while other valid groups remain available. Diagnostics record exact rejection reasons. No repair call is made.

This extractive contract intentionally trades free paraphrase for auditability. It prevents the unsupported entity and numerical additions observed in prior live gates without adding a second model call.

## 8. Read-Model And Citation Contract

Add small immutable read-model types rather than embedding footnote markers into strings:

```python
ExternalNarrativePart(
    argument_key: str,
    unit_id: str,
    quote: str,
    relation: str,
    citation_refs: tuple[int, ...],
)

ExternalTopicNarrative(
    scope_bucket: str,
    primary_family: str,
    parts: tuple[ExternalNarrativePart, ...],
)
```

Narrative envelopes do not persist citation IDs. During pack read/display projection, each validated part inherits `citation_refs` from its referenced canonical evidence unit. The original citation still identifies and hashes the full source unit; no quote-specific citation record is created.

`MaterialSnapshot` stores full external rows and validated narratives. `_CitationAllocator` maps each inherited part ref through the same external citation mapping object used by its source card. `Chapter4Section("4.3")` exposes narratives alongside rows. The formal-medium visible citation table is the union of visible row refs and visible narrative-part refs; the renderer's existing final `_visible_citations_only()` pass remains authoritative and prevents unused definitions.

For both profiles, projection first removes memo parts whose `argument_key` is not in the selected visible row set for that scope/topic, then recomputes the first-part connector. The filtered narrative is usable only when every evidence unit of every selected visible row is represented exactly once by the remaining parts. Otherwise that group uses deterministic rows. Hidden parts never render, so a memo cannot reintroduce an external card that the owner/delta selector removed.

Formal-thin citation offsets remain based on the full `MaterialSnapshot`:

```text
visible ref = baseline max ref + snapshot-global narrative part ref
```

No offset is recomputed from narrative-only refs, display order, or a filtered citation table. Chapter 4.4 continues to use row refs and therefore remains unchanged.

## 9. Renderer And Quality Gates

The shared formal-medium/formal-thin 4.3 renderer chooses independently for every topic group:

1. valid exact-coverage narrative group -> one paragraph;
2. otherwise -> current deterministic grouped rows.

Peer and target groups never merge. Unknown topic groups retain first-seen order. All visible narrative parts receive sentence/clause-local inline citations derived from their source units. Repeated source identities continue to canonicalize to one displayed reference where the current renderer already does so.

Paragraph assembly is deterministic. The renderer strips one terminal punctuation mark from each stored quote for joining, places that part's footnote markers immediately after the quote text, then emits `；此外，` for `continuation` or `。` for `separate`; the final part ends with `。`. The deterministic group lead is a separate first sentence. This algorithm may alter joining punctuation only, never quote words or order.

Quality gates gain explicit recognition for the two deterministic narrative leads:

- `近期外部材料主要围绕`
- `同业与行业材料主要集中在`

These phrases count as low-credit external framing. Existing Preview disclaimer, strong-confirmation, malformed-marker, missing/unused-reference, and source-boundary checks remain active. The peer boundary banner remains the split marker. The gate must still reject an unframed market-share or confirmed-order statement.

`build_curated_external_argument_display()` exposes validated groups only under the private key `_curated_external_topic_narratives`. It does not replace or edit `industry_logic`, `_curated_external_argument_cards`, `synthesis_text`, taxonomy fields, item counts, or source lists. Evidence profile, freshness, executive summary, recommendation, and any non-Chapter-4.3 consumer therefore continue to see the canonical exact-card projection.

## 10. Refresh And Runtime Behavior

The preview/refresh command performs the existing selector calls, builds the ready core pack, then makes one logical Topic Memo call with at most one HTTP attempt. The same model/base URL/key configuration may be reused, but the selector prompt and memo prompt remain separate functions and response schemas. The shared JSON request helper gains an optional timeout argument whose default remains 120 seconds for the existing selector; the memo passes `max_api_retries=0` and a 60-second timeout. It has no repair retry.

- Memo request failure or malformed top-level response: write the ready core pack with narrative `status=unavailable`; exit success if core cards are ready.
- Some groups invalid: write validated groups with `status=partial`; report falls back group by group.
- All groups valid: `status=ready`.
- Repeated report generation: zero LLM calls because the report only reads the stored pack.
- If the complete accepted-card payload cannot fit the configured model context, skip Topic Memo generation and store `status=unavailable`; never truncate cards or split into a hidden second batching strategy.

Expected added refresh latency is normally about 5-20 seconds and is bounded at 60 seconds. There is no memo retry or repair loop.

## 11. Proposed File Scope

Implementation is split into two gates so the producer contract can be proven before report cutover:

- **Batch A — producer/persistence:** build, validate, store, and read the optional envelope. Core packs and existing reports must behave exactly as before when the envelope is absent or invalid.
- **Batch B — display/read-model:** expose validated groups, project sentence-level refs, and render narrative-or-row fallback for formal-medium and formal-thin.

Batch B starts only after Batch A producer/reader tests pass and an invalid envelope is proven unable to poison a ready core pack. No live LLM run occurs between the batches.

Runtime:

- Create `scripts/utils/curated_external_topic_narrative.py`: pure prompt construction, fingerprint, validation, and envelope projection; it does not import OpenAI or perform I/O.
- Modify `scripts/utils/curated_external_argument_cards.py`: optional envelope read validation without weakening core pack validation.
- Modify `scripts/utils/curated_external_full_body_viewpoint_claims.py`: own the memo client factory using the existing JSON request helper and attach one optional narrative request after card production.
- Modify `scripts/previews/curated_external_full_body_viewpoint_preview.py`: enable the producer-time memo using existing LLM configuration and report narrative status.
- Modify `scripts/utils/curated_external_display.py`: expose only validated narrative groups.
- Modify `scripts/utils/deep_analysis_material_snapshot.py`: project structured parts and preserve full-snapshot refs.
- Modify `scripts/utils/reporter/sections/deep_analysis_renderer.py`: narrative-or-row rendering per group.
- Modify `scripts/utils/report_quality.py`: recognize the two new external-framing leads.

Focused tests mirror those files. Changes to scoring, technical, target, risk, recommendation, profile routing, `KnowledgeSynthesizer`, source collection, stock config, canonical pack data, Knowledge notes, or reports are forbidden during implementation.

Runtime budget is measured against the implementation-start `HEAD` for exactly the listed runtime files; docs and tests are excluded. Batch notes must include per-file additions, deletions, and net lines so replacement versus layering is auditable.

## 12. Required Tests

| Requirement | Required test |
| --- | --- |
| Same-file optional envelope | ready core pack reads successfully with no narrative object |
| Narrative cannot poison core pack | malformed/stale envelope returns cards `ok` and narrative status `invalid|stale` |
| One stock-level call | multiple topic groups invoke composer exactly once |
| No report-time LLM/source reads | display/snapshot/renderer tests use stored pack only and patch composer/source reads to raise |
| Private display projection | narratives do not alter `industry_logic`, exact-card synthesis text, profile inputs, freshness inputs, item count, or source list |
| Exact quote | paraphrased or edited quote rejects only its group |
| Complete boundary | mid-word/mid-clause quote is rejected; full bounded clause passes |
| Evidence ownership | omitting any source unit or representing one twice rejects the group |
| Subject preservation | a suffix quote that drops the source-unit subject is rejected; a complete prefix passes |
| No card cap | more than ten cards in one topic remain represented and render |
| Scope isolation | peer part cannot reference either target scope and the target bucket cannot reference a peer card/unit |
| Topic isolation | part cannot move an argument key to another family |
| Stable order | out-of-order parts reject the group |
| Forbidden prose/decision fields | free-form summary, target price, score, risk, or recommendation keys reject draft |
| Partial fallback | one invalid topic renders deterministic rows while another uses its memo |
| Formal-medium visibility | hidden parts are filtered, every unit of all remaining visible rows is covered exactly once, and no removed row is restored |
| Formal-thin offset | narrative refs equal baseline max plus full-snapshot refs, with all refs resolved |
| Unit-derived citations | persisted drafts cannot supply refs; projected refs exactly equal the referenced unit refs |
| Chapter 4.4 isolation | price-path rows/text are unchanged when narratives are present |
| Framing | new target and peer lead phrases pass external framing gates |
| Strong claim guard | unframed market share/order confirmation still fails quality gate |
| Presentation | each valid topic heading appears once and repeated `同业/行业背景观察：` is absent |
| Punctuation assembly | every part has local inline refs before punctuation and connector text introduces no factual words |
| Bounded memo request | memo performs one HTTP attempt with 60-second timeout while selector defaults remain unchanged |

Run focused producer/reader/display/snapshot/renderer/quality/source-boundary suites, full `pytest`, `tools/ci_grep_gates.sh`, and `git diff --check`. Live LLM and formal report generation are separate post-implementation acceptance gates.

## 13. Failure Modes And Stop Conditions

| Failure | Stop/response |
| --- | --- |
| Memo output changes card admission, family, scope, profile, or citations | stop; display projection crossed the evidence boundary |
| Report path imports/calls LLM client or reads source JSONL | stop; runtime ownership violated |
| Invalid memo makes a valid core pack unreadable | stop; optional-envelope isolation failed |
| A sentence cannot be reconstructed from exact validated quote parts | reject that group and use deterministic fallback |
| Target and peer material appear in one paragraph | stop; entity ownership regression |
| Narrative refs use a filtered/new offset rather than full snapshot refs | stop; formal-thin citation regression |
| Implementation needs a second model/verifier or repair loop | return to design |
| Implementation adds a total display cap | stop; no-cap contract violated |
| Batch A runtime net growth exceeds +220 lines or Batch B exceeds +170 lines | stop and return with a deletion/reuse audit |
| Combined runtime net growth exceeds +380 lines | stop; same-pack simplicity has not translated into a bounded implementation |

## 14. Acceptance Gate

After code-level acceptance, run one producer refresh for 中际旭创, 复旦微电, and 黑芝麻智能 using local source inputs and the configured live model, then generate fresh reports for 中际旭创 and 复旦微电. Approval requires:

- no unsupported quote or entity binding;
- target/peer scope remains correct;
- every used quote has a resolved inline citation;
- at least one valid memo topic in each stock, otherwise the feature has not demonstrated value;
- invalid groups visibly fall back without blocking the report;
- Chapter 4.3 reads as topic paragraphs and does not repeat `同业/行业背景观察：` per card;
- quality/source/prose/CI gates contain no new error;
- scoring, target, risk, technical analysis, recommendation, and Chapter 4.4 are unchanged.

Because this changes LLM composition behavior, representative live paragraph output must be shown to the user for confirmation before merge.

## 15. Codex Self-Review Delta

Two Codex self-review rounds were completed on 2026-07-21.

- Accepted: evidence-unit exact coverage replaces card-only coverage; quote suffix extraction is forbidden; memo request is one attempt with a 60-second timeout; optional-envelope reader status is explicit; raw invalid model text is not persisted.
- Accepted: narrative data stays under a private display key; exact-card synthesis/profile/freshness inputs remain unchanged; citation refs are inherited from canonical units; punctuation and inline-marker order are deterministic; runtime budgets use implementation-start `HEAD`.
- Rejected: free-writing paraphrase and a second verification model. They improve style but recreate the hallucination, latency, and evidence-ownership failures already seen in live gates.
- Deferred: report-time memo generation, narrative sidecars, cached Knowledge notes, cross-topic synthesis, and Chapter 4.4 memo use.
- Independent Level 3 Round 1 review remains required before implementation.
