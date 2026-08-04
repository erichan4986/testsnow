# Chapter 4 Evidence Boundary and SourceUnit Repair Design

Date: 2026-07-16
Status: three Codex self-review rounds passed; independent Level 3 review pending

## Evidence

The fresh 20260716 reports reveal three independent defects.

1. Zhongji (`formal_medium`) 4.4 renders an official and an external condition,
   but omits an institution-assumption condition although 4.2 has usable broker
   material. The snapshot rejects every broker row whose title is a generic
   memo heading such as `券商核心观点`.
2. Fudan 4.1 puts an R&D/product sentence and an unrelated other-income-change
   explanation in the same `研发与产品进展` row. The annual narrative pack shows
   that these are distinct source units (`cash_flow_capex_table-0:u5` and
   `:u6`) concatenated into one display card.
3. Fudan 4.3 cites an article titled `聚辰股份...` for target-company MCU/EEPROM
   assertions. The cached external narrative joins target-company claims and a
   peer citation before the renderer sees it.

These are not one renderer problem. A renderer substring filter would either
hide material without fixing its ownership or leave an unsupported assertion
with a footnote removed.

## Decision

Use two batches.

### Rejected alternatives

1. **Renderer-only masking**: rejected. It can remove a useful clause, leave a
   target assertion uncited, or create a second selection owner.
2. **A complete entity graph for every external claim**: deferred. It is useful
   long term, but exceeds the evidence-boundary repair and needs an explicit
   source ontology project.
3. **Recommended two-batch repair**: a narrow snapshot/display safeguard first,
   followed by annual SourceUnit card ownership. It assigns each fault to the
   component that owns the corresponding evidence decision.

## Scope and Non-goals

Both batches preserve raw annual/broker/external inputs. Neither batch changes
profile selection, scoring, target price, risk score, technical analysis,
recommendation, citation allocation/offset arithmetic, collection, cached data,
or an LLM prompt.

`formal_rich` keeps its legacy Chapter 4 route. External observations remain
Preview-only and never become a 4.1 confirmation, a core fact, or a scoring
input.

The first batch must not generate formal reports or access the network. Formal
report validation follows only after focused tests are green.

## Batch A: 4.4 Institution Condition and External Entity Boundary

### A1. Snapshot price-path broker fallback

Owner: `deep_analysis_material_snapshot.py`.

`_select_price_path_rows()` continues to choose an annual row, a broker row,
and an already-selected external row. Its broker selection changes only as
follows:

1. Prefer an informative-title `broker_assumption` or `broker_forecast` row as
   today.
2. If none exists, select the first visible `broker_assumption`; if no
   assumption exists, select the first visible `broker_forecast`.
3. Never select `broker_risk` as the institution condition.
4. In the 4.4-only tuple returned by `_select_price_path_rows()`, use
   `dataclasses.replace()` to change a generic title to
   `<attribution>研报核心假设` (or `研报核心假设` when attribution is the generic
   fallback `研报`). The original row in 4.2 remains unchanged.

`argument_complete` is not a broker-selection input: `_broker_rows()` does not
currently propagate that field, and the already-visible 4.2 order is the
deterministic editorial order. No new diagnostic or renderer branch is needed;
the renderer continues to print the ViewModel row title. It must never print an
unhelpful heading such as `机构假设：券商核心观点` merely because the memo title
is generic.

The fallback must deliberately bypass `_select_price_row()`'s informative-title
filter. It scans the original ordered broker rows by role after the normal
informative selection has failed; applying the same filter twice would preserve
the current omission. "Visible" means a row has non-empty body and at least one
mapped citation, not merely a non-empty generic title.

This does not alter the actual broker text, model, forecast, score, or target
price. It only guarantees that 4.4 expresses the already-visible 4.2 broker
assumption as a conditional statement.

### A2. Curated external target-claim boundary

Owner: one pure source-title scope classifier in
`curated_external_display.py`. `curated_external_viewpoint_narrative.py` uses
it to reject unsafe digest claims before calling the composer, and
`build_curated_external_narrative_display()` uses it to validate cached JSON.
The second call is required: the current report path reads
`fudan_20260702.json` directly and would otherwise bypass a producer-only fix.

