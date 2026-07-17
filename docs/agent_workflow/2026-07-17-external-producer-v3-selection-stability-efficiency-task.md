# External Producer v3 Selection Stability and Efficiency Implementation Task

> **For the implementation model:** REQUIRED SUB-SKILLS: use test-driven-development and executing-plans.

**Goal:** Make target coverage deterministic and reduce live selector latency by removing target material
from the LLM path and admitting only distinct high-value peer/industry units before the sole selector.

**Architecture:** One shared preparation helper creates deterministic target bundles and the optional-peer
selector pool. Target cards bypass the LLM; peer cards retain the existing ID-only selector. All coverage is
the ordered union of precomputed source-unit families, and all evidence remains exact and source ordered.

**Design:**
`docs/agent_workflow/2026-07-17-external-producer-v3-selection-stability-efficiency-design.md`

**Review:**
`docs/agent_workflow/2026-07-17-external-producer-v3-selection-stability-efficiency-claude-review-round1-notes.md`

---

## 1. Execution Rules

1. Execute Task 1 through Task 5 in order. Add each behavior as a failing test before runtime changes.
2. Preserve the dirty worktree. Do not restore, reset, delete, reformat, or overwrite unrelated changes.
3. Only modify files in section 2.
4. Replace the mixed target/peer path; do not retain it behind a compatibility switch.
5. Do not introduce a second selector, stock/entity dictionary, fuzzy matcher, embedding, semantic repair,
   final card/source cap, or report-time source/LLM read.
6. Do not access the network, call a live model, generate reports, or modify config/cache/data/knowledge.
7. Runtime net growth for this batch relative to the starting worktree must remain `<= +140`. Stop before
   further edits if the limit is exceeded.
8. Do not commit or push. Write implementation notes and stop for independent review.

## 2. Allowed Files

Runtime:

- `scripts/utils/curated_external_argument_cards.py`
- `scripts/utils/curated_external_full_body_viewpoint_claims.py`

Tests:

- `tests/utils/test_curated_external_argument_cards.py`
- `tests/utils/test_curated_external_full_body_viewpoint_claims.py`
- `tests/utils/test_curated_external_display.py` only for selector-version staleness
- `tests/reporter/test_synthesis_skills.py` only for target-only profile regression

Notes:

- `docs/agent_workflow/2026-07-17-external-producer-v3-selection-stability-efficiency-notes.md`

Forbidden modules include renderer/snapshot, report quality, scoring, target price, risk, technical,
recommendation, `KnowledgeSynthesizer`, preview CLI, stock config, and production assembly.

## 3. Locked Interfaces

Add this sole preparation owner in `curated_external_argument_cards.py`:

```python
def prepare_external_argument_material(
    units: list[dict], *, stock_name: str, baseline_text: str,
) -> dict:
    """Return deterministic target bundles, eligible peer units, and admission diagnostics."""
```

Its exact keys are those in design section 5. Use dictionaries, not a new dataclass/schema.

Update the canonical builder without creating a parallel builder:

```python
def build_external_argument_pack(
    *,
    stock_name: str,
    source_packets: list[dict],
    baseline_text: str,
    selections: list[dict],
    selector_version: str = SELECTOR_VERSION,
    prepared_material: dict | None = None,
    selector_request_count: int = 0,
) -> dict:
    ...
```

Direct callers may omit `prepared_material`; the builder then calls the same preparation helper. The refresh
wrapper passes its prepared result so admission is not recomputed or reimplemented.

Keep these schemas:

```python
SOURCE_UNIT_SCHEMA = "curated_external_source_unit.v1"
SELECTION_SCHEMA = "curated_external_unit_selection.v1"
ARGUMENT_CARD_V3_SCHEMA = "curated_external_argument_card.v3"
ARGUMENT_PACK_V3_SCHEMA = "curated_external_argument_pack.v3"
```

Bump only:

```python
SELECTOR_VERSION = "external_unit_selector.v2"
```

Do not add compatibility for `external_unit_selector.v1`; old Gate packs must read as stale.

## 4. Task 1: RED - Source Order and Coverage Ownership

Add focused tests in `test_curated_external_argument_cards.py`:

1. `_selected_unit_groups()` receives target-first pool indexes for source ordinals `7, 5, 6`; a valid group
   persists evidence ordinals `[5, 6, 7]`.
2. A handcrafted group contains one `target_bound=True` financial unit and one peer capacity unit. Enrichment
   returns only the target unit's family for target coverage.
3. Changing peer grouping around the same target unit does not alter the target-family union.
4. `_build_v3_card()` stores unit-family union rather than rescanning joined text.

Run only these new tests and record RED output in notes.

Implement the minimal GREEN change:

- add one fixed-priority ordered family-union helper;
- make `enrich_external_evidence_group()` use precomputed unit families;
- if any unit is `target_bound`, use only target-bound units for coverage;
- persist each group in `(source_id, source_ordinal)` order;
- do not weaken reader adjacency, source identity, hash, or citation checks.

