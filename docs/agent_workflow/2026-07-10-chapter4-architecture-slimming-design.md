# Chapter 4 Architecture Slimming Design

> **Date**: 2026-07-10
> **Owner**: Codex
> **Status**: Under Claude Review

---

## 1. Goal

Reduce the structural complexity behind Chapter 4 without changing the current
report profiles or their visible meaning. The immediate goal is to make annual
report, broker research, and external observation material pass through one
explicit deep-analysis contract before rendering.

The target is not fewer lines at any cost. The target is clear ownership:

- producers extract and classify source material;
- a Chapter 4 material layer admits rows and resolves citations;
- a view-model selects the rows visible in each profile;
- renderers format already-admitted rows;
- quality gates validate the same contract plus final Markdown hygiene.

This design covers only Chapter 4 deep analysis. It is the first bounded step in
a broader pipeline cleanup.

## 2. Non-Goals

- Do not change evidence-profile thresholds or routing.
- Do not change scoring, target price, risk scoring, technical analysis,
  recommendation labels, or executive-summary inputs.
- Do not change `KnowledgeSynthesizer` prompts or canonical LLM synthesis.
- Do not add a new LLM memo in the first implementation cycle.
- Do not add data sources, network calls, Xueqiu detail crawling, Chrome, or CDP.
- Do not persist `MaterialSnapshot` or add a large sidecar.
- Do not migrate `formal_rich` away from its legacy body in the first cycle.
- Do not delete compatibility helpers until active callers and report samples
  prove they are obsolete.

## 3. Current Context

### 3.1 Pipeline

The single-stock pipeline currently performs source intake, consolidation,
market/technical fetching, synthesis, scoring, chart generation, and assembly.
`SynthesisSkill` is the last large material-building stage before scoring and
report assembly.

```text
source intake / periodic report intake
  -> cross-source consolidation
  -> quote / peer / technical fetching
  -> SynthesisSkill
       -> annual_report_memo
       -> broker digest note refresh
       -> broker_research_memo
       -> external display
       -> evidence profile
       -> canonical synthesis and core facts
  -> scoring
  -> charts
  -> report assembly
```

### 3.2 Hotspots

| Area | Current responsibility mix | Size at design time |
| --- | --- | ---: |
| `synthesis_skills.py` | canonical synthesis, annual/broker memo production, note refresh, profile routing, coverage diagnostics, source policy | 2,054 lines |
| `deep_analysis_renderer.py` | profile branching, source cleanup, row selection, prose projection, citation allocation, Chapter 4 rendering | 1,970 lines |
| `report_quality.py` | Markdown parsing, citation hygiene, profile gates, source-layer gates, evidence depth, peer/fundflow checks | 1,410 lines |
| `broker_research_digest.py` | PDF extraction, heading candidates, ranking, diagnostics, OCR cleanup, card deduplication | 1,260 lines |

The tests protect behavior well, but their size also exposes the missing
boundary: fixtures repeatedly construct profile, memo, citation, and display
payloads directly instead of using one stable Chapter 4 interface.

### 3.3 Existing Good Boundary

`scripts/utils/deep_analysis_material_snapshot.py` already defines a
deep-analysis-only read model. Its invariants are correct:

- it does not mutate `ctx`;
- it does not feed scoring, risk, target price, recommendation, technical, or
  executive-summary paths;
- it normalizes annual, broker, and external rows;
- it resolves local citation ids into one Chapter 4 citation space.

The missing piece is that the renderer still reads the original memo/display
payloads for row selection and prose decisions. The snapshot is currently used
mainly for citation offsets and quality checks, so it is not yet the real
renderer contract.

## 4. Design Options

### Option A: Split Large Files Only

Move helpers into smaller files without changing data flow.

Pros:

- low behavioral risk;
- easy to review.

Cons:

- preserves duplicate source/citation decisions across producer, renderer, and
  gate layers;
- line count moves, but ownership remains unclear.

### Option B: Contract-First Incremental Migration

Extend the existing snapshot into the sole Chapter 4 material contract, add a
profile-specific view-model, then move producers and gates behind that contract
in small batches.

Pros:

- removes the cause of duplication;
- keeps current producers and report prose stable during the first batch;
- creates a safe place for later deterministic or LLM-assisted memo work.

Cons:

- temporarily requires compatibility adapters;
- line count may rise before obsolete helpers can be removed.

