# Deep Analysis MaterialSnapshot S0 Audit

Date: 2026-07-06

Scope: read-only audit for
`docs/agent_workflow/2026-07-06-deep-analysis-material-snapshot-design.md`.
No runtime code should be changed in S0.

## Audit Conclusion

Proceed to S1 only as an adapter/read-model. The current code already has most
row-level citation fields on annual and broker memo rows, while external display
rows carry `citation_refs` in several shapes. The highest-value cleanup target is
not the producers; it is `DeepAnalysisRenderer` citation offset / merge / used-ref
plumbing.

Do not delete helpers yet. Several helpers still serve formal-rich 4.4 external
addendum, Markdown source-boundary gates, and sidecar-backed quality gates.

## Producer Contract Map

| Producer | Current ctx field | Current core fields | Current consumers | Snapshot V1 decision |
| --- | --- | --- | --- | --- |
| Annual memo | `annual_report_memo` | `sections.confirmed`, `sections.annual_report_explanation`, `sections.not_disclosed`, `sections.inconclusive`, `citations` | `DeepAnalysisRenderer._annual_report_memo_section`, profile diagnostics, renderer tests | Enter Snapshot V1 |
| Broker memo | `broker_research_memo` | `sections`, `forecast_ranges`, `risks`, `citations`, `diagnostics`, `validation` | `DeepAnalysisRenderer._broker_research_memo_section`, profile diagnostics, renderer/tests | Enter Snapshot V1 |
| External display | `deep_analysis_display` | `_curated_external_reasoning_cards`, `_curated_external_topic_groups`, `_curated_external_narrative_paragraphs`, `citations` | formal-rich 4.4 addendum, formal-thin external map, `report_quality.py`, `report_source_boundary.py`, renderer tests | Enter Snapshot V1 |
| Fundflow pack | `fundflow_material_pack` | `rows`, `summary` | `KnowledgeSynthesizer` prompt appendix, sidecar persistence, `report_quality.py` fundflow gate, tests | Diagnostics only in V1 |
| Peer material | `peer_comparison_material` | `rows`, `source_refs`, confidence fields | `KnowledgeSynthesizer` peer appendix, executive-summary PE sanitizer, deep-analysis PE sanitizer, sidecar persistence, `report_quality.py` peer gates | Diagnostics only in V1 |

## Existing Row Shapes

### Annual Memo

Location: `scripts/utils/report_skills/synthesis_skills.py`.

Rows from `_build_annual_report_memo()` already look close to `EvidenceRow`:

- visible fields: `title`, `body`;
- audit fields: `internal_refs`, `citation_refs`, `source_ref_ids`;
- grouping: optional `display_group`;
- local citation metadata: `citations`.

Snapshot projection can map:

- `row_id`: `annual:<section>:<index>`;
- `text`: `"{title}：{body}"`;
- `source_layer`: `annual`;
- `claim_status`: `formal_fact` for confirmed rows, `formal_explanation`
  for explanation rows, `disclosure_boundary` for undisclosed/inconclusive rows;
- `display_scope`: `("deep_analysis",)`;
- `scoring_eligible`: `False`;
- `risk_score_eligible`: `False`;
- `section_hint`: `4.1` or `annual_memo`.

No producer replacement is needed in S1.

### Broker Memo

Location: `scripts/utils/report_skills/synthesis_skills.py`.

Rows from `_build_broker_research_memo()` already include the same audit fields
across `sections`, `forecast_ranges`, and `risks`:

- `internal_refs`;
- `citation_refs`;
- `source_ref_ids`.

Snapshot projection can map:

- `row_id`: `broker:<kind>:<index>`;
- `source_layer`: `broker`;
- `claim_status`: `professional_analysis`;
- `display_scope`: `("deep_analysis",)`;
- `scoring_eligible`: `False`;
- `risk_score_eligible`: `False`;
- `section_hint`: `4.2` or `broker_memo`.

Important: forecast and risk rows are rendered, so they must remain in the
snapshot contract. This matches the previous review finding about
`forecast_ranges`.

### External Display

Location: `scripts/utils/report_skills/synthesis_skills.py` and
`scripts/utils/curated_external_display.py`.

Current shapes:

- narrative paragraphs: `heading`, `text`, `citation_refs`;
- reasoning cards: `claim`, `reasoning_steps`, `counterpoints`,
  `verification_need`, `citation_refs`;
- topic-group rows: `heading`, `text`, `citation_refs`;
- global `citations` metadata.

Snapshot projection should preserve display-only status:

- `source_layer`: `external`;
- `claim_status`: `external_observation`;
- `display_scope`: `("deep_analysis",)`;
- `scoring_eligible`: `False`;
- `risk_score_eligible`: `False`;
- `section_hint`: `4.3` for formal-thin annual/broker layout, `4.4` for
  formal-rich legacy addendum.

Do not infer formal facts from external rows.

### Fundflow Pack

Location: `scripts/utils/fundflow_material.py`,
`scripts/utils/report_skills/synthesis_skills.py`.

Fundflow material already has a deterministic pack and quality gate. It also
feeds `KnowledgeSynthesizer` as a funding appendix.

S1 should only place it in `MaterialSnapshot.diagnostics`, for example:

- `fundflow_rows_count`;
- `fundflow_summary_signal`;
- `fundflow_has_sidecar_material`.

Do not move fundflow rows into renderable `EvidenceRow` in V1. That would risk
changing 4.3 synthesis behavior.