`build_curated_external_narrative_display()` receives a required keyword-only
`expected_stock_name`; `SynthesisSkill` passes the normalized
`ctx.get("stock_name")` value. An empty expected name returns
`missing_stock_identity`. The loader requires the expected name to equal a
non-empty cached `stock_name`; a mismatch returns
`stock_identity_mismatch` instead of trusting the cache or guessing. All three
currently configured narrative caches contain the expected `stock_name`, so
this is contract hardening rather than a data migration.

The fresh builder has the same identity contract: its `stock_name` argument is
required, non-empty, and must equal a non-empty digest `stock_name` when that
field is present. It returns `stock_identity_mismatch` before claim admission
when they differ. The preview caller and all direct tests pass the configured
stock name explicitly; neither path may fall back to an untrusted cache/digest
name merely because its explicit argument was omitted.

The shared classifier receives a source title and configured target name and
returns `target`, `foreign_company`, or `ambiguous`. Target-name containment is
checked first. A title is `foreign_company` only when it excludes the target
name and its leading issuer token either:

- ends in a structural company suffix such as `股份`, `科技`, `电子`, `微电`,
  `智能`, or `集团` and is followed by `:` / `：`; or
- is followed immediately by a 6-digit stock code in parentheses.

`聚辰股份:...` and `新易盛(300502)...` therefore classify as foreign for a
different target, while `全球科技趋势` and `行业观察:...` remain ambiguous.
Titles without either syntax are `ambiguous` and fail open as Preview. This is
a structural parser, not a stock-name or industry-specific dictionary.

Claims/paragraphs are separately classified from their text, heading, and
configured `stock_name` as:

- `target_fact`: the normalized claim, source quote, paragraph text, or heading
  explicitly contains the configured `stock_name`. Substring matching allows
  `复旦微电` to match `复旦微电子`; no product/metric is guessed to be
  target-specific in this batch.
- `peer_or_industry_context`: it is explicitly framed as `同业`, `竞品`,
  `行业`, `产业链`, or `市场` context and does not make a factual assertion
  about the target company; or it has a `foreign_company` citation while its
  own evidence text does not contain the target name.
- `ambiguous`: neither deterministic condition holds.

A `target_fact` claim is rejected when all of the following are true:

1. it has at least one surviving citation; and
2. every surviving citation is classified `foreign_company`.

An abstract/generic article title is not treated as foreign evidence by this
gate. The test fixture uses `复旦微电` as target and `聚辰股份:...` as the sole
cited-source title. The entire target-fact claim is dropped, including its
citation; no renderer is allowed to retain the assertion with an unrelated or
missing footnote.

Peer/industry material may remain only when it is a separate claim/card and
has an explicit `peer_or_industry_context` classification. Its rendered heading
is `同业/行业背景（Preview）`; it must not be merged into a target-company sentence.
Ambiguous material is retained as ordinary Preview only when the normal source
validation accepts it; it may not be promoted to a target fact.

The fresh-producer path applies the predicate to each validated digest claim
before composition, so a rejected claim cannot contaminate a mixed paragraph
and other safe claims remain available to the composer. The cached-display path
has no claim-to-sentence map, so it applies a fail-closed rule:

1. build one `claim_id -> evidence text` index from each reasoning card's
   `claim`, `source_excerpt`, and `display_topic`; when a claim lacks a card,
   add the text/heading of paragraphs that reference it;
2. collect rejected `claim_id` values by applying the shared title/target
   predicate to that indexed text and citation metadata, using one shared
   exact-then-unique-suffix claim-ID resolver. Batch A also replaces the
   current last-write hydration suffix map with that resolver; duplicate suffix
   matches are ambiguous and resolve to no claim rather than to the last match;
3. remove reasoning cards whose `claim_id` is rejected;
4. drop an entire paragraph if any `claim_ref` is rejected; never rewrite its
   prose or detach only the bad footnote;
5. compact citations from the union of refs used by remaining paragraphs and
   reasoning cards before hydration and display construction. A safe standalone
   card therefore keeps its source even if a mixed paragraph was dropped.

The result is valid when it retains either a paragraph or a reasoning card with
at least one mapped citation. The current `not paragraphs or not citations`
empty check must become `not citations or not (paragraphs or reasoning_cards)`;
otherwise the required safe-card case would still disappear after filtering.