### Option C: Rewrite Producers and Add LLM Memo Now

Replace annual/broker/external material production and let an LLM write the new
Chapter 4 body.

Pros:

- potentially improves prose faster.

Cons:

- combines architecture, content quality, citation, and hallucination risk;
- makes regressions difficult to localize;
- violates the current need to slim and stabilize first.

**Decision:** Option B.

## 5. Target Architecture

### 5.1 Components

| Component | Responsibility | Inputs | Outputs |
| --- | --- | --- | --- |
| Annual material producer | Extract formal facts, management explanation, business changes, disclosure boundaries | periodic-report packs and narrative cards | annual material rows |
| Broker digest producer | Extract typed research claims with attribution, diagnostics, and cleaned excerpts | local broker PDFs/manifest/notes | broker material rows |
| External material producer | Normalize curated low-credit observations | existing curated external display | external material rows |
| `Chapter4MaterialSnapshot` | Normalize row identity, source layer, claim status, visibility eligibility, and citations | producer payloads | immutable material snapshot |
| `Chapter4ViewModel` | Apply profile policy and select only visible rows | snapshot + evidence profile | four section models + visible citations |
| Chapter 4 projector | Convert view-model rows into deterministic report prose | view-model | section Markdown |
| Chapter 4 quality contract | Validate source-layer, attribution, citation, and profile rules | snapshot/view-model + Markdown | quality issues |

### 5.2 Material Row Contract

Retain the current `EvidenceRow` fields and add only fields that remove active
renderer inference:

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
    render_role: str = ""
    attribution: str = ""
    source_credit: str = ""
    diagnostics: tuple[tuple[str, str], ...] = ()
```

Field rules:

- `render_role` is semantic, not a final heading. Initial values are
  `business_profile`, `operating_change`, `financial_explanation`,
  `broker_assumption`, `broker_risk`, `external_variable`, and
  `disclosure_boundary`.
- `attribution` is required for visible broker rows and empty for annual rows.
- `source_credit` is one of `official`, `professional`, `external_low_credit`,
  or `deterministic_market_data`.
- `diagnostics` carries producer observations such as heading candidate, score,
  selection reason, cleaner version, or fallback reason. It is for tests/debug
  output and is not rendered by default.
- `display_scope` remains exactly `("deep_analysis",)`.
- external rows remain non-scoring and non-risk-scoring.

No row may be upgraded from low-credit to official/professional by a renderer.

### 5.3 View-Model Contract

```python
@dataclass(frozen=True)
class Chapter4Section:
    section_id: str
    title: str
    rows: tuple[EvidenceRow, ...]
    disclaimer: str = ""


@dataclass(frozen=True)
class Chapter4ViewModel:
    profile: str
    sections: tuple[Chapter4Section, ...]
    citations: dict[int, dict]
    diagnostics: dict[str, object]
```

The view-model owns admission and ordering. The renderer may shorten or join
text, but it may not:

- change `source_layer`, `claim_status`, or source credit;
- invent attribution;
- add a citation not present on the row;
- select rows directly from `ctx`;
- promote external content into an official section.

Visible citations are derived from admitted rows before Markdown rendering.
This replaces the current pattern of merging all citations and deleting unused
ones after rendering.

### 5.4 Profile Policy

#### `formal_medium`

- 4.1 reads official annual rows.
- 4.2 reads attributed broker rows.
- 4.3 reads external rows and carries the Preview/non-scoring disclaimer.
- 4.4 deterministically joins selected official, broker, and external variables
  into conditional price-path statements.

This is the first profile migrated because it exercises all three source
layers and already uses the source-layer-first structure.

#### `formal_thin_external_rich`

- retains its current 4.1-4.3 headings and absence behavior;
- migrates after `formal_medium` is stable;
- continues to omit 4.4 in V1.

#### `formal_rich`

- remains on `_legacy_deep_analysis_body()` during this design's implementation;
- may receive a separate migration design only after the new contract has passed
  both target-stock samples.

### 5.5 Pipeline Ownership

The migration introduces a dedicated orchestration stage after canonical
synthesis has produced its current outputs:

```text
SynthesisSkill
  -> Chapter4MaterialSkill
       -> build/refresh source-layer materials through producer adapters
       -> build Chapter4MaterialSnapshot
       -> build Chapter4ViewModel
  -> scoring (unchanged inputs)
  -> report assembly
