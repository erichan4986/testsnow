# External Producer v3 Selection Stability and Efficiency Design

## 1. Status

- Status: proposed for Round 1 read-only review.
- Gate B2 remains blocked.
- This design replaces mixed target/peer LLM grouping; it does not add a second selector.
- No production config/cache/report cutover is allowed in this batch.

## 2. Why Gate B2 Failed

The live gate exposed one implementation bug and one ownership flaw:

1. `_selected_unit_groups()` persisted grouped members in target-first pool order instead of immutable
   source order, so five of six packs failed reader validation with `invalid_evidence_group`.
2. Target and peer units were sent through the same stochastic grouping path. Once a peer unit was grouped
   with an explicit target unit, its families were counted as target coverage. Grouping therefore changed
   profile routing, contrary to the design contract.

The same mixed pool also caused poor runtime. `--max-sources 0` sent nearly every broad family match to the
LLM, including generic industry sentences. Zhongji required 27 sequential requests and retained 96--123
peer cards. Increasing batch size would trade latency for more incomplete responses without fixing
admission or coverage ownership.

## 3. Considered Approaches

### A. Order and coverage hotfix only

Sort group members by `source_ordinal` and ignore peer-unit families on target cards. This fixes pack
validity and profile drift, but leaves 20+ sequential calls and a noisy peer block. Rejected as incomplete.

### B. Larger batches or a stricter prompt

This may reduce request count, but larger responses already caused `selector_incomplete`, and prompt wording
cannot make a broad transport pool high-value. Rejected.

### C. Deterministic target bundles plus a filtered peer selector

Target facts bypass LLM admission. Strict adjacent continuations are attached deterministically. Only
high-value, deduplicated peer/industry units reach the existing selector. This is the selected approach.

## 4. Locked Ownership

### 4.1 Target material

An explicit target unit remains mandatory when it contains the configured stock name, has at least one
canonical family, and is not an exact baseline duplicate.

Mandatory target units are never sent to the LLM. They are retained without a total cap. A target bundle is
built deterministically in source order:

- start with one explicit mandatory target unit;
- attach at most two immediately adjacent units from the same source;
- after an optional `同时/此外/其中` discourse prefix, an attached unit must begin with the closed subject
  allowlist `公司`, `本公司`, `该公司`, `该产品`, `上述产品`, or `相关产品`;
- ambiguous anaphora such as `其` and multi-entity subjects such as `双方` are never attached;
- an attached unit must have canonical coverage and must not contain an entity-relation switch such as
  `竞争对手`, `同行`, `同业`, `友商`, `客户`, `供应商`, `合作方`, `合作伙伴`, `相比`, `相较`, `联合`,
  or `共同`;
- a unit belongs to at most one bundle;
- otherwise the mandatory target unit remains a standalone card.

This is deliberately a closed syntactic admission rule, not entity recognition. The implementation must not
try to prove that an arbitrary company name is absent with `_mentioned_entities()`, a widened suffix regex,
or a stock dictionary. Any ambiguous continuation fails closed and remains outside target coverage. The
current local Gate inputs already provide explicit target-only breadth of 3 families for Zhongji and 4 each
for Fudan and Black Sesame; Fudan retains financial, technology, and competitive coverage without relying
on continuation ownership.

Target coverage is the ordered union of the precomputed `coverage_families` on units inside deterministic
target bundles. It is never recomputed from a mixed target/peer presentation group.

### 4.2 Optional peer/industry material

An optional unit may enter the LLM selector only when both conditions hold:

1. **Peer/industry context:** it contains an explicit comparison/industry marker, a generic named-company
   form, or a named subject immediately followed by a corporate action predicate.
2. **Concrete anchor:** it contains a number, percentage, year, product/model token, comparison metric, or a
   concrete event/action such as release, production, verification, delivery, order, capacity change,
   cooperation, acquisition, restriction, or price change.

Generic statements such as `行业竞争格局加剧` do not qualify. Rules are generic and must not contain stock
names, codes, sample-specific product names, or industry-specific exceptions.

Before selection:

- reject exact baseline duplicates;
- remove global exact normalized duplicates, keeping the first source packet in existing quality order;
- remove strict normalized containment duplicates only within the same source;
- preserve every remaining distinct high-value unit; there is no final unit/card cap.

The sole LLM selector receives only eligible optional peer units. It may keep, skip, or group adjacent peer
units. It cannot see, skip, group, or relabel mandatory target units.

## 5. Canonical Flow

```text
source packets
  -> exact source units
  -> deterministic partition
  -> deterministic target bundles (no LLM)
  -> optional peer structural admission + dedupe
  -> per-source peer-only selector batches
  -> validated peer decisions
  -> source-ordered target and peer cards
  -> pack v3 reader/display/profile
```

One shared helper owns target bundling and optional-peer admission:

```python
prepare_external_argument_material(
    units: list[dict], *, stock_name: str, baseline_text: str,
) -> dict
```

It returns exactly:

```python
{
    "target_bundles": [
        {
            "bundle_key": str,
            "units": list[dict],
            "coverage_families": list[str],
        }
    ],
    "optional_peer_units": list[dict],
    "diagnostics": {
        "mandatory_target_unit_count": int,
        "target_bundle_count": int,
        "continuation_rejected_count": int,
        "continuation_truncated_count": int,
        "optional_peer_raw_count": int,
        "optional_peer_eligible_count": int,
        "optional_peer_low_signal_count": int,
        "optional_peer_duplicate_count": int,
        "rejected_by_reason": dict[str, int],
    },
}
```

The function uses plain dictionaries to match the existing pack contracts; no new dataclass/schema layer is
introduced. `build_curated_external_argument_pack()` batches only `optional_peer_units` and records selector
attempts. `build_external_argument_pack()` consumes the same prepared result, creates deterministic keep
decisions for `target_bundles`, validates peer selections, and never recreates admission or dedupe logic.

## 6. Persistence and Versioning

- Keep `curated_external_argument_card.v3` and `curated_external_argument_pack.v3`.
- Keep `curated_external_unit_selection.v1`; the response shape is unchanged.
- Bump producer ownership to `external_unit_selector.v2` so prior Gate B2 packs fail stale rather than being
  read under new coverage semantics.
- Persist each card's evidence units in `(source_id, source_ordinal)` order.
- `enrich_external_evidence_group()` derives families as the fixed-priority ordered union of each admitted
  unit's already materialized `coverage_families`; it does not rescan joined group text.
- When a group contains any `target_bound=True` units, only those target-bound units contribute coverage.
  Target bundles therefore use their unit-family union; peer cards use their peer-unit union.
- Mixed target/peer selector groups are impossible. Enrichment still fails safe if a handcrafted mixed
  group is passed: only units already marked `target_bound` may contribute target coverage.

## 7. Diagnostics

Ready packs record at least:

- `source_unit_count`
- `mandatory_target_unit_count`
- `target_bundle_count`
- `optional_peer_raw_count`
- `optional_peer_eligible_count`
- `optional_peer_low_signal_count`
- `optional_peer_duplicate_count`
- `selector_batch_count`
- `selector_request_count` including retries
- accepted target-card and peer-card counts

Diagnostics do not affect profile or display.

## 8. Allowed Scope

Runtime:

- `scripts/utils/curated_external_argument_cards.py`
- `scripts/utils/curated_external_full_body_viewpoint_claims.py`

Tests:

- `tests/utils/test_curated_external_argument_cards.py`
- `tests/utils/test_curated_external_full_body_viewpoint_claims.py`
- existing reader/display/profile tests only when an assertion must be updated for selector v2

Workflow notes may be added under `docs/agent_workflow/`.

Forbidden:

- stock-specific rules;
- a second selector, semantic repair model, embedding, or fuzzy matcher;
- final total card/source cap;
- report-time source or LLM reads;
- production config/cache/report changes;
- scoring, target price, risk, technical, recommendation, or `KnowledgeSynthesizer` changes;
- network/live Gate B2 execution during implementation.

## 9. Required Tests