The fresh path has the same citation-ownership invariant. It validates and
lints paragraphs first, normalizes safe reasoning cards, then compacts the
single citation map over the union of both retained object types. It must not
compact inside paragraph linting before cards are normalized. This changes only
the local curated-narrative ref map; the `MaterialSnapshot` allocator and all
formal-thin offset arithmetic remain unchanged.

For a retained `peer_or_industry_context` item, attach the display-only field
`entity_context=peer_or_industry_context`. Normalization preserves the field and
sets its heading to `同业/行业背景（Preview）`; `_external_rows()` can consume the
existing `heading` field without a second entity decision.

The gate is deterministic and deliberately narrow. It uses only configured
target name, explicit source titles, and explicit peer/industry framing. The
helper returns rejection counts/reasons for diagnostics. It does not infer
entity relationships from prose, embeddings, LLM calls, or a hardcoded
stock/industry list.

After filtering, citations are compacted through the existing narrative
compaction path. The display consumer receives a coherent paragraph/card set
and a matching citation map, so visible-ref alignment remains intact. The
cached JSON is never rewritten.

### A3. Batch A tests

Add focused tests for:

| Case | Expected result |
|---|---|
| generic broker title, usable attributed broker row | 4.4 has an institution condition with deterministic attribution label |
| generic broker title plus risk-only row | uses assumption/forecast, not risk-only row |
| informative broker title | existing selection and label stay unchanged |
| fresh target claim, sole citation title names another company | claim is removed before composer; other safe claims remain available |
| cached target reasoning card, sole citation title names another company | card and citation are absent |
| cached mixed paragraph references one rejected claim | whole paragraph is absent; no partial rewrite/dangling ref |
| cached mixed paragraph also has a safe reasoning card | paragraph is dropped, safe standalone card remains available |
| safe standalone card is the only remaining owner of a citation | citation remains and is not reported unused |
| cached display retains only a safe reasoning card | status is `ok`, card and citation render without a paragraph |
| fresh lint drops a paragraph while a safe reasoning card retains its claim | card keeps its citation after final compaction |
| target fact, citation title contains target | claim remains |
| generic/ambiguous title without company syntax | claim remains Preview; no false foreign-company rejection |
| expected stock and cached `stock_name` differ | status is `stock_identity_mismatch`, no display |
| expected stock is empty | status is `missing_stock_identity`, no display |
| synthesis context has no `stock_name` | status is `missing_stock_identity`, no display |
| fresh configured stock and digest `stock_name` differ | status is `stock_identity_mismatch`, composer is not called |
| two claim IDs share a suffix | no suffix-based citation/entity binding occurs |
| explicitly framed peer paragraph with a peer citation | remains separate Preview context, never target fact |
| drop leaves no citations | result is empty/valid, with no dangling refs |

Run the snapshot, deep-analysis renderer, curated narrative, curated display,
and synthesis consumer suites. Assert `missing`, `unused`, and `未知` behavior
through existing citation-oriented renderer fixtures rather than creating a
parallel checker.

Update existing direct display fixtures to carry a matching non-empty
`stock_name` in both the JSON payload and `expected_stock_name` argument.
Existing non-`ok` status fixtures retain their original status contract unless
they intentionally exercise the new identity gate.

The existing `_sanitize_indirect_industry_citations_from_43()` remains a legacy
synthesis-output policy and is not expanded in this batch. Its source-type
policy differs from curated narrative entity validation; tests must confirm the
new path does not call or duplicate its line-dropping behavior.

### A4. Batch A failure modes and stop conditions

| Failure | Required behavior |
|---|---|
| generic titles hide all broker price-path conditions | deterministic fallback only for broker assumption/forecast roles |
| foreign-company article leaks into target fact | drop whole target claim before display/citation hydration |
| valid peer context disappears | retain only as separately labelled peer/industry Preview |
| source title is ambiguous | do not falsely call it a foreign-company rejection |
| citation compaction changes offsets | no change to snapshot allocator or renderer offset formula |
| paragraph is dropped but safe card still uses a source | compact over paragraph/card ref union |
| only a safe card survives | return a valid card-only display with its mapped citation |
| cached narrative belongs to another stock | fail closed before paragraph/citation hydration |

