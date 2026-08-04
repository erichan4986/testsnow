# External Producer v2 Evidence Unit Selector Implementation Task

> **For the implementation model:** REQUIRED SUB-SKILLS: use test-driven-development and executing-plans.

**Goal:** Replace the stochastic free-form external claim contract with exact source units, deterministic
target admission/entity/family enrichment, target-only profile routing, and one canonical v3 pack.

**Architecture:** Refresh-time code materializes immutable source units and admits target evidence
deterministically. The LLM may only group mandatory target units and keep/skip optional peer/industry
units by stable ID. Report-time code reads the persisted v3 pack, renders exact evidence text, and never
opens source packets or legacy caches.

**Design:**
`docs/agent_workflow/2026-07-17-external-producer-v2-evidence-unit-selector-design.md`

**Baseline:** `62be6bf`

---

## 1. Execution Rules

1. Execute Batch A -> B -> C -> D in order. Each behavior starts with a failing focused test.
2. Stop after Batch D. Do not run a live LLM, generate reports, edit production config/cache, or perform
   Batch E until the user has reviewed the three-stock live samples.
3. Preserve unrelated dirty-worktree changes. Do not reset, restore, format, or delete files outside this
   task.
4. The intermediate runtime net delta relative to `62be6bf` must stay `<= +650` (user-approved on 2026-07-17).
5. After Batch E deletion/cutover, the final runtime net delta relative to `62be6bf` must be `<= +120`.
6. Crossing a budget, needing a stock-specific rule, or needing free-form LLM prose is a stop condition.
7. No source collection, network access, Chrome/CDP, Xueqiu detail access, annual/broker changes,
   scoring, target price, risk score, technical analysis, recommendation, or KnowledgeSynthesizer prompt
   changes.
8. Do not commit or push.

## 2. Allowed Files Before the Live Gate

Runtime:

- `scripts/utils/curated_external_argument_cards.py`
- `scripts/utils/curated_external_full_body_viewpoint_claims.py`
- `scripts/utils/curated_external_display.py`
- `scripts/previews/curated_external_full_body_viewpoint_preview.py`
- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/evidence_freshness.py`
- `scripts/utils/report_skills/assembly_skills.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/stock_reporter.py`

Focused tests:

- `tests/utils/test_curated_external_argument_cards.py`
- `tests/utils/test_curated_external_full_body_viewpoint_claims.py`
- `tests/utils/test_curated_external_display.py`
- `tests/reporter/test_curated_external_full_body_viewpoint_preview.py`
- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/utils/test_evidence_freshness.py`
- `tests/reporter/test_recommendation_decision.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_stock_reporter_source_intake_config.py`

Notes:

- `docs/agent_workflow/2026-07-17-external-producer-v2-evidence-unit-selector-notes.md`

Batch E may additionally modify/delete only the files listed in section 7.

## 3. Locked Public Contracts

Use these exact versions:

```python
SOURCE_UNIT_SCHEMA = "curated_external_source_unit.v1"
SELECTION_SCHEMA = "curated_external_unit_selection.v1"
ARGUMENT_CARD_SCHEMA = "curated_external_argument_card.v3"
ARGUMENT_PACK_SCHEMA = "curated_external_argument_pack.v3"
SELECTOR_VERSION = "external_unit_selector.v1"
VALIDATOR_VERSION = "external_argument_validator.v3"
```

Required refresh-time APIs:

```python
materialize_external_source_units(
    source_packets: list[dict], *, stock_name: str
) -> list[dict]

enrich_external_evidence_group(
    units: list[dict], *, stock_name: str
) -> dict

partition_external_source_units(
    units: list[dict], *, stock_name: str, baseline_text: str
) -> dict

validate_external_unit_selection(
    source_units: list[dict], selection: dict, *, mandatory_ids: set[str]
) -> dict

build_external_argument_pack(
    *,
    stock_name: str,
    source_packets: list[dict],
    baseline_text: str,
    selections: list[dict],
    selector_version: str = SELECTOR_VERSION,
) -> dict

build_curated_external_argument_pack(
    source_packets: list[dict],
    baseline_text: str,
    *,
    selector,
    stock_name: str,
) -> dict
```

