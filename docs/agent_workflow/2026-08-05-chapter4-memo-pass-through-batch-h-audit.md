# Chapter 4 Memo Pass-Through Batch H Audit

## Verdict

`implementation_candidate`

`annual_report_memo.v1` and `broker_research_memo.v1` are now internal
intermediate projections rather than durable source contracts. They are built
inside `SynthesisSkill`, read by the evidence profile/coverage diagnostics, and
then converted a second time into `MaterialRow` by
`deep_analysis_material_snapshot.py`.

The next safe reduction is a behavior-preserving Batch H1: project the existing
annual packs and broker digest items directly into the Chapter 4 read model,
derive the same profile diagnostics from that projection, and remove both memo
builders. Content-policy changes belong in a later H2 batch.

This audit changes no runtime, tests, configuration, data, Knowledge notes, or
reports.

## Current Data Flow

### Annual

1. `PeriodicReportFulltextIntakeSkill` produces current in-memory narrative
   cards, filing facts, and explanation rows.
2. `build_annual_report_material_pack()` reads the validated canonical pack.
3. `SynthesisSkill._annual_narrative_cards()` prefers current in-memory cards
   over the persisted pack.
4. `_build_annual_report_memo()` cleans, truncates, deduplicates, maps families,
   creates rows, allocates local citations, and derives a memo status.
5. `_annual_rows()` converts those rows and citations into `MaterialRow`.

### Broker

1. Broker digest notes are refreshed, loaded, cleaned, and converted to guarded
   `SynthesisItem` objects.
2. `_build_broker_research_memo()` repeats guard checks, deduplicates, derives
   admission/status, adds attribution, caps output at six rows, and allocates
   local citations.
3. `_broker_rows()` converts the memo rows and citations into `MaterialRow`.

The evidence profile and coverage diagnostics read only memo status/count
fields. No external runtime consumer needs either memo schema directly.

## Evidence

- `SynthesisSkill` is 1,880 lines.
- The two memo paths occupy 339 lines before their profile/coverage consumers:
  - annual card choice/cleaning/table guard/memo builder: 203 lines;
  - broker memo builder: 136 lines.
- All eight configured stocks load annual material in `pack_first` mode.
- All eight report `v1_adapter_use_count=0` and
  `v1_actionable_needs_recovery_count=0`.
- The current canonical annual packs contain 651 selected cards. The memo
  cleaner changes the display text of 505, truncates 36 above 300 characters,
  and removes 72 exact normalized duplicates. The old table-fragment and
  forbidden-source guards reject zero canonical cards.
- Current local broker material is sparse: four guarded items for 中际旭创,
  two for 圣邦股份, and none for the other configured stocks. The memo's
  `selected[:6]` is therefore a hidden secondary cap, not the intake budget.

## Findings

### H1. The memo schemas duplicate the read-model adapter

Both builders turn structured producer output into row dictionaries, allocate
citations, and are immediately adapted again. This is an ownership problem,
not merely a large-file problem.

Direction: `build_deep_analysis_material_snapshot()` should consume:

- `periodic_report_narrative_evidence_cards` when non-empty, otherwise
  `annual_report_material_pack.selected_narrative_cards`;
- `formal_financial_fact_pack.facts`;
- `formal_financial_explanation_pack.rows`;
- one already-loaded `broker_research_digest_items` list.

The snapshot remains the sole `MaterialRow` and citation owner.

### H2. Annual display cleanup is still active and cannot simply disappear

Canonical annual cards preserve exact source-unit text. Visible PDF/OCR spacing
cleanup is therefore still useful, especially for HK traditional-Chinese text.
Moving directly to raw pass-through would make reports noisier.

Direction for H1: move the existing visible-text normalization into the annual
MaterialRow projection without changing source cards. Preserve the current
300-character boundary and exact-body dedupe for equivalence. Do not push
display cleanup back into the producer because that would weaken exact source
substring guarantees.

### H3. Legacy annual compatibility is no longer a production blocker

The material-pack adapter remains responsible for persisted legacy migration,
but all configured canonical packs currently require zero v1 recovery. The memo
does not need its separate legacy `card_type` family map. A canonical card must
already carry `argument_family`; adapted legacy cards receive that field before
they reach the read model.

Direction: delete the memo-local family map and test canonical families at the
pack/read-model boundary.

### H4. Broker items are loaded more than once

The memo builder, freshness overlay, and optional display synthesis can each
call `_eligible_broker_research_digest_items()`. This repeats note-directory
reads and makes the memo appear to own eligibility.

Direction: after note refresh, load guarded items once, store them in
`broker_research_digest_items`, and let memo replacement, freshness, and display
synthesis consume that list.

### H5. Policy changes must not be hidden inside H1

The current memo applies three content decisions:

- annual excerpts are bounded at 300 characters;
- broker rows are bounded again by `selected[:6]` after the configured loader
  budget;
- one thin broker item receives `status=absent` and is not displayed.

These choices deserve reconsideration, but removing them changes visible report
content and profile routing. H1 must preserve them. H2 may remove the secondary
six-row cap, retain full annual bodies in the snapshot, and define a sparse
broker display state only after report comparison.

## Recommended H1 Design

1. Add pure annual/broker input adapters to
   `deep_analysis_material_snapshot.py`; they return rows plus the status and
   diagnostics currently exposed by the memos.
2. Make `SynthesisSkill` load broker digest items once after refresh.
3. Replace `_build_annual_report_memo()` and
   `_build_broker_research_memo()` with one lightweight read-model summary call
   used by evidence-profile and coverage diagnostics.
4. Preserve the public evidence-profile keys
   `annual_memo_status`, `broker_memo_status`,
   `broker_usable_card_count`, `broker_content_families`, and
   `broker_institution_count` during migration even though the memo objects are
   removed from `ctx`.
5. Build the renderer snapshot directly from the upstream packs/items. Keep
   pipeline order, profile names, citation order, and visible Chapter 4 output
   unchanged.
6. Delete:
   - `_annual_narrative_cards()`;
   - `_clean_annual_memo_excerpt()` from `SynthesisSkill` after its projection
     equivalent is tested;
   - `_looks_like_annual_table_fragment()`;
   - `_build_annual_report_memo()`;
   - `_build_broker_research_memo()`;
   - memo-only fixtures and schema assertions.

Do not create another memo-shaped module merely to move these lines out of
`SynthesisSkill`.

## Expected Budget

- removable `SynthesisSkill` surface: about 330-360 runtime lines, including
  simplified profile/coverage reads;
- replacement direct adapters/status summary: about 110-160 lines after
  replacing existing `_annual_rows()` and `_broker_rows()`;
- target net runtime reduction: at least 160 lines;
- hard stop: stop and return to design if net reduction is below 110 lines or a
  third formal-material projection path appears.

## Required Tests

| Requirement | Guard |
|---|---|
| current in-memory annual cards beat a stale persisted pack | existing 复旦 fixture rewritten at the snapshot boundary |
| canonical annual family and `argument_complete` survive | direct MaterialRow contract test |
| visible annual whitespace/table cleanup is unchanged | 复旦 noisy annual fixture |
| HK traditional-Chinese source remains readable | 黑芝麻智能 fixture with CJK spacing |
| annual status/profile routing is unchanged | ready/fallback/absent profile matrix |
| broker guardrails and attribution survive | 中际 multi-institution fixture |
| forecast/risk refs remain globally valid | snapshot citation identity regression |
| single-institution status is preserved | 圣邦 two-item/same-family fixture |
| broker notes are loaded once | loader call-count test |
| memo schemas are gone from runtime | hygiene grep assertions |

After focused tests, run three offline report comparisons:

1. 中际旭创: annual plus multi-institution broker material;
2. 复旦微电: dense A-share annual material and no broker material;
3. 黑芝麻智能: HK annual format and no broker material.

For H1, Chapter 4 text, profile, source identities, and citation count must be
equivalent except for explicitly documented whitespace-only differences.

## Failure Modes And Stop Conditions

| Failure mode | Visible symptom | Stop/guard |
|---|---|---|
| display cleanup is removed with the memo | CJK word spacing and PDF headers reappear | noisy A/HK fixtures |
| current cards lose precedence | report shows stale persisted material | in-memory-over-pack test |
| profile reads missing memo fields | profile falls from formal-medium to thin | exact profile matrix |
| citation order changes | footnotes point to the wrong source | identity and report comparison |
| broker loader runs repeatedly | extra disk work and inconsistent note view | call-count test |
| H1 changes admission/caps | row counts change before H2 | frozen snapshot equivalence |
| implementation only relocates code | runtime does not shrink | net reduction hard stop |

Stop if implementation requires producer schema changes, LLM prompt changes,
pipeline reordering, profile-name changes, or edits to scoring, target price,
risk, technical analysis, recommendation, data, Knowledge notes, or reports.

## Scope And Process

This is a Level 3 refactor because it removes two internal schemas and changes
more than three files across synthesis and the Chapter 4 read model.

Expected runtime scope:

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/deep_analysis_material_snapshot.py`

Expected tests:

- `tests/reporter/test_synthesis_skills.py`
- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/test_runtime_hygiene.py`

## Recommendation

Proceed with a locked H1 design and two self-reviews before implementation.
Keep H1 behavior-preserving and measure code deletion. Only after H1 passes the
three-stock comparison should H2 revisit truncation, secondary caps, or sparse
broker admission.
