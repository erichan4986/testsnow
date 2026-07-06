# Deep Analysis MaterialSnapshot V1 Design

Date: 2026-07-06

## Context

Recent 4.1-4.4 iterations improved source separation, but the implementation now
has repeated citation and source-boundary logic across:

- `annual_report_memo`
- `broker_research_memo`
- `deep_analysis_display`
- `fundflow_material_pack`
- `peer_comparison_material`
- `DeepAnalysisRenderer` citation offset / merge helpers
- `report_quality.py` and `report_source_boundary.py` gates

The desired end state is a unified evidence contract. V1 must be conservative:
it should normalize the material already present in `ctx` for deep-analysis
rendering and gates, not expand where material can flow.

## Hard Invariants

1. `MaterialSnapshot` V1 is a deep-analysis read-model only.
2. It serves only 4.1-4.4 deep analysis.
3. It must not affect executive summary, scoring, target price, risk scoring,
   recommendation labels, or technical analysis.
4. It must not write or mutate `synthesis`, `synthesis_display`, `core_facts`,
   `pillar`, `recommendation_decision`, `structured_risk_signals`, or
   `price_target`.
5. It must not call LLMs, fetch network data, write files, or mutate Knowledge.
6. It must not replace the existing producers in V1:
   `annual_report_memo`, `broker_research_memo`, `deep_analysis_display`,
   `fundflow_material_pack`, and `peer_comparison_material` remain source
   producers.
7. It may normalize citation refs, source-layer flags, display scope, and
   scoring/risk eligibility for 4.1-4.4 rendering and gates.
8. All low-credit or external rows must remain display-only and non-scoring.
9. Snapshot construction must be deterministic from `ctx`.
10. `display_scope` must be exactly `("deep_analysis",)` in V1.

Explicitly forbidden V1 display scopes:

- `("executive_summary",)`
- `("risk",)`
- `("scoring",)`
- `("price_target",)`

## Known Boundary Risk

`ExecutiveSummaryRenderer` currently reads:

```python
ctx.get("synthesis_display") or ctx.get("synthesis")
```

That means display-only synthesis can already influence the executive summary.
`MaterialSnapshot` V1 must not make this path broader:

- it must not write `synthesis_display`;
- it must not change the meaning of `synthesis_display`;
- any future decision about whether the executive summary should read
  display-only material needs a separate design.

## Proposed Module

Use a narrow name to prevent accidental reuse outside chapter 4:

```text
scripts/utils/deep_analysis_material_snapshot.py
```

## EvidenceRow Contract

```python
@dataclass(frozen=True)
class EvidenceRow:
    row_id: str
    text: str
    source_layer: str
    claim_status: str
    citation_refs: tuple[int, ...]
    source_ref_ids: tuple[str, ...]
    display_scope: tuple[str, ...]
    scoring_eligible: bool
    risk_score_eligible: bool
    section_hint: str = ""
```

Field notes:

- `row_id`: stable local row id for renderer/gate diagnostics.
- `text`: visible or renderable claim text.
- `source_layer`: one of annual, broker, external, fundflow, peer, baseline.
- `claim_status`: formal fact, professional analysis, external observation,
  deterministic data, or equivalent existing status.
- `citation_refs`: final or locally resolvable report citation numbers.
- `source_ref_ids`: internal source ids for audit.
- `display_scope`: exactly `("deep_analysis",)` in V1.
- `scoring_eligible` and `risk_score_eligible`: copied from the source layer,
  never inferred upward.
- `section_hint`: optional renderer/gate hint such as `4.1`, `4.2`, `4.3`,
  `annual_memo`, `broker_memo`, or `external_map`.

## MaterialSnapshot Contract

```python
@dataclass(frozen=True)
class MaterialSnapshot:
    schema: str
    rows: tuple[EvidenceRow, ...]
    citations: dict[int, dict]
    diagnostics: dict
```

V1 must not include:

- ranking;
- LLM prompt material;
- synthesis text;
- scoring inputs;
- recommendation inputs;
- target-price inputs.

## Producer Map

| Producer | Current ctx field | Key fields | Current consumers | Snapshot V1 |
| --- | --- | --- | --- | --- |
| Annual memo | `annual_report_memo` | `sections.confirmed`, `sections.annual_report_explanation`, `sections.undisclosed`, `citations` | deep renderer | yes |
| Broker memo | `broker_research_memo` | `sections`, `forecast_ranges`, `risks`, `citations` | deep renderer | yes |
| External display | `deep_analysis_display` | `_curated_external_reasoning_cards`, `_curated_external_topic_groups`, `citations` | deep renderer, quality gate, source boundary | yes |
| Fundflow pack | `fundflow_material_pack` | `rows`, `summary` | synthesis, sidecar, quality | read-only diagnostics first |
| Peer material | `peer_comparison_material` | `rows`, `source_refs` | executive-summary sanitizer, sidecar, quality | read-only diagnostics first |

V1 replacement priority:

1. annual memo rows;
2. broker memo rows;
3. external display rows;
4. fundflow and peer material as diagnostics only.

## S0 Audit

S0 is read-only. It must produce a contract map and deletion candidate list.

Audit table columns:

- producer;
- current `ctx` field;
- current core fields;
- current consumers;
- whether it enters Snapshot V1;
- helpers that only perform citation offset, refs checks, or source-boundary
  duplication.

Helpers to inspect first:

- `_offset_citations`
- `_merged_citations`
- `_used_formal_thin_external_citations`
- `annual_citation_offset`
- `broker_citation_offset`
- curated external citation ref mapping helpers

S0 stop condition:

- If any helper also serves executive summary, scoring, risk, target price, or
  Knowledge persistence, do not mark it for deletion.

## S1 Adapter

Add only:

```python
def build_deep_analysis_material_snapshot(ctx: Mapping[str, Any]) -> MaterialSnapshot:
    """Project existing chapter-4 material fields into a deterministic snapshot."""
```

Allowed reads:

- `ctx["annual_report_memo"]`
- `ctx["broker_research_memo"]`
- `ctx["deep_analysis_display"]`
- `ctx["fundflow_material_pack"]`
- `ctx["peer_comparison_material"]`
- `ctx["deep_analysis_evidence_profile"]`

Forbidden writes:

- `ctx["synthesis"]`
- `ctx["synthesis_display"]`
- `ctx["core_facts"]`
- `ctx["pillar"]`
- `ctx["recommendation_decision"]`
- `ctx["structured_risk_signals"]`
- `ctx["price_target"]`

Pipeline connection:

- S1 may set `ctx["deep_analysis_material_snapshot"]` only after tests prove the
  adapter is deterministic and scope-limited.
- It may also remain test-only until S2.

## S2 Renderer Integration

S2 does not change report prose.

Only replace mechanical citation handling for formal-thin annual, broker, and
external rows:

- citation offset;
- used refs collection;
- citation merge.

Do not change:

- profile routing;
- formal-rich headings;
- formal-thin headings;
- external map wording;
- annual/broker memo body text;
- 4.3 fundflow/catalyst logic.

Expected result:

- Markdown body should be text-equivalent except for internal citation plumbing.
- If citation numbering changes, tests must show every visible `[^n]` resolves.

## S3 Quality Gates

Add optional snapshot support:

```python
check_report_text(
    text,
    path="<memory>",
    deep_analysis_material_snapshot=None,
)
```

First snapshot-based gates:

- unresolved citation refs;
- non-deep-analysis display scope;
- `scoring_eligible` or `risk_score_eligible` inconsistent with source layer;
- low-credit external row lacks display-only framing.

Do not replace all Markdown regex gates in S3. Keep existing checks for:

- required subsection structure;
- financial direction contradiction;
- industry-chain relevance;
- peer comparison support;
- fundflow claims;
- prose quality and source-boundary region scanning.

## S4 Deletion

Delete only after all of the following hold:

1. `rg "_offset_citations|_merged_citations|_used_formal_thin_external_citations|annual_citation_offset|broker_citation_offset"`
   shows only compatibility shims or no active dependency.
2. Snapshot tests cover annual, broker, and external rows with citation refs.
3. Renderer snapshot output passes formal-thin and formal-rich tests.
4. `report_quality.py` and `report_source_boundary.py` pass for formal-thin
   and formal-rich fixtures.
5. Smoke reports pass:
   - Fudan Microelectronics formal-thin: no duplicate/lost citations, external
     viewpoints stay out of formal fact sections.
   - Zhongji Innolight formal-rich/formal-medium: 4.1-4.3 do not degrade.

## Tests

S1 adapter tests:

- annual memo row becomes `EvidenceRow` with `display_scope=("deep_analysis",)`;
- broker `forecast_ranges` and `risks` become rows with citation refs and
  non-scoring flags;
- external display rows remain display-only and non-scoring;
- fundflow and peer material appear only in diagnostics in V1;
- adapter does not write to forbidden `ctx` fields.

S2 renderer tests:

- formal-thin annual/broker/external citations all resolve;
- formal-thin output has no `4.4` when layout uses merged external map;
- formal-rich headings are unchanged;
- formal-medium keeps legacy headings.

S3 gate tests:

- unresolved snapshot citation ref is an error;
- external row with non-deep display scope is an error;
- low-credit row marked scoring/risk eligible is an error;
- framed external map row passes.

## Stop Conditions

Stop and re-plan if any batch requires:

- changing `KnowledgeSynthesizer` prompts;
- changing scoring, risk scoring, target-price, or recommendation algorithms;
- changing executive-summary input semantics;
- introducing network fetches or new data sources;
- replacing annual/broker/external producers instead of adapting them;
- broad deletion before snapshot tests are green.

## Recommended Next Step

Start with S0 audit only. Do not implement the adapter until the audit shows
which helpers are truly duplicated and which ones still protect other modules.