```

The first batch may have `Chapter4MaterialSkill` adapt existing
`annual_report_memo`, `broker_research_memo`, and `deep_analysis_display` fields.
Later batches move annual/broker material construction and broker-note refresh
out of `SynthesisSkill` without changing the output schema.

The new skill may set only:

- `chapter4_material_snapshot`;
- `chapter4_view_model`;
- Chapter 4 diagnostics.

It must not write canonical synthesis, core facts, scoring, risk, target price,
recommendation, technical, or executive-summary fields.

## 6. Data Flow

```text
local source material
  -> existing annual / broker / external producers
  -> producer payload compatibility adapters
  -> Chapter4MaterialSnapshot
       - normalize source layer and claim status
       - resolve citation ids once
       - preserve producer diagnostics
  -> Chapter4ViewModel
       - apply profile policy
       - select and order visible rows
       - derive visible citations
  -> Chapter 4 projector
       - deterministic prose only
  -> Markdown citation/source-boundary hygiene
```

## 7. Migration Plan

### Batch A: Contract Completion, No Visible Prose Change

- Extend `EvidenceRow` with render role, attribution, source credit, and
  diagnostics.
- Add `build_chapter4_view_model(snapshot, profile)`.
- Build the view-model in tests and optionally in `ctx`, but leave renderer
  output unchanged.
- Add fixture builders so renderer and quality tests stop hand-assembling
  incompatible payload shapes.

Stop if existing producer data cannot express a visible row without parsing
rendered prose.

### Batch B: Migrate `formal_medium`

- Make `formal_medium` render only from `Chapter4ViewModel`.
- Keep headings and visible content semantically equivalent to the current
  approved reports.
- Move citation admission and source-layer checks out of renderer helpers.
- Preserve `formal_rich` and `formal_thin_external_rich` paths.

### Batch C: Migrate `formal_thin_external_rich`

- Reuse official/broker/external section models.
- Preserve broker-absent fallback and three-section layout.
- Keep external rows Preview-only and fully cited.

### Batch D: Extract Producer Ownership

- Move annual memo construction from `SynthesisSkill` into an annual material
  producer module.
- Move broker note refresh/memo construction into a broker material producer or
  dedicated report skill.
- Keep note persistence optional and explicitly configured.
- Reuse existing `curated_external_display.py` for external input.
- Leave canonical LLM synthesis and evidence-profile routing in
  `SynthesisSkill` until a separate routing design exists.

### Batch E: Quality-Gate Split

- Keep `check_report_file`, `check_report_text`, `QualityIssue`, and
  `QualityResult` in `report_quality.py`.
- Move Chapter 4 snapshot/view-model rules to
  `report_quality_chapter4.py`.
- Keep final Markdown gates for malformed/missing/unused citations, headings,
  and disclaimers.
- Do not make file-mode quality checks depend on an in-memory snapshot.

### Batch F: Deletion Audit

Delete only helpers with no active callers after both migrated profiles pass:

- renderer-local citation offset/merge/visible-only helpers superseded by the
  view-model citation registry;
- duplicated annual row grouping and broker attribution inference superseded by
  producer row metadata;
- obsolete formal-thin verification checklist helpers;
- visible reasoning-card/addendum compatibility paths no longer selected by any
  profile.

Do not delete legacy helpers still used by `formal_rich`.

### Batch G: Producer Quality V2, Separate Scope

After the architecture is stable, improve annual and broker material quality:

- broader but typed annual narrative coverage;
- better broker section candidate ranking and OCR diagnostics;
- deterministic investment-note summaries from admitted rows.

Only if deterministic summaries remain unreadable should a bounded LLM memo be
designed. Such a memo must consume admitted rows, return row refs, and pass
numeric/citation validation. It is not part of this design's first execution.

## 8. Error Handling And Fallbacks

- A visible annual/broker/external row without resolved citations is excluded
  and recorded in diagnostics; it is not rendered with `unknown` evidence.
- A broker row without attribution is excluded from 4.2 or rendered only as an
  explicitly unattributed research excerpt warning in debug output, never as a
  confirmed fact.
- An external row marked scoring/risk eligible is a hard contract error.
- An external row selected for 4.1 is a hard contract error.
- Missing broker material keeps the current short 4.2 absence statement.
- Missing annual material uses the current deterministic boundary/fallback;
  it does not fall back to legacy mixed-source synthesis.
- If the view-model cannot be built, the migrated profile must fail closed to a
  concise material-unavailable section and emit diagnostics. It must not silently
  use a different profile layout.
- Broker note refresh failure is non-fatal when current valid notes exist, but
  diagnostics must expose stale/cleaner-version status.

## 9. Failure Modes And Tests

| Failure mode | User/runtime symptom | Test or check |
| --- | --- | --- |
| Renderer still reads raw memo rows | source policy differs between test and report | monkeypatch raw payload after view-model build; rendered output remains unchanged |
| Citation collision across producers | wrong footnote or duplicate source id | annual/broker/external local ref `1` maps to three valid global refs |
| Snapshot includes rows that view-model drops | unused global references | visible citation set equals refs on admitted rows |
| Broker attribution is lost | research forecast reads as company fact | broker row without attribution is rejected; attributed row renders with institution label |
| External row leaks into 4.1 | low-credit claim appears official | source-layer contract gate fails |
| External row affects scoring/risk | low-credit observation changes recommendation | snapshot invariant test and forbidden-ctx-write test fail |
| `formal_rich` is accidentally migrated | legacy report headings/content change | formal-rich golden/structural test |
| Thin broker-absent path renumbers sections | 4.2 disappears or 4.3 becomes 4.2 | formal-thin structural test |
| OCR/stale broker note is selected | broken excerpts return to 4.2 | cleaner-version and selection-diagnostics tests |
| Markdown has malformed/missing/unused refs | visible claim cannot be traced | existing citation hygiene gates |
| File-mode quality gate assumes in-memory state | standalone checker differs from CLI | `check_report_file` remains Markdown/sidecar-only test |
| Compatibility helper deleted too early | legacy profile loses citations | `rg` caller audit plus formal-rich regression test |

## 10. Files Expected To Change

The implementation plan should use these boundaries; not every file changes in
every batch.

| File | Change type | Reason |
| --- | --- | --- |
| `scripts/utils/deep_analysis_material_snapshot.py` | modify/rename only if needed | complete material row contract |
| `scripts/utils/chapter4_view_model.py` | create | profile admission, ordering, visible citations |
| `scripts/utils/report_skills/chapter4_material_skill.py` | create | explicit Chapter 4 orchestration boundary |
| `scripts/utils/report_skills/__init__.py` | modify in later batch | insert dedicated stage without changing other order |
| `scripts/utils/reporter/sections/deep_analysis_renderer.py` | reduce/delegate | retain header/core facts/profile routing; delegate migrated bodies |
| `scripts/utils/reporter/sections/chapter4_renderer.py` | create in Batch B | deterministic projection from view-model |
| `scripts/utils/report_quality.py` | reduce/delegate in Batch E | preserve public quality API |
| `scripts/utils/report_quality_chapter4.py` | create in Batch E | snapshot/view-model contract checks |
| `scripts/utils/report_skills/synthesis_skills.py` | reduce in Batch D | remove Chapter 4 producer orchestration only after adapters pass |
| `tests/utils/test_deep_analysis_material_snapshot.py` | expand | material contract tests |
| `tests/utils/test_chapter4_view_model.py` | create | profile and citation admission tests |
| `tests/reporter/test_deep_analysis_renderer.py` | adapt | renderer regression and delegation tests |
| `tests/reporter/test_report_quality.py` | adapt | public API and Chapter 4 gate integration |
| `tests/reporter/test_synthesis_skills.py` | reduce fixtures over time | ensure canonical synthesis behavior is unchanged |

## 11. Files And Areas That Must Not Change

| File/area | Reason |
| --- | --- |
| `scripts/utils/reporter/scoring_engine.py` | scoring is outside Chapter 4 projection |
| `scripts/utils/reporter/technical_*.py` | technical algorithms are out of scope |
| `scripts/utils/reporter/price_target.py` | target-price behavior must not change |
| recommendation/risk decision paths | low-credit material must not expand influence |
| `scripts/utils/knowledge_synthesizer.py` prompts | LLM synthesis changes require a separate Level 3 design and sample approval |
| source collection and Xueqiu/Chrome/CDP logic | no data-source or account-risk changes |
| `xueqiu_monitor_v2.py` and stock entry scripts | entry compatibility is required |
| `formal_rich` legacy rendering body | explicitly deferred |

## 12. Acceptance Gates

### Contract Tests

- annual, broker, and external local citation ids resolve without collision;
- every admitted visible row has final citation refs and source ref ids;
- broker rows require attribution;
- external rows are Preview-only, non-scoring, and non-risk-scoring;
- view-model construction is deterministic and does not mutate `ctx`;
- forbidden fields are unchanged before and after Chapter 4 material building.

### Focused Tests

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_deep_analysis_material_snapshot.py \
  tests/utils/test_chapter4_view_model.py \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_report_quality.py \
  tests/reporter/test_report_source_boundary.py \
  -q -p no:cacheprovider

bash tools/ci_grep_gates.sh
git diff --check
```