Stop and return to design if the repair needs to modify cached external JSON,
citation allocator/offset logic, source collection, a prompt, or a quality
gate; if it requires fuzzy entity matching; or if it changes `formal_thin`
offset behavior.

Batch A expected runtime delta is at most +85 lines across snapshot, curated
display/narrative, and the synthesis call site; +120 is a hard stop. The
renderer runtime should remain unchanged.
Tests and documents are excluded from this ledger. Measure against the
pre-Batch-A worktree state, not an older branch baseline.

## Batch B: Annual SourceUnit Display Ownership

Batch B starts only after Batch A is accepted. It is intentionally a separate
producer task.

Owner: `periodic_report_narrative_evidence_cards.py` and its existing annual
material-pack consumer.

### B1. SourceUnit invariant

An annual display card can contain a contiguous bundle of SourceUnits only
when every unit belongs to the same `argument_family` and the later unit
continues the same argument. A unit that opens a new financial explanation,
even when adjacent to an R&D sentence in the same source block, begins a new
candidate/card.

The bundle loop checks `following_family != family` before any continuation
state shortcut. For this fixture, add the generic financial metric
`其他收益` (`其他收益变动原因说明`) so u6 resolves to
`financial_quality_explanation` rather than inheriting the surrounding
technology usage. This is a schema-level financial phrase, not a Fudan-specific
rule. Do not classify every mention of `政府补助` or `税收优惠` as financial on
its own.

For the Fudan regression:

- `cash_flow_capex_table-0:u5` remains a technology/product-progress R&D
  statement;
- `cash_flow_capex_table-0:u6` becomes a financial-quality explanation;
- they never appear in one 4.1 display row.

No raw source text is discarded merely to improve Chapter 4. The output retains
both units with their original source IDs, order, and citations. The display
selector may later decide which card fits a role budget, but it cannot merge
two conflicting argument families back together.

### B2. Admission and renderer boundaries

The producer owns SourceUnit classification and bundle boundaries. The
`MaterialSnapshot` retains its existing display-row selection role; the
renderer only groups already-classified rows. Do not add a new renderer
sentence splitter or a Fudan-specific keyword rule.

### B3. Batch B tests

| Case | Expected result |
|---|---|
| adjacent same-family continuation | one ordered card with contiguous unit IDs |
| adjacent technology then financial explanation | two cards, no shared unit IDs |
| exact Fudan u5/u6 text | technology card contains only u5; financial card only u6 |
| material pack to snapshot | roles remain distinct and citations remain traceable |
| Chapter 4 annual grouping | R&D section cannot contain the financial other-income explanation |

### B4. Batch B stop conditions

Stop if the repair requires accepting/rejecting more source material to force
coverage, introduces a second selector, changes annual source unit identity,
or exceeds +20 expected / +40 hard-stop runtime lines measured from the accepted
Batch A state. This batch needs its own
implementation task and review because it changes producer behavior.

## Acceptance Sequence

1. Implement and test Batch A in isolation; no formal report run.
2. Run a local formal-report acceptance only after Batch A focused tests pass:
   Zhongji 4.4 must have official, institution, and external layers when those
   source layers exist; Fudan must not contain a target-company claim supported
   only by a different-company title.
3. Design/review/implement Batch B separately.
4. Repeat Fudan report acceptance: the R&D and other-income explanations must
   be separate rows/roles, and all citation/source-boundary checks must pass.
5. Because Batch A changes the set of claims sent to the narrative composer,
   show the user an offline deterministic/heuristic sample in which the foreign
   target claim is absent and a safe target claim remains. User confirmation is
   required before merge; no paid LLM call is required for this sample.

## Scope Audit

| Area | Batch A | Batch B |
|---|---:|---:|
| Chapter 4 view/snapshot | yes | consumes unchanged contract |
| curated external producer/display | yes | no |
| annual producer/material pack | no | yes |
| renderer formatting | unchanged consumer; tests only | no new selection |
| synthesis skill | pass expected stock name only | no |
| profile/scoring/target/risk/technical/recommendation | no | no |
| LLM prompt/collection/cached data | no | no |