| Requirement | Required RED test |
| --- | --- |
| Group persistence follows source order | mixed pool index fixture persists ordinals `[5, 6, 7]`, never `[7, 5, 6]` |
| Grouping cannot change target coverage | same target units with different peer grouping produce identical target family union |
| Peer families do not become target families | handcrafted target+peer group counts only `target_bound` families |
| Mandatory target bypasses LLM | target-only build succeeds when selector raises if called |
| Strict continuation is deterministic | adjacent `公司/该产品` continuation joins target and persists in source order |
| Ambiguous continuation is rejected | `其竞争对手英伟达...`, `双方...`, and relation-switch fixtures remain outside the target bundle |
| Low-signal peer is prefiltered | generic industry-risk sentence never reaches selector |
| High-value peer reaches selector | named peer/industry plus numeric/model/action anchor is supplied unchanged |
| Dedupe is deterministic | global exact and same-source containment duplicates produce one selector unit |
| No total cap | more than one selector batch of distinct eligible peers all reaches selector |
| Admission diagnostics are exact | low-signal and duplicate fixtures increment their named diagnostic fields exactly once |
| Retry accounting is visible | incomplete first response succeeds and `selector_request_count == 2` |
| Selector v1 packs are stale | reader rejects prior selector version after version bump |
| Profile remains target-only | peer-only three-family and same-family volume fixtures remain non-rich |
| Required target breadth remains rich | Fudan-like generic fixtures retain financial, technology, and competitive target coverage |
| Target bundle persistence is ordered | deterministic bundle ordinals are `[7, 8, 9]`, never pool-index order |

Run the focused producer/reader/display/profile suites, the related Chapter 4 suite,
`tools/ci_grep_gates.sh`, and `git diff --check`. No live model or report run is part of implementation.

## 10. Failure Modes and Stop Conditions

| Failure | Stop/response |
| --- | --- |
| Target coverage requires an LLM decision | stop; ownership boundary is violated |
| Optional peer pool is prepared differently in wrapper and builder | stop; replace with one shared helper |
| A valid distinct high-value peer is removed only to meet a count | stop; no-cap contract is violated |
| Continuation rule needs a stock/product-specific phrase | stop and return to design |
| Existing exact evidence/hash/citation chain regresses | stop; do not weaken reader validation |
| Runtime code grows by more than net +140 lines for this batch | stop and replace existing mixed-pool logic instead of layering another path |
| Focused reader/display/profile tests fail outside explicit version assertions | stop and report the regression |

## 11. Acceptance Gate

After code-only verification passes, rerun Gate B2 locally against the same six inputs. Approval requires:

- all six packs pass reader/display/lint;
- target family sets and profile routing are identical across two runs per stock;
- Fudan retains financial, technology, and competitive target families;
- every evidence unit remains an exact source substring with valid hashes/citations;
- no target fact depends on peer grouping;
- selector request count and peer-card volume are materially below the blocked run, without a total cap;
- manual samples contain no entity misbinding or low-signal peer flood.

## 12. Design Delta

- **Accepted:** fix persistence order; move target admission and strict continuation ownership out of the
  LLM; derive target coverage only from deterministic target-bound units; structurally filter and dedupe
  optional peer material before the sole selector; add latency/admission diagnostics. Round 1 MF-01 is
  resolved by closed syntax and fail-closed ambiguity rather than unreliable entity-name recognition;
  MF-02 is resolved by per-unit family union in enrichment; MF-03 is resolved by explicit negative and
  diagnostic tests.
- **Rejected:** a two-line order/union hotfix because it leaves the 27-call peer flood; larger batches because
  they increase incomplete responses; a fixed card/source cap because it would discard distinct evidence;
  stock-specific recall/entity dictionaries and widened company-suffix regexes because they remain incomplete
  and do not generalize.
- **Deferred:** renderer prose compression and production config/cache promotion. They depend on Gate B2 but
  are not needed to fix selection correctness or latency. Peer anchor-type breakdown and explicit profile
  scope enumeration are nice-to-have follow-ups, not Gate B2 requirements.
- **R2 required:** no. All three must-fix findings are resolved without changing target/peer ownership,
  evidence identity, no-cap behavior, or the sole-selector boundary.