The wrapper materializes units, invokes the selector in per-source batches, validates completeness and
groups, then calls the deterministic pack builder. `selector_incomplete` must be returned as a non-ready
result and must never be written as a ready pack.

`enrich_external_evidence_group()` returns deterministic `entity_scope`, `target_entity`,
`coverage_families`, and `primary_family` from exact unit text only. It has no selector, title, or LLM
inputs.

`partition_external_source_units()` returns `mandatory_target_units`, `optional_peer_units`, and
`rejected_by_reason`; it is the only owner of deterministic target admission and exact baseline-duplicate
rejection.

`validate_external_unit_selection()` validates selector IDs, actions, forbidden fields, mandatory target
decisions, and later grouping invariants. It returns `{"status": "ok" | "invalid", "reason": ...}`.

Required selector factory behavior:

```python
selector(source_units: list[dict]) -> dict
```

It returns `curated_external_unit_selection.v1`, one decision per supplied unit ID. The selector must
not return claim text, quote text, entity scope, family labels, delta prose, prices, scores, risks, or
recommendations.

Required report-time contract:

```python
read_external_argument_pack(path, *, expected_stock_name: str) -> dict
build_curated_external_argument_display(path, *, expected_stock_name: str) -> dict
```

The display output keeps the existing internal key temporarily to minimize downstream churn:
`_curated_external_argument_cards_v2`. Its rows must contain v3 cards and exact evidence-derived
`display_text`; no v2 schema is accepted. Rename of that internal context key is explicitly deferred.

## 4. Batch A: Exact Source Units and Deterministic Enrichment

### A1. RED: source-unit materialization

Add focused tests proving:

- Chinese/English sentence and semicolon boundaries are preserved with terminal punctuation;
- every unit text is an exact continuous substring of canonical `source_packet.content`;
- `unit_id`, `unit_hash`, source ID, ordinal, and source block hash are stable;
- structural labels and empty fragments are omitted;
- an incomplete terminal tail is omitted rather than repaired;
- whitespace is not rewritten after hash/ID calculation.

Run the new tests and record the expected failures before implementation.

### A2. GREEN: one splitter

Implement one source-unit materializer in `curated_external_argument_cards.py`. Do not add a second
splitter in the extractor or preview CLI. Keep source order and use stable hashes derived from exact unit
text and source identity.

### A3. RED/GREEN: deterministic entity and families

Add fixtures for:

- explicit target evidence -> `target`;
- explicit target plus named peer/comparison marker -> `target_with_peer_context`;
- title-only target name -> `peer_or_industry`;
- pronoun-only standalone unit -> `peer_or_industry`;
- adjacent continuation grouped after an explicit target unit -> target-bound group;
- Fudan financial evidence -> includes `financial_quality` regardless of selector output;
- one evidence group may carry multiple canonical families;
- unknown material may map to `other`, which never contributes to richness.

Implement one shared generic family table and deterministic entity resolver. No stock name, stock code,
industry name, sample phrase, LLM topic hint, or source title may change the result.

### A4. RED/GREEN: mandatory target admission and exact baseline duplicate

Add tests proving an explicit-target unit with at least one canonical family is mandatory, has no total
cap, and cannot be removed by a selector decision. Exact normalized baseline containment/hash overlap is
rejected; partial/semantic overlap remains Preview material.

## 5. Batch B: ID-only Selector and v3 Pack

### B1. RED: selector response completeness

Use a fake OpenAI-compatible client. Test:

- at most 24 ordered units from one source per call;
- all source units are traversed across batches;
- response IDs equal request IDs exactly;
- missing, duplicate, and unknown IDs trigger one retry with the same batch;
- a second incomplete response returns `selector_incomplete`;
- a selector `skip` for a mandatory target unit is invalid;
- forbidden extra fields such as `claim`, `topic_family`, `source_quote`, `score`, or `target_price`
  invalidate the response;
- no selector call receives units from two sources.

### B2. GREEN: replace the free-form prompt/parser

Replace `llm_argument_extractor_factory()` with an ID-only selector contract. The prompt may describe
grouping and optional peer/industry selection, but cannot request prose, quotes, taxonomy, target scope,
or delta. Do not preserve the v2 candidate parser behind another name.

### B3. RED/GREEN: grouping validator

Test and implement:

- 1--3 adjacent units, same source, source order;
- non-adjacent, cross-source, oversized, and duplicate-membership groups fail closed;
- mandatory target units remain standalone when not validly grouped;
- grouping changes presentation only, not mandatory admission or coverage union;
- optional peer/industry units respect `keep/skip`.

### B4. RED/GREEN: canonical v3 pack

Replace the v2 pack builder and reader. Assert:

- v3 cards persist exact evidence units, deterministic entity/families/primary family, citations, and
  Preview/display-only safety flags;
- no persisted card contains `claim`, `incremental_delta`, LLM topic/entity fields, target price, score,
  risk score, recommendation, or duplicate free-form display prose;
- citation identity is stable and reused for the same source;
- evidence hash/source identity/dangling refs are validated at read time;
- missing/stale/invalid/incomplete/stock-mismatch states fail closed with no legacy fallback;
- report-time reader never opens source packets, source JSONL, digest, or narrative files.

Delete `_anchors_supported()`, free-form candidate normalization, title-based target fallback, and
`source_quote_not_exact` handling from the selector path as their replacements go green.

## 6. Batch C: Display, Snapshot, and Profile Ownership

### C1. RED/GREEN: exact display projection

Test that display text is the source-order join of stored exact evidence units plus citations. Fixed
Preview framing/disclaimer is allowed; evidence text may not be compacted, paraphrased, or regenerated.
Target cards render first. `peer_or_industry` cards render under a separate
`同业/行业背景（Preview）` block and are never phrased as target facts.

### C2. RED/GREEN: one MaterialRow adapter and citation offsets

Update `deep_analysis_material_snapshot._external_rows()` to consume v3 cards only. Preserve the full
snapshot citation allocator and formal-thin annual + broker + external offset formula. Add regression
tests for complete refs, no missing/unused refs, formal-medium 4.4 reuse, and no renderer pack read.

### C3. RED/GREEN: deterministic target-only profile

For the v3-active path, replace raw card count/LLM topic logic with:

```python
target_cards = [card for card in cards if card["entity_scope"].startswith("target")]
target_coverage = union(card["coverage_families"] for card in target_cards) - {"other"}
external_rich = len(target_coverage) >= 3
```

Required fixtures:

- three peer/industry families -> not rich;
- six target cards in one family -> not rich;
- three target families -> rich;
- Fudan available source units yield financial, technology, and competitive target coverage;
- Zhongji annual + usable broker remains `formal_medium`;
- Black Sesame external-only input does not become a formal profile;
- formal-rich and annual/broker precedence remain unchanged.

### C4. RED/GREEN: downstream display-only consumers

Update freshness and external risk observations to read v3 cards/evidence/citations only when v3 is
active. Missing dates remain unknown. External rows stay excluded from scoring and risk score. Preserve
existing explicit non-viewpoint risk inputs and recommendation identity tests.

## 7. Batch D: Offline Preview and Live-Gate Packet

### D1. RED/GREEN: preview CLI

Change the preview path to write
`/tmp/<stock>-curated-external-argument-pack-v3.json`. It must run the source-unit selector path only,
must not write a digest/narrative object, and must reject output paths inside the repository.

### D2. Offline verification