### Report Acceptance

Run only after a migration batch changes runtime rendering:

- `中际旭创`: remains `formal_medium`, keeps source-layer-first 4.1-4.4,
  broker attribution, clean citations, and no external leakage into 4.1.
- `复旦微电`: remains `formal_thin_external_rich`, keeps 4.1-4.3, complete
  external citations, and no forced 4.4.
- `formal_rich` fixture/sample retains legacy headings and citation behavior.

For each report:

- no missing, unused, malformed, or `unknown` citation metadata;
- no low-credit source in official sections;
- Preview disclaimers remain explicit;
- quality and source-boundary checks pass;
- prose warnings may remain only if they do not indicate truncation, attribution
  loss, or source-layer leakage.

### Complexity Gates

- Batch A runtime growth should stay under 220 net lines, excluding tests.
- No new module should combine producer extraction, profile routing, rendering,
  and quality checks.
- Every new public function must have one owner and one contract-level test.
- A batch may not delete more code than its tests prove unreachable.

## 13. Stop Conditions

Stop and re-plan if implementation requires:

- changing profile routing thresholds;
- changing scoring, target price, risk, technical, recommendation, or executive
  summary semantics;
- changing `KnowledgeSynthesizer` prompts or canonical synthesis behavior;
- adding network fetches or new source types;
- persisting a new MaterialSnapshot sidecar;
- parsing final Markdown to reconstruct source-layer metadata inside the new
  view-model;
