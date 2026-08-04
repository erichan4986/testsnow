# External Topic Narrative Memo Implementation Plan

> **For agentic workers:** execute tasks in order with strict RED/GREEN checkpoints. Do not modify decision paths or canonical pack ownership.

**Goal:** Add an optional producer-time extractive Topic Memo to External Producer v3 and use it for coherent Chapter 4.3 topic paragraphs with deterministic per-topic fallback.

**Architecture:** Core v3 cards remain canonical. A pure narrative module validates exact source-unit prefixes and stores only a versioned optional envelope in the same pack. The report projects validated parts through `MaterialSnapshot`; formal-medium and formal-thin share one narrative-or-row renderer, while profile, synthesis, Chapter 4.4, scoring, target, risk, technical analysis, and recommendation remain card/row based.

**Baseline:** runtime numstat is measured against `cb010646616ba340004d37c0fb92d084c803d7a5` for the runtime files listed below. Batch A hard stop is +220 net lines, Batch B +170, combined +380.

---

## Task 1: Pure Topic Narrative Contract

**Files:**
- Create: `scripts/utils/curated_external_topic_narrative.py`
- Create: `tests/utils/test_curated_external_topic_narrative.py`

- [ ] Write failing tests for deterministic fingerprinting, exact-prefix acceptance, suffix/mid-clause rejection, ellipsis rejection, full evidence-unit coverage, duplicate/missing unit rejection, scope/topic isolation, stable order, relation validation, forbidden keys, partial-group validation, and absence of persisted citation refs/raw response.
- [ ] Run the new test file and confirm failures are caused by the missing module/API.
- [ ] Implement constants and pure helpers:
  - `NARRATIVE_DRAFT_SCHEMA`
  - `NARRATIVE_ENVELOPE_SCHEMA`
  - `NARRATIVE_PRODUCER_VERSION`
  - `external_topic_source_fingerprint(pack)`
  - `build_external_topic_narrative_prompt(pack)`
  - `validate_external_topic_narrative_draft(pack, draft)`
  - `build_external_topic_narrative_envelope(pack, draft_or_none, status_reason="")`
  - `read_external_topic_narratives(pack)`
- [ ] Ensure the module is pure: no OpenAI import, filesystem access, source-cache read, report import, or mutation of core cards.
- [ ] Run the new tests GREEN and refactor duplication without changing behavior.

## Task 2: Producer, Reader, And Preview Integration

**Files:**
- Modify: `scripts/utils/curated_external_argument_cards.py`
- Modify: `scripts/utils/curated_external_full_body_viewpoint_claims.py`
- Modify: `scripts/previews/curated_external_full_body_viewpoint_preview.py`
- Modify: `tests/utils/test_curated_external_argument_cards.py`
- Modify: `tests/utils/test_curated_external_full_body_viewpoint_claims.py`
- Modify: `tests/reporter/test_curated_external_full_body_viewpoint_preview.py`

- [ ] Write failing reader tests proving absent/malformed/stale envelopes cannot poison a ready core pack and the result adds only `topic_narrative_status/topic_narratives`.
- [ ] Write failing producer tests proving multiple groups use one memo HTTP attempt, memo failure writes `unavailable` while core pack stays ready, partial groups persist only validated data, and selector retries/timeouts are unchanged.
- [ ] Write failing preview tests proving the existing model configuration enables the memo, output summary reports narrative status/group count, and core-ready exit code does not depend on memo success.
- [ ] Run focused tests RED.
- [ ] Extend `_request_json(..., timeout_seconds=120)` without changing selector defaults. Add `llm_topic_narrative_composer_factory()` using one attempt and 60 seconds.
- [ ] Add optional `topic_narrative_composer` to refresh-time pack construction; attach the envelope only after a ready core pack exists. Never persist raw responses.
- [ ] Extend `read_external_argument_pack()` with narrative status/data while preserving current core status semantics.
- [ ] Run focused tests GREEN plus existing producer/reader tests.
- [ ] Measure Batch A runtime numstat; stop if net growth exceeds +220.