Run the new tests, then the complete argument-card test file.

## 5. Task 2: RED - Shared Preparation and Fail-Closed Continuations

Add tests for `prepare_external_argument_material()`:

1. Explicit target units are retained without a selector and without a total cap.
2. Immediately adjacent `公司...` and `该产品...` units with canonical families attach in source order, up to
   the existing three-unit card limit.
3. `其竞争对手英伟达已发布新品。` does not attach.
4. `双方将共同推进合作。` does not attach.
5. A continuation containing any locked relation-switch marker does not attach.
6. A new explicit target unit starts a new bundle rather than being consumed as continuation.
7. Target bundle `coverage_families` equals the fixed-priority union of its units.
8. Diagnostics count mandatory units, bundles, rejected continuations, and truncated continuations exactly.

The continuation implementation must use only the closed syntax in design section 4.1. Do not broaden
`_mentioned_entities()`, add company suffixes, or maintain an entity dictionary.

Refactor existing partition logic into the shared preparation path. A low-level partition helper may remain
only when it is called by `prepare_external_argument_material()` and is not separately called by either
builder. Run the focused tests and the complete argument-card test file.

## 6. Task 3: RED - Optional Peer Admission, Dedupe, and No Cap

Add exact fixtures proving:

1. `行业竞争格局加剧。` is low signal and never reaches the selector.
2. A named peer or industry subject plus a numeric/model/action anchor reaches the selector unchanged.
3. Generic rules do not contain any sample stock name, stock code, or sample-specific product string.
4. Global exact normalized duplicates keep the first packet in existing input order.
5. Strict containment duplicates are removed only within the same source.
6. Distinct high-value units from different sources are all retained.
7. More than 24 distinct eligible units produce multiple selector batches; none is removed to satisfy a
   count.
8. Diagnostics set `optional_peer_raw_count`, `optional_peer_eligible_count`,
   `optional_peer_low_signal_count`, and `optional_peer_duplicate_count` to exact expected values.

Implement structural peer admission and dedupe inside the shared preparation helper. Reuse the existing
family table and source order. Do not add a final cap or a second recovery pass.

## 7. Task 4: RED - Target Bypass, Retry Accounting, and Version Refresh

Update `test_curated_external_full_body_viewpoint_claims.py`:

1. Target-only material builds a ready pack when a fake selector raises if called; selector calls equal zero.
2. Mixed material sends only eligible optional peer units to the selector.
3. A first incomplete peer response and a second complete response produce a ready pack with
   `diagnostics["selector_request_count"] == 2`.
4. Two incomplete responses fail closed as `selector_incomplete` with no partial ready cards.
5. `selector_batch_count` equals the number of eligible peer batches, including zero.
6. Deterministic target cards precede peer cards and target/peer selector groups cannot mix.
7. A v1-selector pack is stale after the version bump.

Refactor `build_curated_external_argument_pack()` to:

- materialize once and call `prepare_external_argument_material()` once;
- invoke the selector only for prepared optional peer batches;
- increment `selector_request_count` for every selector invocation, including completeness retries;
- pass prepared material, valid peer selections, and the request count to the canonical builder.

Refactor `build_external_argument_pack()` to:

- build deterministic target cards from `target_bundles` without selector decisions;
- require selection batch count to match optional-peer batches only;
- validate peer selection with an empty `mandatory_ids` set;
- group peer units only;
- combine target cards then peer cards;
- persist all diagnostics from the preparation helper plus selector/card counts.

Delete the old mixed `mandatory + optional` pool, target mandatory validation inside selector batches, and
pool-index group ordering rather than layering new branches around them.

## 8. Task 5: Regression and Budget Verification

Run focused suites:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_curated_external_argument_cards.py \
  tests/utils/test_curated_external_full_body_viewpoint_claims.py \
  tests/utils/test_curated_external_display.py \
  tests/reporter/test_synthesis_skills.py \
  -q -p no:cacheprovider
```

Run related external/Chapter 4 suites already used by the branch, then:

```text
bash tools/ci_grep_gates.sh
git diff --check
```

Measure runtime numstat before and after this batch using the starting worktree snapshot recorded in notes.
Stop if net runtime growth exceeds `+140`.

Do not run the six live model commands or generate reports. The user will run Gate B2 only after independent
code review.

## 9. Required Notes

Write:

`docs/agent_workflow/2026-07-17-external-producer-v3-selection-stability-efficiency-notes.md`

Include:

- modified files;
- each RED and GREEN command/result;
- requirement-test matrix;
- shared helper return example;
- target bypass and continuation negative results;
- optional-peer admission/dedupe counts;
- selector batch/request diagnostics;
- focused/related/CI/diff-check results;
- before/after runtime numstat;
- blocker, warning, deviation;
- `Gate B2 rerun allowed: yes|no`.

Stop after writing notes and wait for independent read-only review.