- migrating `formal_rich` in the same batch;
- deleting producer or citation compatibility paths before both target profiles
  pass report acceptance.

## 14. Deletion Candidates

### Eligible Only After Migration

- `_max_snapshot_ref`, `_merged_citations`, `_offset_citations`, and
  `_visible_citations_only` in the renderer, if the view-model owns one final
  visible citation registry.
- annual row grouping/selection helpers that become producer `render_role`
  metadata.
- broker attribution inference that becomes producer `attribution` metadata.
- formal-thin checklist and external addendum paths with no active profile.

### Keep For Now

- annual/broker memo schemas and compatibility adapters;
- broker digest diagnostics and OCR cleaner;
- curated external source identity/deduplication utilities;
- MaterialSnapshot quality gates;
- all `formal_rich` compatibility rendering helpers.

### Risky To Delete

- citation identity helpers still used by legacy 4.4;
- internal claim/source metadata consumed by source-boundary gates;
- note loader preference logic that prevents stale legacy notes from winning;
- canonical synthesis provenance enrichment.

## 15. Open Decisions

| Decision | Resolution |
| --- | --- |
| Should the first batch add an LLM memo? | No. Stabilize the material contract first. |
| Should all report profiles migrate together? | No. `formal_medium` first, then `formal_thin_external_rich`; `formal_rich` deferred. |
| Should the snapshot be persisted? | No. Keep it in memory and deep-analysis-only. |
| Should file-mode quality load an in-memory snapshot? | No. File mode remains Markdown/sidecar-only. |
| Should producer diagnostics be visible in the report? | No by default; expose in debug payload/tests/notes. |
| Should broker sections expand in count? | No. Broaden typed category coverage and improve candidate quality instead. |

## 16. Claude Review Log

### Round 1 Feedback

- Not yet received; Round 1 review task is defined in the companion review file.

### Design Delta After Round 1

Accepted:

- Not applicable until Round 1 feedback is received.

Rejected:

- Not applicable until Round 1 feedback is received.

Deferred:

- Not applicable until Round 1 feedback is received.

R2 Required:

- Undecided. Trigger only for a blocker, unresolved must-fix, or high-risk
  design change.

### Final Implementation Readiness

- Not ready for implementation until Round 1 design review is resolved.