Run focused tests for every allowed test file, then:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_deep_analysis_renderer.py tests/reporter/test_report_quality.py tests/reporter/test_report_source_boundary.py -q -p no:cacheprovider
bash tools/ci_grep_gates.sh
git diff --check
git diff --numstat 62be6bf -- scripts/utils scripts/previews
```

Stop if any test fails or intermediate runtime net exceeds `+650`.

### D3. Required implementation notes

Write:
`docs/agent_workflow/2026-07-17-external-producer-v2-evidence-unit-selector-notes.md`

Include:

- modified files;
- RED/GREEN sequence and exact focused/downstream results;
- schema/API requirement-test matrix;
- selector retry/completeness tests;
- deterministic target/family/profile fixtures;
- reader isolation and citation-offset results;
- runtime numstat relative to `62be6bf`;
- blocker/warning/deviation;
- exact commands for the three-stock two-run live gate, but do not execute them.

Then stop for independent review and the user-run live gate.

## 8. Gate B2 Live Acceptance

After offline implementation review, run Zhongji Innolight, Fudan Microelectronics, and Black Sesame
Intelligence twice from identical local source packets/baseline. Write only `/tmp` packs.

Approval requires all items in design section 10, including:

- complete selector batches;
- exact evidence hashes/refs;
- no LLM prose/taxonomy/entity fields in persisted packs;
- explicit target evidence in every target group;
- Fudan target coverage includes financial, technology, and competitive families;
- same profile and same target family set in both runs;
- reader/display/lint/focused/downstream/CI green;
- user approval of displayed samples.

Any hallucinated prose is now a schema violation, not a warning. Do not lower profile thresholds or add
sample-specific rules to pass the gate.

## 9. Batch E: Final Cutover and Deletion (Only After User Approval)

Additional allowed modifications/deletions:

- `config/stocks.json`
- `scripts/utils/curated_external_viewpoint_narrative.py` (delete)
- `scripts/previews/curated_external_viewpoint_narrative_preview.py` (delete)
- `scripts/previews/social_viewpoint_digest_preview.py` (delete)
- `tests/utils/test_curated_external_viewpoint_narrative.py` (delete)
- `tests/reporter/test_curated_external_viewpoint_narrative_preview.py` (delete)
- `tests/reporter/test_social_viewpoint_digest_preview.py` (delete)
- `tests/conftest.py`
- `tests/test_scripts_layout.py`
- `tests/test_pytest_marker_contract.py`
- `tests/README.md`
- existing config/plumbing/consumer tests already listed above
- obsolete v1 digest/narrative cache files listed by the deletion ledger, after recording exact paths

Batch E requirements:

1. Switch production config to one canonical argument-pack display key/path.
2. Remove digest/narrative switches, fallback code, payload keys, old composer/preview modules, tests,
   registry entries, and stale cache files.
3. Remove v2 candidate/card/pack compatibility tests and APIs. The v3 reader rejects old packs as stale.
4. Repo grep must show no formal runtime read/import of digest, narrative, v1 claim schema,
   `_curated_external_narrative_paragraphs`, `_curated_external_reasoning_cards`, or
   `_curated_external_topic_groups`.
5. Run the focused suites, the full external/downstream suites, CI gates, `git diff --check`, and one
   no-network report-time fixture using a persisted v3 pack.
6. Final runtime net relative to `62be6bf` must be `<= +120`; otherwise stop and return to design.
7. Do not generate or promote production packs without a separate explicit user instruction.

## 10. Final Stop Conditions

Stop immediately and report instead of improvising if:

- exact source units cannot recover the required Fudan families from the supplied local source packets;
- deterministic family rules require a stock/industry-specific exception;
- a mandatory target unit must be capped or skipped for the tests to pass;
- the selector needs to write prose or taxonomy;
- report-time code needs source packets, legacy caches, or an LLM;
- profile stability differs across identical live inputs;
- intermediate or final runtime budget is exceeded;
- any change outside the allowed scope is required.