## Task 3: Display And Material Read-Model Projection

**Files:**
- Modify: `scripts/utils/curated_external_display.py`
- Modify: `scripts/utils/deep_analysis_material_snapshot.py`
- Modify: `tests/utils/test_curated_external_display.py`
- Modify: `tests/utils/test_deep_analysis_material_snapshot.py`

- [ ] Write failing tests proving display exposes narratives only as `_curated_external_topic_narratives` and leaves exact `industry_logic`, synthesis text, cards, taxonomy, item count, and sources unchanged.
- [ ] Write failing snapshot tests for immutable `ExternalNarrativePart`/`ExternalTopicNarrative`, unit-derived refs, shared allocator mapping, target-bucket normalization, hidden-argument filtering, exact visible-unit coverage, and Chapter 4.4 row isolation.
- [ ] Run focused tests RED.
- [ ] Project validated narratives without embedding footnote markers into strings. Keep cards and rows unchanged.
- [ ] Add narrative tuples to `MaterialSnapshot` and `Chapter4Section` with backwards-compatible defaults. Build formal-medium visible refs from rendered rows/narrative parts; keep full snapshot citations available for formal-thin offsets.
- [ ] Run focused tests GREEN and profile/freshness regression tests.

## Task 4: Shared Chapter 4.3 Rendering And Quality Gates

**Files:**
- Modify: `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- Modify: `scripts/utils/report_quality.py`
- Modify: `tests/reporter/test_deep_analysis_renderer.py`
- Modify: `tests/reporter/test_report_quality.py`
- Modify: `tests/reporter/test_report_source_boundary.py` only if an existing boundary assertion needs the unchanged peer banner locked explicitly.

- [ ] Write failing renderer tests for one paragraph per valid topic, deterministic punctuation/connectors, local refs before punctuation, target/peer isolation, unknown-topic order, invalid-topic-only fallback, no display cap, no repeated `同业/行业背景观察：`, formal-medium visible refs, and formal-thin baseline-plus-full-snapshot offsets.
- [ ] Write failing quality tests recognizing the two new lead phrases while still rejecting unframed market share/order confirmation and malformed/missing refs.
- [ ] Run focused tests RED.
- [ ] Extend `_formal_medium_external_variable_map()` to accept optional narratives and select narrative or current rows per scope/topic. Reuse the same call for formal-thin.
- [ ] Preserve the peer boundary banner and exact fallback renderer. Do not change `_select_price_path_rows()` or Chapter 4.4.
- [ ] Run focused tests GREEN, source-boundary tests, and profile regression suites.
- [ ] Measure Batch B and combined runtime numstat; stop at +170/+380.

## Task 5: Verification And Notes

**Files:**
- Create: `docs/agent_workflow/2026-07-21-external-topic-narrative-memo-codex-notes.md`

- [ ] Run focused producer/reader/display/snapshot/renderer/quality/source-boundary suites.
- [ ] Run full `pytest`.
- [ ] Run `bash tools/ci_grep_gates.sh`.
- [ ] Run `git diff --check`.
- [ ] Audit imports to prove report runtime cannot reach OpenAI, source JSONL, or composer functions.
- [ ] Record RED/GREEN evidence, requirement-test matrix, per-file runtime numstat, regressions, deviations, warnings, and whether live acceptance is allowed.
- [ ] Do not run a live LLM or formal report in this implementation session. Those remain the post-code acceptance gate because they require user-visible sample confirmation.

## Stop Conditions

- Core pack status changes because the memo is absent/invalid.
- A memo hides, duplicates, reorders, or reassigns an evidence unit.
- Memo prose enters synthesis/profile/freshness/recommendation inputs.
- Report runtime imports an LLM client or source reader.
- Formal-thin refs are based on filtered narrative refs rather than the full snapshot.
- Target and peer appear in one paragraph.
- Any code path changes scoring, target, risk, technical analysis, recommendation, profile thresholds, Chapter 4.4, or `KnowledgeSynthesizer`.
- Runtime budgets are exceeded.