### Peer Material

Location: `scripts/utils/peer_comparison_material.py`,
`scripts/utils/reporter/sections/executive_summary_renderer.py`,
`scripts/utils/reporter/sections/deep_analysis_renderer.py`,
`scripts/utils/report_quality.py`.

Peer material currently serves several non-deep-snapshot consumers:

- `KnowledgeSynthesizer` peer appendix;
- executive-summary PE spread sanitizer;
- deep-analysis PE spread sanitizer;
- sidecar persistence;
- peer comparison quality gates.

S1 should only place peer diagnostics in the snapshot:

- `peer_rows_count`;
- `peer_high_confidence_rows`;
- `peer_has_social_leak`.

Do not replace peer material consumers in V1.

## Renderer Helper Audit

| Helper / local variable | Current role | S1/S2 status | Deletion candidate |
| --- | --- | --- | --- |
| `annual_citation_offset` | Offsets annual memo refs after baseline synthesis citations | Replace in S2 by snapshot citation allocation | yes, after S2 |
| `broker_citation_offset` | Offsets broker memo refs after annual memo citations | Replace in S2 by snapshot citation allocation | yes, after S2 |
| `curated_citation_offset` | Offsets external display refs after baseline + annual + broker | Replace in S2/S3 only if snapshot owns external rows | yes, after S2/S3 |
| `_max_citation_id` | Finds next citation offset | Keep until all renderer citation merging moves to snapshot | later |
| `_merged_citations` | Merges citation maps with offsets | Keep until renderer uses snapshot citations for annual/broker/external | later |
| `_offset_citations` | Offsets local citation maps | Keep; also used by legacy 4.4 external addendum | later |
| `_append_section_citations` | Renders local section citation lists | Keep; can consume snapshot refs later but not dead | no for S2 |
| `_used_formal_thin_external_citations` | Finds external refs used by formal-thin map/checklist | Strong S2/S3 replacement candidate | yes, after snapshot external rows |
| `_curated_external_display_ref_map` | Dedupes/remaps external citations for visible 4.4 addendum | Keep until snapshot has external citation canonicalization | later |
| `_curated_external_used_refs_from_rows` | Collects refs from narrative/reasoning rows | Keep until external rows are projected to snapshot | later |
| `_curated_external_used_refs_from_grouped_rows` | Collects refs from topic-group rows | Keep until external rows are projected to snapshot | later |

## Quality / Source Boundary Audit

### `report_quality.py`

Keep existing Markdown regex gates in V1. Snapshot should be additive at first.

Safe first snapshot gates:

- citation ref exists in snapshot citations;
- row has only `display_scope=("deep_analysis",)`;
- low-credit/external row has `scoring_eligible=False` and
  `risk_score_eligible=False`;
- row with `source_layer=external` has display-only framing.

Do not replace these existing gates in S3:

- required deep-analysis subsection checks;
- financial direction contradiction checks;
- industry-chain relevance checks;
- peer comparison support checks;
- fundflow claim checks;
- prose quality warnings.

Reason: those gates operate on final Markdown semantics or sidecar packs, not
just row contracts.

### `report_source_boundary.py`

Keep region-based Markdown scanning in V1. It knows current layout-specific
heading rules:

- formal-thin annual/broker/external layout permits external tokens in the
  external map region;
- formal analysis region still blocks social/external tokens.

Snapshot can later simplify some display-only leak checks, but it should not
remove Markdown region scanning until generated reports prove equivalent.

## S1 Adapter Requirements

The adapter should be pure:

```python
snapshot = build_deep_analysis_material_snapshot(ctx)
```

It must not mutate `ctx`.

Recommended S1 tests:

1. Annual confirmed/explanation rows project to immutable `EvidenceRow` objects.
2. Broker sections, forecast rows, and risk rows project with citation refs.
3. External reasoning cards and topic rows project as display-only rows.
4. Fundflow and peer material appear only in `snapshot.diagnostics`.
5. All rows have `display_scope == ("deep_analysis",)`.
6. All rows have `scoring_eligible is False` and
   `risk_score_eligible is False` unless source layer is later explicitly
   allowed by a new design.
7. Building the snapshot does not write `synthesis`, `synthesis_display`,
   `core_facts`, `pillar`, `recommendation_decision`,
   `structured_risk_signals`, or `price_target`.

## S2 First Replacement Target

Start with formal-thin annual/broker/external citation plumbing only:

- replace local offset computation with snapshot citation allocation;
- keep Markdown body text unchanged;
- keep section headings unchanged;
- keep formal-rich path unchanged in the first S2 patch if possible.

The smallest useful S2 success criterion:

- Fudan formal-thin fixture renders the same section text;
- every visible `[^n]` resolves in the global citation section;
- `report_source_boundary.py` still passes.

## Do Not Delete Yet

Do not delete these in S1:

- `_offset_citations`
- `_merged_citations`
- `_max_citation_id`
- `_append_section_citations`
- curated external addendum helpers
- source-boundary region helpers
- peer/fundflow sidecar loaders

They are not dead code yet.

## Recommended Next Step

Implement S1 only:

- create `scripts/utils/deep_analysis_material_snapshot.py`;
- add tests under `tests/utils/test_deep_analysis_material_snapshot.py`;
- do not connect it to renderer or pipeline until tests prove the adapter is
  deterministic and scope-limited.
